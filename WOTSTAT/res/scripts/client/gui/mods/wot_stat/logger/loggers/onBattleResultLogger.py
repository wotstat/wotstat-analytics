import BattleReplay
import BigWorld
import json
import personal_missions
from PlayerEvents import g_playerEvents
from skeletons.gui.battle_session import IBattleSessionProvider
from skeletons.gui.lobby_context import ILobbyContext
from skeletons.gui.server_events import IEventsCache
from items import vehicles as vehiclesWG
from constants import ARENA_PERIOD, FINISH_REASON, FINISH_REASON_NAMES
from helpers import dependency

try:
  from gui.battle_control.arena_info.arena_vos import Comp7Keys
  from gui.impl.lobby.comp7 import comp7_i18n_helpers
except:
  from comp7.gui.battle_control.arena_info.arena_vos import Comp7Keys
  from comp7.gui.impl.lobby.comp7_helpers import comp7_i18n_helpers

try: from potapov_quests import PQ_STATE as PM_STATE
except ImportError: from pm_quests import PM_STATE

from ..eventLogger import eventLogger
from ..events import OnBattleResult
from ..sessionStorage import sessionStorage
from ..utils import short_tank_type, get_tank_role, get_comp7_skill_tag, setup_dynamic_battle_info, setup_session_meta, setup_server_info
from ..wotHookEvents import wotHookEvents
from ...common.exceptionSending import with_exception_sending
from ...utils import print_debug, print_error

import typing
if typing.TYPE_CHECKING:
  from gui.server_events.event_items import PersonalMission


PM_STATE_NAMES = dict([(v, k) for k, v in PM_STATE.__dict__.iteritems() if isinstance(v, int)])

def parseCurrencies(results):
  # type: (dict) -> dict
  
  currencies = {
    'originalCredits': results.get('originalCredits', 0),
    'originalGold': results.get('originalGold', 0),
    'originalCrystal': results.get('originalCrystal', 0),
    'subtotalCredits': results.get('subtotalCredits', 0),
    'autoRepairCost': 0,
    'autoLoadCredits': 0,
    'autoLoadGold': 0,
    'autoEquipCredits': 0,
    'autoEquipGold': 0,
    'autoEquipCrystals': 0,
    'piggyBank': 0,
  }
  
  if 'autoRepairCost' in results:
    currencies['autoRepairCost'] = results.get('autoRepairCost', 0)
    
  if 'autoLoadCost' in results:
    cost = results.get('autoLoadCost', (0, 0))
    currencies['autoLoadCredits'] = cost[0]
    currencies['autoLoadGold'] = cost[1]
      
  if 'autoEquipCost' in results:
    cost = results.get('autoEquipCost', (0, 0, 0))
    currencies['autoEquipCredits'] = cost[0]
    currencies['autoEquipGold'] = cost[1]
    currencies['autoEquipCrystals'] = cost[2]
      
  if 'piggyBank' in results:
    currencies['piggyBank'] = results.get('piggyBank', 0)
      
  return currencies

def parsePersonalMissions(results):
  # type: (dict) -> dict
  pmProgress = results.get('PMProgress', {}) # type: dict
  pm2Progress = results.get('PM2Progress', {}) # type: dict
  pmProgress.update(pm2Progress)

  quests = dependency.instance(IEventsCache).getPersonalMissions().getAllQuests()

  parsedPmQuests = []

  for qID, data in pmProgress.iteritems():
    if qID not in quests: continue
    quest = quests[qID] # type: PersonalMission
    tag = quest.getGeneralQuestID()
    current = data.get('current', None)
    if not current: continue

    parsedConditions = []
    for condition, progress in current.iteritems():
      state = progress.get('state', None)
      stateName = PM_STATE_NAMES.get(state, 'UNKNOWN')

      battles = progress.get('battles', None)
      battlesArray = battles if isinstance(battles, list) else None
      isBattlesAreBool = battlesArray and all(isinstance(b, bool) for b in battlesArray)
      
      parsedConditions.append({
        'tag': condition,
        'state': stateName,
        'value': progress.get('value', None),
        'goal': progress.get('goal', None),
        'battles': battlesArray if isBattlesAreBool else None,
      })

    parsedPmQuests.append({
      'tag': tag,
      'conditions': parsedConditions
    })

  questsProgress = results.get('questsProgress', {}) # type: dict
  for qID, data in questsProgress.iteritems():
    if not personal_missions.g_cache.isPersonalMission(qID): continue
    
    parsedPmQuests.append({
      'tag': qID,
      'conditions': []
    })

  return parsedPmQuests

