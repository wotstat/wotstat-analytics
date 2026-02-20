import re

import BigWorld
from BattleFeedbackCommon import BATTLE_EVENT_TYPE
from constants import ARENA_BONUS_TYPE, ARENA_GAMEPLAY_NAMES, ROLE_TYPE_TO_LABEL
from gui.battle_control.battle_constants import FEEDBACK_EVENT_ID
from .sessionStorage import sessionStorage
from ..common.exceptionSending import with_exception_sending
from ..load_mod import config
from .extra.ExtraCollector import ExtraCollector

from .providers.ArenaInfoProvider import ArenaInfoProvider
from .providers.AccountStatsProvider import AccountStatsProvider
from .providers.ServerOnlineProvider import ServerOnlineProvider
from .providers.SystemInfoProvider import SystemInfoProvider

from .events import DynamicBattleEvent, SessionMeta, ServerInfo, HangarEvent  # noqa: F401

def vector(t): return {'x': t.x, 'y': t.y, 'z': t.z} if t else None


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
    tankTag=BigWorld.entities[BigWorld.player().playerVehicleID].typeDescriptor.name,
    tankType=short_tank_type(get_tank_type(player.vehicleTypeDescriptor.type.tags)),
    tankRole=get_tank_role(player.vehicleTypeDescriptor.role),
    tankLevel=player.vehicleTypeDescriptor.level,
    gunTag=player.vehicleTypeDescriptor.gun.name,
    allyTeamHealth=arenaInfoProvider.allyTeamHealth[0],
    enemyTeamHealth=arenaInfoProvider.enemyTeamHealth[0],
    allyTeamMaxHealth=arenaInfoProvider.allyTeamHealth[1],
    enemyTeamMaxHealth=arenaInfoProvider.enemyTeamHealth[1],
    allyTeamFragsCount=arenaInfoProvider.allyTeamFragsCount,
    enemyTeamFragsCount=arenaInfoProvider.enemyTeamFragsCount,
    mapsBlackList=accountStatsProvider.mapBlackList
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
