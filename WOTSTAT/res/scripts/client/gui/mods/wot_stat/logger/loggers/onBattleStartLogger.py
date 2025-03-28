import BattleReplay
import BigWorld
from account_helpers import gameplay_ctx
from constants import ARENA_PERIOD, ARENA_BONUS_TYPE, ARENA_PERIOD_NAMES
from ..eventLogger import eventLogger, battle_time
from ..events import OnBattleStart
from ..sessionStorage import sessionStorage
from ..utils import vector, setup_dynamic_battle_info, setup_session_meta
from ..wotHookEvents import wotHookEvents
from ...utils import print_debug


AWAIT_BATTLE_PERIOD_BEFORE_START = [ARENA_BONUS_TYPE.COMP7]

class OnBattleStartLogger:
  def __init__(self):
    self.battle_loaded = False
    self.is_queue_visible = False
    self.is_battle_initialized = False

    self.on_enter_queue_time = 0  # Вход в очередь
    self.on_enter_world_time = 0  # Вход в бой
    self.on_end_load_time = 0  # Завершение загрузки
    self.shot_disp_multiplier_factor = 0

    wotHookEvents.PlayerAvatar_onEnterWorld += self.on_enter_world
    wotHookEvents.PlayerAvatar_updateTargetingInfo += self.update_targeting_info
    wotHookEvents.PlayerAvatar_onArenaPeriodChange += self.on_arena_period_change
    wotHookEvents.BattleQueue_populate += self.on_enqueued

  def on_enqueued(self, obj, *a, **k):
    print_debug('OnBattleStartLogger.on_enqueued')

    self.is_queue_visible = True
    self.battle_loaded = False
    self.on_enter_queue_time = BigWorld.serverTime()

  def on_enter_world(self, obj, *a, **k):
    print_debug('OnBattleStartLogger.on_enter_world')

    self.battle_loaded = False
    self.is_battle_initialized = False
    if not self.is_queue_visible:
      self.on_enter_queue_time = BigWorld.serverTime()
    self.on_enter_world_time = BigWorld.serverTime()

  def update_targeting_info(self, obj, turretYaw, gunPitch, maxTurretRotationSpeed, maxGunRotationSpeed,
                            shot_disp_multiplier_factor, *a, **k):
    if BattleReplay.isPlaying():
      return
    if not hasattr(BigWorld.player(), 'arena') or not BigWorld.player().getOwnVehiclePosition():
      return

    print_debug("______OnEndLoad______")
    BigWorld.player().enableServerAim(True)

    if self.battle_loaded:
      return

    self.battle_loaded = True
    self.on_end_load_time = BigWorld.serverTime()
    self.shot_disp_multiplier_factor = shot_disp_multiplier_factor

    arena = BigWorld.player().arena
    
    if arena.period in [ARENA_PERIOD.PREBATTLE, ARENA_PERIOD.BATTLE] and arena.bonusType not in AWAIT_BATTLE_PERIOD_BEFORE_START:
      self.init_battle_session()
    elif arena.period == ARENA_PERIOD.BATTLE and arena.bonusType in AWAIT_BATTLE_PERIOD_BEFORE_START:
      self.init_battle_session()

  def on_arena_period_change(self, obj, period, periodEndTime, periodLength, periodAdditionalInfo, *a, **k):
    arena = BigWorld.player().arena
    
    if period is ARENA_PERIOD.PREBATTLE and arena.bonusType not in AWAIT_BATTLE_PERIOD_BEFORE_START:
      self.init_battle_session()
      
    if period is ARENA_PERIOD.BATTLE and arena.bonusType in AWAIT_BATTLE_PERIOD_BEFORE_START:
      self.init_battle_session()

    if period is ARENA_PERIOD.BATTLE:
      eventLogger.start_battle_time = periodEndTime - periodLength
      
  def init_battle_session(self):
    if not self.battle_loaded:
      return
    if self.is_battle_initialized:
      return

    print_debug("______INIT______")
    self.is_battle_initialized = True

    player = BigWorld.player()

    eventLogger.start_battle_time = player.arena.periodEndTime \
      if player.arena.period is ARENA_PERIOD.PREBATTLE \
      else player.arena.periodEndTime - player.arena.periodLength

    player.enableServerAim(True)

    prebattle_time = max(0, eventLogger.start_battle_time - self.on_end_load_time)
    loading_time = self.on_end_load_time - self.on_enter_world_time
    queueing_time = self.on_enter_world_time - self.on_enter_queue_time

    print_debug("Timings:\n\tqueueing_time: %s\n\tloading_time: %s\n\tprebattle_time: %s\n" % (
      queueing_time, loading_time, prebattle_time))

    onBattleStart = OnBattleStart(arenaId=player.arenaUniqueID,
                                  spawnPoint=vector(player.getOwnVehiclePosition()),
                                  battlePeriod=ARENA_PERIOD_NAMES[player.arena.period],
                                  battleTime=battle_time(),
                                  loadTime=loading_time,
                                  preBattleWaitTime=prebattle_time,
                                  inQueueWaitTime=queueing_time,
                                  gameplayMask=gameplay_ctx.getMask()
                                  )

    setup_dynamic_battle_info(onBattleStart)
    setup_session_meta(onBattleStart)

    eventLogger.emit_event(onBattleStart)
    sessionStorage.on_start_battle()

    self.on_enter_queue_time = 0
    self.on_enter_world_time = 0
    self.on_end_load_time = 0
    self.is_queue_visible = False


onBattleStartLogger = OnBattleStartLogger()