def get_comp7_rank_tag(rankInfo, isQualActive, ranksConfig):
  if isQualActive:
    return 'qual'

  if not rankInfo:
    return None

  try:
    rank, divisionIdx = rankInfo
  except:
    return None

  if not rank:
    return None

  rankTag = comp7_i18n_helpers.RANK_MAP.get(rank, None)
  if rankTag is None:
    return None

  divisions = ()
  try:
    divisions = ranksConfig.divisionsByRank.get(rank, ())
  except:
    pass

  if len(divisions) <= 1:
    return rankTag

  divisionTag = comp7_i18n_helpers.DIVISION_MAP.get(divisionIdx, None)
  if divisionTag is None:
    return None

  return '{}_{}'.format(rankTag, divisionTag)

class OnBattleResultLogger:
  arenas_id_wait_battle_result = []
  battle_loaded = False
  eventsCache = dependency.descriptor(IEventsCache)
  sessionProvider = dependency.descriptor(IBattleSessionProvider)
  lobbyContext = dependency.descriptor(ILobbyContext)

  def __init__(self):
    self.arenas_id_wait_battle_result = []
    self.precreated_battle_result_event = dict()
    self.comp7_skill_tags_by_arena = dict()
    self.comp7_ranks_by_arena = dict()
    self.battle_loaded = False

    g_playerEvents.onBattleResultsReceived += self.on_battle_results_received
    eventLogger.on_session_created += self.on_session_created
    eventLogger.on_battle_started += self.on_battle_started
    wotHookEvents.PlayerAvatar_onArenaPeriodChange += self.on_arena_period_change
    wotHookEvents.PlayerAvatar_onBecomeNonPlayer += self.on_avatar_become_non_player
    self.battle_result_cache_checker()

  def on_session_created(self, battleEventSession):
    self.arenas_id_wait_battle_result.append(battleEventSession.arenaID)  

  def on_battle_started(self, battleEventSession, arenaID=None):
    BigWorld.callback(1, lambda: self.create_battle_result_event(arenaID or battleEventSession.arenaID))

  def create_battle_result_event(self, arenaID):
    print_debug("Creating battle result event for arenaID: {}".format(arenaID))
    if arenaID in self.precreated_battle_result_event: return

    event = OnBattleResult()
    setup_dynamic_battle_info(event)
    setup_server_info(event)
    self.precreated_battle_result_event[arenaID] = event

  def on_arena_period_change(self, obj, period, *a, **k):
    if period is ARENA_PERIOD.AFTERBATTLE:
      self.update_comp7_skill_tags()
      self.update_comp7_ranks()

  def on_avatar_become_non_player(self, obj, *a, **k):
    self.update_comp7_skill_tags(obj.arenaUniqueID, obj)
    self.update_comp7_ranks(obj.arenaUniqueID, obj)

  def update_comp7_skill_tags(self, arenaID=None, player=None):
    player = player or BigWorld.player()
    if not hasattr(player, 'arena') or player.arena is None:
      return

    arenaID = arenaID or player.arenaUniqueID
    skill_tags = self.comp7_skill_tags_by_arena.setdefault(arenaID, dict())
    for vehicleID, vehicle in player.arena.vehicles.iteritems():
      skill_tag = get_comp7_skill_tag(vehicle.get('selectedComp7Skill', 0))
      if skill_tag: skill_tags[vehicleID] = skill_tag

  def update_comp7_ranks(self, arenaID=None, player=None):
    player = player or BigWorld.player()
    if not hasattr(player, 'arena') or player.arena is None:
      return

    arenaID = arenaID or player.arenaUniqueID
    try:
      arenaDP = self.sessionProvider.getArenaDP()
      ranksConfig = self.lobbyContext.getServerSettings().comp7RanksConfig
    except: return

    try:
      comp7_ranks = self.comp7_ranks_by_arena.setdefault(arenaID, dict())
      for vInfo in arenaDP.getVehiclesInfoIterator():
        rankInfo = vInfo.gameModeSpecific.getValue(Comp7Keys.RANK, None)
        isQualActive = vInfo.gameModeSpecific.getValue(Comp7Keys.IS_QUAL_ACTIVE, False)
        comp7_rank = get_comp7_rank_tag(rankInfo, isQualActive, ranksConfig)
        if comp7_rank: comp7_ranks[vInfo.vehicleID] = comp7_rank
    except Exception as e:
      print_error('failed to update comp7 ranks for arena: ' + str(e))

  @with_exception_sending
  def on_battle_results_received(self, isPlayerVehicle, results):
    if not isPlayerVehicle or BattleReplay.isPlaying(): return
    self.update_comp7_skill_tags(results.get('arenaUniqueID'))
    self.update_comp7_ranks(results.get('arenaUniqueID'))
    self.process_battle_result(results)

  @with_exception_sending
  def battle_result_cache_checker(self):
    BigWorld.callback(3, self.battle_result_cache_checker)

    def result_callback(arenaID, code, result):
      if code > 0:
        self.process_battle_result(result)

    if len(self.arenas_id_wait_battle_result) > 0:
      arenaID = self.arenas_id_wait_battle_result.pop(0)
      self.arenas_id_wait_battle_result.append(arenaID)
      try:
        BigWorld.player().battleResultsCache.get(arenaID, lambda code, battleResults: result_callback(arenaID, code, battleResults))
      except:
        pass

  def process_battle_result(self, results):
    arenaID = results.get('arenaUniqueID')
    print_debug("Got result for {}".format(arenaID))

    if arenaID not in self.arenas_id_wait_battle_result:
      return

    self.arenas_id_wait_battle_result.remove(arenaID)
    battleEvent = self.precreated_battle_result_event.pop(arenaID, None)  # type: OnBattleResult
    comp7_skill_tags = self.comp7_skill_tags_by_arena.pop(arenaID, dict()) # type: dict
    comp7_ranks = self.comp7_ranks_by_arena.pop(arenaID, dict()) # type: dict

    if battleEvent is None:
      print_error('missing precreated battle result event for {}'.format(arenaID))
      return

    decodeResult = {}
    try:
      winnerTeam = results['common']['winnerTeam']
      playerTeam = results['personal']['avatar']['team']
      winnerTeamIsMy = playerTeam == winnerTeam
      teamHealth = [results['common']['teamHealth'][1], results['common']['teamHealth'][2]]

      players = results['players'] # type: dict
      avatars = results['avatars'] # type: dict
      vehicles = results['vehicles'] # type: dict
      personalAvatar = results['personal']['avatar'] # type: dict
      playersResultList = list()
      personalVehicleId = None

      squadStorage = dict()
      squadCount = 0
      for playerID in players:
        squadID = players[playerID]['prebattleID']
        if squadID != 0 and squadID not in squadStorage:
          squadCount += 1
          squadStorage[squadID] = squadCount

      for vehicleId in vehicles:
        if vehicles[vehicleId][0]['accountDBID'] == personalAvatar['accountDBID']:
          personalVehicleId = vehicleId

      def getVehicleInfo(vehicle):
        veWG = vehiclesWG.getVehicleType(vehicle['typeCompDescr'])
        return {
          'spotted': vehicle['spotted'],
          'lifeTime': vehicle['lifeTime'],
          'mileage': vehicle['mileage'],
          'damageBlockedByArmor': vehicle['damageBlockedByArmor'],
          'damageAssistedRadio': vehicle['damageAssistedRadio'],
          'damageAssistedTrack': vehicle['damageAssistedTrack'],
          'damageAssistedStun': vehicle['damageAssistedStun'],
          'damageReceivedFromInvisibles': vehicle['damageReceivedFromInvisibles'],
          'damageReceived': vehicle['damageReceived'],
          'shots': vehicle['shots'],
          'directEnemyHits': vehicle['directEnemyHits'],
          'piercingEnemyHits': vehicle['piercingEnemyHits'],
          'explosionHits': vehicle['explosionHits'],
          'damaged': vehicle['damaged'],
          'damageDealt': vehicle['damageDealt'],
          'kills': vehicle['kills'],
          'stunned': vehicle['stunned'],
          'stunDuration': vehicle['stunDuration'],
          'piercingsReceived': vehicle['piercingsReceived'],
          'directHitsReceived': vehicle['directHitsReceived'],
          'explosionHitsReceived': vehicle['explosionHitsReceived'],
          'tankLevel': veWG.level,
          'tankTag': veWG.name,
          'tankType': short_tank_type(veWG.classTag),
          'tankRole': get_tank_role(veWG.role),
          'maxHealth': vehicle['maxHealth'],
          'health': max(0, vehicle['health']),
          'isAlive': vehicle['health'] > 0,
          'comp7PrestigePoints': vehicle.get('comp7PrestigePoints', 0),
          'xp': vehicle.get('xp', 0),
        }

      for vehicleId in vehicles:
        vehicle = vehicles[vehicleId][0]
        bdid = vehicle.get('accountDBID', None)
        if bdid is None: continue
        if bdid not in players: continue
        if bdid not in avatars: continue
        player = players[bdid]
        vehAvatar = avatars[bdid]
        squadID = player['prebattleID']
        
        res = {
          'name': player['realName'],
          'squadID': squadStorage[squadID] if squadID in squadStorage else 0,
          'bdid': bdid,
          'clan': player['clanAbbrev'],
          'clanDBID': player['clanDBID'],
          'team': player['team'],
          'playerRank': vehAvatar['playerRank'],
          'comp7SkillTag': comp7_skill_tags.get(vehicleId, None),
          'comp7Rank': comp7_ranks.get(vehicleId, None),
          '__vehicleId': vehicleId
        }
        res.update(getVehicleInfo(vehicle))
        playersResultList.append(res)
        
      playersResultList = sorted(playersResultList, key=lambda p: p['team'])
      
      indexById = {}
      for index in range(len(playersResultList)):
        indexById[playersResultList[index]['__vehicleId']] = (index + 1)
        
      for result in playersResultList:
        resultID = result.pop('__vehicleId')
        killerId = vehicles[resultID][0]['killerID']
        result['killerIndex'] = indexById[killerId] if killerId in indexById else -1

      personalVehicle = results['personal'].items()[0][1]
      killerId = personalVehicle['killerID']
      squadID = players[personalAvatar['accountDBID']]['prebattleID']
      personal = {
        'team': personalAvatar['team'],
        'killerIndex': indexById[killerId] if killerId in indexById else -1,
        'squadID': squadStorage[squadID] if squadID in squadStorage else 0,
        'playerRank': personalAvatar['playerRank'],
        'comp7SkillTag': battleEvent.comp7SkillTag,
        'comp7Rank': comp7_ranks.get(personalVehicleId, None),
      }
      personal.update(getVehicleInfo(personalVehicle))
      personal.update({'xp': personalVehicle['originalXP']})
      
      comp7 = {
        'ratingDelta': personalAvatar.get('comp7RatingDelta', 0),
        'rating': personalAvatar.get('comp7Rating', 0) + personalAvatar.get('comp7RatingDelta', 0),
        'qualBattleIndex': personalAvatar.get('comp7QualBattleIndex', 0),
        'qualActive': personalAvatar.get('comp7QualActive', False),
      }
      
      currencies = parseCurrencies(personalVehicle)

      try: parsedPmQuests = parsePersonalMissions(personalAvatar)
      except: parsedPmQuests = []

      try:
        progress = personalAvatar.get('PMProgress', {})
        rawPmQuests = json.dumps(progress)
      except: rawPmQuests = ''
      

      battle_result = 'tie' if not winnerTeam else 'win' if winnerTeamIsMy else 'lose'
      decodeResult['playerTeam'] = playerTeam
      decodeResult['result'] = battle_result
      decodeResult['teamHealth'] = teamHealth
      decodeResult['personal'] = personal
      decodeResult['comp7'] = comp7
      decodeResult['playersResults'] = playersResultList
      decodeResult['duration'] = results['common']['duration']
      decodeResult['finishReason'] = FINISH_REASON_NAMES.get(results['common']['finishReason'], FINISH_REASON_NAMES[FINISH_REASON.UNKNOWN])
      decodeResult['winnerTeam'] = winnerTeam
      decodeResult['arenaID'] = arenaID
      decodeResult['currencies'] = currencies
      decodeResult['isPremium'] = personalVehicle.get('isPremium', False)
      decodeResult['fortClanDBIDs'] = personalAvatar.get('fortClanDBIDs', [])
      decodeResult['personalMissions'] = parsedPmQuests
      decodeResult['personalMissionsRaw'] = rawPmQuests
      setup_session_meta(battleEvent)
      battleEvent.set_result(result=decodeResult)
      eventLogger.emit_event(battleEvent, arena_id=arenaID)

      sessionStorage.on_result_battle(result=battle_result,
                                      player_team=playerTeam,
                                      player_bdid=personalAvatar['accountDBID'],
                                      players_results=playersResultList)

    except Exception as e:
      print_error('cannot decode battle result\n' + str(e))


onBattleResultLogger = OnBattleResultLogger()
