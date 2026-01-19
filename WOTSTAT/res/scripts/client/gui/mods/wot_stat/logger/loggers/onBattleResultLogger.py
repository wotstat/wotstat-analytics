import BattleReplay
import BigWorld
import json
import personal_missions
from PlayerEvents import g_playerEvents
from skeletons.gui.server_events import IEventsCache
from items import vehicles as vehiclesWG
from constants import FINISH_REASON, FINISH_REASON_NAMES
from helpers import dependency

try: from potapov_quests import PQ_STATE as PM_STATE
except ImportError: from pm_quests import PM_STATE

from ..eventLogger import eventLogger
from ..events import OnBattleResult
from ..sessionStorage import sessionStorage
from ..utils import short_tank_type, get_tank_role, setup_dynamic_battle_info, setup_session_meta, setup_server_info
from ...common.exceptionSending import with_exception_sending
from ...utils import print_log, print_debug

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

class OnBattleResultLogger:
  arenas_id_wait_battle_result = []
  battle_loaded = False
  eventsCache = dependency.descriptor(IEventsCache)

  def __init__(self):
    self.arenas_id_wait_battle_result = []
    self.precreated_battle_result_event = dict()
    self.battle_loaded = False

    g_playerEvents.onBattleResultsReceived += self.on_battle_results_received
    eventLogger.on_session_created += self.on_session_created
    self.battle_result_cache_checker()

  def on_session_created(self, battleEventSession):
    self.arenas_id_wait_battle_result.append(battleEventSession.arenaID)
    event = OnBattleResult()
    setup_dynamic_battle_info(event)
    setup_server_info(event)
    self.precreated_battle_result_event[battleEventSession.arenaID] = event

  @with_exception_sending
  def on_battle_results_received(self, isPlayerVehicle, results):
    if not isPlayerVehicle or BattleReplay.isPlaying():
      return
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
        BigWorld.player().battleResultsCache.get(arenaID, lambda code, battleResults: result_callback(arenaID, code,
                                                                                                      battleResults))
      except:
        pass


  def process_battle_result(self, results):
    arenaID = results.get('arenaUniqueID')
    print_debug("Got result for {}".format(arenaID))

    if arenaID not in self.arenas_id_wait_battle_result:
      return

    self.arenas_id_wait_battle_result.remove(arenaID)
    battleEvent = self.precreated_battle_result_event.pop(arenaID)  # type: OnBattleResult

    decodeResult = {}
    try:
      winnerTeam = results['common']['winnerTeam']
      playerTeam = results['personal']['avatar']['team']
      winnerTeamIsMy = playerTeam == winnerTeam
      teamHealth = [results['common']['teamHealth'][1], results['common']['teamHealth'][2]]

      players = results['players']
      avatars = results['avatars']
      vehicles = results['vehicles']
      playersResultList = list()

      squadStorage = dict()
      squadCount = 0
      for playerID in players:
        squadID = players[playerID]['prebattleID']
        if squadID != 0 and squadID not in squadStorage:
          squadCount += 1
          squadStorage[squadID] = squadCount


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
        bdid = vehicle['accountDBID']
        if bdid not in players: continue
        if bdid not in avatars: continue
        player = players[bdid]
        avatar = avatars[bdid]
        squadID = player['prebattleID']
        res = {
          'name': player['realName'],
          'squadID': squadStorage[squadID] if squadID in squadStorage else 0,
          'bdid': bdid,
          'team': player['team'],
          'playerRank': avatar['playerRank'],
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

      avatar = results['personal']['avatar']
      personalRes = results['personal'].items()[0][1]
      killerId = personalRes['killerID']
      squadID = players[avatar['accountDBID']]['prebattleID']
      personal = {
        'team': avatar['team'],
        'xp': personalRes['originalXP'],
        'killerIndex': indexById[killerId] if killerId in indexById else -1,
        'squadID': squadStorage[squadID] if squadID in squadStorage else 0,
        'playerRank': avatar['playerRank'],
      }
      personal.update(getVehicleInfo(personalRes))
      
      comp7 = {
        'ratingDelta': avatar.get('comp7RatingDelta', 0),
        'rating': avatar.get('comp7Rating', 0) + avatar.get('comp7RatingDelta', 0),
        'qualBattleIndex': avatar.get('comp7QualBattleIndex', 0),
        'qualActive': avatar.get('comp7QualActive', False),
      }
      
      currencies = parseCurrencies(personalRes)

      try: parsedPmQuests = parsePersonalMissions(avatar)
      except: parsedPmQuests = []

      try:
        progress = avatar.get('PMProgress', {})
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
      decodeResult['isPremium'] = personalRes.get('isPremium', False)
      decodeResult['personalMissions'] = parsedPmQuests
      decodeResult['personalMissionsRaw'] = rawPmQuests
      setup_session_meta(battleEvent)
      battleEvent.set_result(result=decodeResult)
      eventLogger.emit_event(battleEvent, arena_id=arenaID)

      sessionStorage.on_result_battle(result=battle_result,
                                      player_team=playerTeam,
                                      player_bdid=avatar['accountDBID'],
                                      players_results=playersResultList)

    except Exception as e:
      print_log('cannot decode battle result\n' + str(e))


onBattleResultLogger = OnBattleResultLogger()
