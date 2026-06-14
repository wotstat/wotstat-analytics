import BigWorld

from battleEventSession import BattleEventSession, HangarEventSession
from constants import ARENA_PERIOD
from events import Event
from wotHookEvents import wotHookEvents
from ..common.exceptionSending import SendExceptionEvent
from ..utils import print_debug
from ..load_mod import config

from ..thirdParty.dataProviderExtension import triggerEvent

class EventLogger:
  old_battle_event_sessions = {}
  battle_event_session = None  # type: BattleEventSession
  start_battle_time = 0
  on_session_created = SendExceptionEvent()
  on_battle_started = SendExceptionEvent()
  hangar_event_session = HangarEventSession(config.get('eventURL'))

  def __init__(self):
    print_debug('INIT EVENT LOGGER')
    self.battle_started_arena_ids = dict()
    wotHookEvents.PlayerAvatar_onArenaPeriodChange += self.on_arena_period_change

  def on_arena_period_change(self, obj, period, periodEndTime, periodLength, *a, **k):
    if period is not ARENA_PERIOD.BATTLE: return

    self.start_battle_time = periodEndTime - periodLength
    self.notify_battle_started(getattr(obj, 'arenaUniqueID', None))

  def notify_current_battle_started(self):
    player = BigWorld.player()
    if not hasattr(player, 'arena') or player.arena is None:
      return

    if player.arena.period is not ARENA_PERIOD.BATTLE:
      return

    if not self.start_battle_time:
      self.start_battle_time = player.arena.periodEndTime - player.arena.periodLength

    self.notify_battle_started(getattr(player, 'arenaUniqueID', None))

  def notify_battle_started(self, arenaID):
    if arenaID is None:
      return

    if self.battle_event_session is None or self.battle_event_session.arenaID != arenaID:
      return

    if arenaID in self.battle_started_arena_ids:
      return

    self.battle_started_arena_ids[arenaID] = True
    BigWorld.callback(0, lambda: self.on_battle_started(self.battle_event_session, arenaID))

  def emit_event(self, event, arena_id=None):
    if event.eventName == Event.NAMES.ON_BATTLE_START:
      if self.battle_event_session:
        self.old_battle_event_sessions[self.battle_event_session.arenaID] = self.battle_event_session
      self.battle_event_session = BattleEventSession(config.get('eventURL'), config.get('initBattleURL'), event)
      self.on_session_created(self.battle_event_session)
      self.notify_current_battle_started()

    elif event.eventName == Event.NAMES.ON_BATTLE_RESULT:
      event_session = None
      if self.battle_event_session.arenaID == arena_id:
        event_session = self.battle_event_session
      if arena_id in self.old_battle_event_sessions:
        event_session = self.old_battle_event_sessions.pop(arena_id)

      if event_session:
        event_session.end_event_session(event)

    elif event.eventName in Event.NAMES.HANGAR_EVENTS:
      self.hangar_event_session.add_event(event)

    else:
      if self.battle_event_session:
        self.battle_event_session.add_event(event)

    triggerEvent(event.get_dict())

eventLogger = EventLogger()


def battle_time():
  player = BigWorld.player()

  if not hasattr(player, 'arena'):
    return -10003

  return {
    ARENA_PERIOD.IDLE: -10001,
    ARENA_PERIOD.WAITING: -10000,
    ARENA_PERIOD.PREBATTLE: BigWorld.serverTime() - player.arena.periodEndTime,
    ARENA_PERIOD.BATTLE: BigWorld.serverTime() - eventLogger.start_battle_time,
    ARENA_PERIOD.AFTERBATTLE: BigWorld.serverTime() - eventLogger.start_battle_time
  }.get(player.arena.period, -10002)
