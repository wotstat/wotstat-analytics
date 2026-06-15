import re

import BigWorld
from BattleFeedbackCommon import BATTLE_EVENT_TYPE
from constants import ARENA_BONUS_TYPE, ARENA_GAMEPLAY_NAMES, ROLE_TYPE_TO_LABEL
from gui.battle_control.battle_constants import FEEDBACK_EVENT_ID
from helpers import dependency
from items import vehicles as vehiclesWG, EQUIPMENT_TYPES, tankmen
from skeletons.gui.battle_session import IBattleSessionProvider
from .sessionStorage import sessionStorage
from ..common.exceptionSending import with_exception_sending
from ..load_mod import config
from ..utils import print_error
from .extra.ExtraCollector import ExtraCollector

from .providers.ArenaInfoProvider import ArenaInfoProvider
from .providers.AccountStatsProvider import AccountStatsProvider
from .providers.ServerOnlineProvider import ServerOnlineProvider
from .providers.SystemInfoProvider import SystemInfoProvider

from .events import DynamicBattleEvent, SessionMeta, ServerInfo, HangarEvent  # noqa: F401

import typing
if typing.TYPE_CHECKING:
  from Avatar import PlayerAvatar

def vector(t):
  if t is None: return None

  try: return {'x': t.x, 'y': t.y, 'z': t.z}
  except: return None


ARENA_TAGS = dict(
  [(v, k) for k, v in ARENA_BONUS_TYPE.__dict__.iteritems() if isinstance(v, int)])

FEEDBACK_EVENT = dict([(v, k) for k, v in FEEDBACK_EVENT_ID.__dict__.iteritems() if isinstance(v, int)])
BATTLE_EVENT = dict([(v, k) for k, v in BATTLE_EVENT_TYPE.__dict__.iteritems() if isinstance(v, int)])


arenaInfoProvider = ArenaInfoProvider()
serverOnlineProvider = ServerOnlineProvider()
accountStatsProvider = AccountStatsProvider()
systemInfoProvider = SystemInfoProvider()


def short_tank_type(tag):
  tags = {
    'lightTank': 'LT',
    'mediumTank': 'MT',
    'heavyTank': 'HT',
    'AT-SPG': 'AT',
    'SPG': 'SPG',
  }
  return tags[tag] if tag in tags else tag

def get_tank_type(vehicleTags):
  tags = vehicleTags
  res = 'mediumTank' if 'mediumTank' in tags \
    else 'heavyTank' if 'heavyTank' in tags \
    else 'AT-SPG' if 'AT-SPG' in tags \
    else 'SPG' if 'SPG' in tags \
    else 'lightTank' if 'lightTank' in tags \
    else 'None'
  return res

def get_tank_role(role):
  return ROLE_TYPE_TO_LABEL.get(role, 'None')


def get_comp7_skill_tag(skill_id):
  if not skill_id:
    return None

  equipment = vehiclesWG.g_cache.getEquipmentByID(skill_id)
  return equipment.name if equipment is not None else None

def get_current_comp7_skill_info(player):
  if player.arena.bonusType != ARENA_BONUS_TYPE.COMP7:
    return None

  vehicle = BigWorld.entities.get(player.playerVehicleID, None)
  if vehicle is None or not hasattr(vehicle, 'selectedComp7Skill'):
    return None

  skill_id = vehicle.selectedComp7Skill
  if not skill_id:
    return None

  return get_comp7_skill_tag(skill_id)

def get_current_equipment_info(player):
  try:
    vehicleType = player.arena.vehicles[player.playerVehicleID].get('vehicleType', None)
    if vehicleType is None: return None

    return [device.name if device is not None else None for device in vehicleType.optionalDevices]
  except Exception as e:
    print_error("Error while getting current equipment info: {}".format(str(e)))
    return None

def get_current_own_vehicle(player):
  vehicle = BigWorld.entities.get(player.playerVehicleID, None)
  if vehicle is None: return None

  return vehicle.dynamicComponents.get('ownVehicle')

def get_consumables_from_battle_controller():
  try:
    sessionProvider = dependency.instance(IBattleSessionProvider) # type: IBattleSessionProvider
    equipmentsCtrl = sessionProvider.shared.equipments
    if equipmentsCtrl is None: return None

    order = getattr(equipmentsCtrl, '_order', None)
    equipments = getattr(equipmentsCtrl, '_equipments', None)
    equipmentCount = getattr(equipmentsCtrl, '_EquipmentsController__equipmentCount', None)

    if order is None or equipments is None or equipmentCount is None or len(order) < equipmentCount:
      return None

    result = []
    for intCD in order:
      if len(result) >= equipmentCount: break
      if not intCD: result.append(None)
      else:
        descriptor = equipments[intCD].getDescriptor()
        if descriptor.equipmentType == EQUIPMENT_TYPES.regular:
          result.append(descriptor.name)

    if len(result) < equipmentCount: return None

    return result
  except Exception as e:
    print_error("Error while getting current consumables info: {}".format(str(e)))
    return None

def get_consumables_from_prebattle_setup():
  try:
    sessionProvider = dependency.instance(IBattleSessionProvider)
    prebattleSetups = sessionProvider.shared.prebattleSetups
    if prebattleSetups is None: return None
    if prebattleSetups.isSelectionEnded(): return None

    vehicle = get_private_attr(prebattleSetups, '__vehicle')
    if vehicle is None: return None

    return [item.name if item is not None else None for item in vehicle.consumables.installed]
  except Exception as e:
    print_error("Error while getting prebattle consumables info: {}".format(str(e)))
    return None

def get_current_consumables_info():
  consumables = get_consumables_from_battle_controller()
  if consumables is not None: return consumables

  return get_consumables_from_prebattle_setup()

def get_shells_from_battle_controller():
  try:
    sessionProvider = dependency.instance(IBattleSessionProvider)
    ammoCtrl = sessionProvider.shared.ammo
    if ammoCtrl is None: return None

    layout = ammoCtrl.getOrderedShellsLayout()
    if not layout: return None

    result = {}
    for shellInfo in layout:
      descriptor = shellInfo[1]
      quantity = shellInfo[2]
      result[descriptor.kind] = result.get(descriptor.kind, 0) + quantity

    return result
  except Exception as e:
    print_error("Error while getting current shells info: {}".format(str(e)))
    return None

def get_shells_from_prebattle_setup():
  try:
    sessionProvider = dependency.instance(IBattleSessionProvider)
    prebattleSetups = sessionProvider.shared.prebattleSetups
    if prebattleSetups is None: return None
    if prebattleSetups.isSelectionEnded(): return None

    vehicle = get_private_attr(prebattleSetups, '__vehicle')
    if vehicle is None: return None

    result = {}
    for shell in vehicle.shells.installed.getItems():
      result[shell.descriptor.kind] = result.get(shell.descriptor.kind, 0) + shell.count

    return result
  except Exception as e:
    print_error("Error while getting prebattle shells info: {}".format(str(e)))
    return None

def get_current_shells_info():
  shells = get_shells_from_battle_controller()
  if shells is not None: return shells

  return get_shells_from_prebattle_setup()

def get_current_battle_booster_info(player):
  try:
    ownVehicle = get_current_own_vehicle(player)
    if ownVehicle is None: return None

    for equipment in ownVehicle.equipment:
      descriptor = vehiclesWG.getItemByCompactDescr(equipment.compactDescr)
      if descriptor.equipmentType == EQUIPMENT_TYPES.battleBoosters:
        return descriptor.name

    return None
  except Exception as e:
    print_error("Error while getting current battle booster info: {}".format(str(e)))
    return None

def get_tankman_actual_level(descriptor, vehicle):
  if hasattr(descriptor, 'efficiencyOnVehicle'):
    return int(round(descriptor.roleLevel * descriptor.efficiencyOnVehicle(vehicle.typeDescriptor)))

  if hasattr(descriptor, 'skillsEfficiency'):
    vehicleType = vehicle.typeDescriptor.type
    if hasattr(descriptor, 'isOwnVehicleOrPremium') and not descriptor.isOwnVehicleOrPremium(vehicleType):
      return 0

    return int(round(descriptor.skillsEfficiency * tankmen.MAX_SKILL_LEVEL))

  return descriptor.roleLevel

def get_tankman_skills_info(descriptor, roles):
  skillLevels = getattr(descriptor, 'skillLevels', None)
  if callable(skillLevels):
    return [{'tag': tag, 'level': level} for tag, level in skillLevels(roles)]

  return [{'tag': tag, 'level': level} for tag, level in skillLevels]

def get_current_crew_info(player):
  # type: (PlayerAvatar) -> list[dict] | None
  try:
    sessionProvider = dependency.instance(IBattleSessionProvider)
    vehicleState = sessionProvider.shared.vehicleState
    if vehicleState is None: return None

    vehicle = vehicleState.getControllingVehicle()
    if vehicle is None or vehicle.id != player.playerVehicleID: return None

    crewCompactDescrs = getattr(vehicle, 'crewCompactDescrs', None)
    if crewCompactDescrs is None: return None

    crewRoles = vehicle.typeDescriptor.type.crewRoles
    result = []
    for compactDescr, roles in zip(crewCompactDescrs, crewRoles):
      descriptor = tankmen.TankmanDescr(compactDescr, battleOnly=True) # type: tankmen.TankmanDescr
      result.append({
        'roles': list(roles),
        'level': get_tankman_actual_level(descriptor, vehicle),
        'skills': get_tankman_skills_info(descriptor, roles)
      })

    return result
  except Exception as e:
    print_error("Error while getting current crew info: {}".format(str(e)))
    return None


@with_exception_sending
def setup_server_info(serverInfo):
  # type: (ServerInfo) -> None
  
  player = BigWorld.player()
  serverName = player.connectionMgr.serverUserName
  if config.get('hideServer'):
    serverName = re.sub(r'\d+', '_hide_', serverName)
  
  serverInfo.setupServerInfo(
    serverName=serverName,
    serverOnline=serverOnlineProvider.serverOnline,
    regionOnline=serverOnlineProvider.regionOnline,
  )

@with_exception_sending
def setup_dynamic_battle_info(dynamicBattleEvent):
  # type: (DynamicBattleEvent) -> None
  
  player = BigWorld.player()
  
  dynamicBattleEvent.setupDynamicBattleInfo(
    arenaTag=player.arena.arenaType.geometry,
    playerName=player.name,
    playerClan=player.arena.vehicles[player.playerVehicleID]['clanAbbrev'],
    playerClanDBID=player.arena.vehicles[player.playerVehicleID]['clanDBID'],
    accountDBID=player.arena.vehicles[player.playerVehicleID]['accountDBID'],
    battleMode=ARENA_TAGS[player.arena.bonusType],
    battleGameplay=ARENA_GAMEPLAY_NAMES[player.arenaTypeID >> 16],
    team=player.team,
    tankTag=BigWorld.entities[player.playerVehicleID].typeDescriptor.name,
    tankType=short_tank_type(get_tank_type(player.vehicleTypeDescriptor.type.tags)),
    tankRole=get_tank_role(player.vehicleTypeDescriptor.role),
    tankLevel=player.vehicleTypeDescriptor.level,
    gunTag=player.vehicleTypeDescriptor.gun.name,
    comp7SkillTag=get_current_comp7_skill_info(player) or '',
    allyTeamHealth=arenaInfoProvider.allyTeamHealth[0],
    enemyTeamHealth=arenaInfoProvider.enemyTeamHealth[0],
    allyTeamMaxHealth=arenaInfoProvider.allyTeamHealth[1],
    enemyTeamMaxHealth=arenaInfoProvider.enemyTeamHealth[1],
    allyTeamFragsCount=arenaInfoProvider.allyTeamFragsCount,
    enemyTeamFragsCount=arenaInfoProvider.enemyTeamFragsCount,
    mapsBlackList=accountStatsProvider.mapBlackList,
    equipment=get_current_equipment_info(player) or [],
    consumables=get_current_consumables_info() or [],
    battleBooster=get_current_battle_booster_info(player) or '',
    shells=get_current_shells_info() or {},
    crew=get_current_crew_info(player) or []
  )

  dynamicBattleEvent.setupSystemInfo(systemInfoProvider.getSystemInfo())
  dynamicBattleEvent.setupExtra(ExtraCollector.instance().getExtraData())

@with_exception_sending
def setup_session_meta(dynamicBattleEvent):
  # type: (SessionMeta) -> None
  
  sessionStorage.setup_session_meta(dynamicBattleEvent)

@with_exception_sending
def setup_hangar_event(hangarEvent):
  # type: (HangarEvent) -> None

  hangarEvent.setupHangarEvent(BigWorld.player().name)
  
def get_private_attr(obj, attr):
  className = obj.__class__.__name__
  
  if not className.startswith('_'): className = '_{}'.format(className)
  
  target = className + attr
  if hasattr(obj, target): return getattr(obj, target)
  return None
