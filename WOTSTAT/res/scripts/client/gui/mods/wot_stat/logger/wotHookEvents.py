from Account import Account
from Avatar import PlayerAvatar
from ProjectileMover import ProjectileMover
from Vehicle import Vehicle
from VehicleGunRotator import VehicleGunRotator
from helpers import dependency
from skeletons.connection_mgr import IConnectionManager
from skeletons.gui.shared.utils import IHangarSpace
from gui.shared.gui_items.processors.loot_boxes import LootBoxOpenProcessor
from ..common.exceptionSending import SendExceptionEvent
from ..common.hook import g_overrideLib
from ..utils import print_warn


class WotHookEvents:
  __connectionMgr = dependency.descriptor(IConnectionManager)
  __hangarSpace = dependency.descriptor(IHangarSpace)

  def __init__(self):
    # DI
    self.__connectionMgr.onConnected += self.__onConnected
    self.__connectionMgr.onLoggedOn += self.__onLoggedOn
    self.__hangarSpace.onSpaceCreate += self.__onHangarSpaceCreate

    self.listeners = {}
    # ------------------INIT------------------#
    self.onConnected = SendExceptionEvent()
    self.onLoggedOn = SendExceptionEvent()
    self.onHangarLoaded = SendExceptionEvent()
    self.Account_onBecomePlayer = SendExceptionEvent()
    self.Account_onBecomeNonPlayer = SendExceptionEvent()
    self.BattleQueue_populate = SendExceptionEvent()
    self.PlayerAvatar_onEnterWorld = SendExceptionEvent()
    self.PlayerAvatar_onBecomeNonPlayer = SendExceptionEvent()
    self.PlayerAvatar_updateTargetingInfo = SendExceptionEvent()
    self.PlayerAvatar_onArenaPeriodChange = SendExceptionEvent()
    self.VehicleGunRotator_start = SendExceptionEvent()
    self.Vehicle_onEnterWorld = SendExceptionEvent()
    # -------------------MOVE------------------#
    self.VehicleGunRotator_updateGunMarker = SendExceptionEvent()
    self.PlayerAvatar_updateGunMarker = SendExceptionEvent()
    # -------------------SHOT------------------#
    self.PlayerAvatar_shoot = SendExceptionEvent()
    self.PlayerAvatar_showTracer = SendExceptionEvent()
    self.PlayerAvatar_showShotResults = SendExceptionEvent()
    self.Vehicle_onHealthChanged = SendExceptionEvent()
    self.PlayerAvatar_showOwnVehicleHitDirection = SendExceptionEvent()
    # -------------------EXPLOSION------------------#
    self.PlayerAvatar_explodeProjectile = SendExceptionEvent()
    self.Vehicle_showDamageFromShot = SendExceptionEvent()
    # -------------------PROJECTILE-------------------#
    self.ProjectileMover_killProjectile = SendExceptionEvent()
    # -------------------HELP-------------------#
    self.PlayerAvatar_enableServerAim = SendExceptionEvent()
    self.LootBoxOpenProcessorOpenRequest = SendExceptionEvent()
    self.LootBoxOpenProcessorOpenResponse = SendExceptionEvent()
    self.LootBoxSystemOpenProcessorResponse = SendExceptionEvent()
    self.WTLootBoxRollResponse = SendExceptionEvent()
    self.WTLootBoxRerollResponse = SendExceptionEvent()
    self.WTLootBoxHistoryResponse = SendExceptionEvent()
    self.WTLootBoxClaimRequest = SendExceptionEvent()
    self.WTLootBoxClaimResponse = SendExceptionEvent()
    self.WTTankLootBoxOpened = SendExceptionEvent()

  def __onConnected(self):
    self.onConnected()

  def __onLoggedOn(self, data):
    self.onLoggedOn(data)

  def __onHangarSpaceCreate(self):
    self.onHangarLoaded()


wotHookEvents = WotHookEvents()


# ------------------INIT------------------#


@g_overrideLib.registerEvent(Vehicle, 'onEnterWorld')
def onEnterWorld(self, *a, **k):
  wotHookEvents.Vehicle_onEnterWorld(self, *a, **k)


@g_overrideLib.registerEvent(Account, 'onBecomePlayer')
def onBecomePlayer(self, *a, **k):
  wotHookEvents.Account_onBecomePlayer(self, *a, **k)


@g_overrideLib.registerEvent(Account, 'onBecomeNonPlayer')
def onBecomeNonPlayer(self, *a, **k):
  wotHookEvents.Account_onBecomeNonPlayer(self, *a, **k)


@g_overrideLib.registerEvent(VehicleGunRotator, 'start')
def vehicleGunRotator_start(self, *a, **k):
  wotHookEvents.VehicleGunRotator_start(self, *a, **k)


try:
  from gui.Scaleform.daapi.view.lobby.battle_queue import BattleQueue
  @g_overrideLib.registerEvent(BattleQueue, '_populate')
  def queuePopulate(self, *a, **k): wotHookEvents.BattleQueue_populate(self, *a, **k)
except:
  from gui.Scaleform.daapi.view.lobby.battle_queue.battle_queue import BattleQueue
  @g_overrideLib.registerEvent(BattleQueue, '_populate')
  def queuePopulate(self, *a, **k): wotHookEvents.BattleQueue_populate(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, 'onEnterWorld')
def onEnterWorld(self, *a, **k):
  wotHookEvents.PlayerAvatar_onEnterWorld(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, 'onBecomeNonPlayer', prepend=True)
def avatarBecomeNonPlayer(self, *a, **k):
  wotHookEvents.PlayerAvatar_onBecomeNonPlayer(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, 'updateTargetingInfo')
def updateTargetingInfo(self, *a, **k):
  wotHookEvents.PlayerAvatar_updateTargetingInfo(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, '_PlayerAvatar__onArenaPeriodChange')
def onArenaPeriodChange(self, *a, **k):
  wotHookEvents.PlayerAvatar_onArenaPeriodChange(self, *a, **k)


# -------------------MOVE------------------#

@g_overrideLib.registerEvent(VehicleGunRotator, '_VehicleGunRotator__updateGunMarker')
def updateGunMarker(self, *a, **k):
  wotHookEvents.VehicleGunRotator_updateGunMarker(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, 'updateGunMarker')
def PlayerAvatar_updateGunMarker(self, *a, **k):
  wotHookEvents.PlayerAvatar_updateGunMarker(self, *a, **k)


# -------------------SHOT------------------#

@g_overrideLib.registerEvent(PlayerAvatar, 'shoot', prepend=True)
def shoot(self, *a, **k):
  wotHookEvents.PlayerAvatar_shoot(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, 'showTracer')
def showTracer(self, *a, **k):
  wotHookEvents.PlayerAvatar_showTracer(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, 'showShotResults')
def showShotResults(self, *a, **k):
  wotHookEvents.PlayerAvatar_showShotResults(self, *a, **k)


@g_overrideLib.registerEvent(Vehicle, 'onHealthChanged')
def onHealthChanged(self, *a, **k):
  wotHookEvents.Vehicle_onHealthChanged(self, *a, **k)


@g_overrideLib.registerEvent(PlayerAvatar, 'showOwnVehicleHitDirection')
def showOwnVehicleHitDirection(self, *a, **k):
  wotHookEvents.PlayerAvatar_showOwnVehicleHitDirection(self, *a, **k)


# -------------------EXPLOSION------------------#

@g_overrideLib.registerEvent(PlayerAvatar, 'explodeProjectile')
def explodeProjectile(self, *a, **k):
  wotHookEvents.PlayerAvatar_explodeProjectile(self, *a, **k)


@g_overrideLib.registerEvent(Vehicle, 'showDamageFromShot')
def showDamageFromShot(self, *a, **k):
  wotHookEvents.Vehicle_showDamageFromShot(self, *a, **k)


# -------------------PROJECTILE-------------------#

@g_overrideLib.registerEvent(ProjectileMover, '_ProjectileMover__killProjectile')
def killProjectile(self, *a, **k):
  wotHookEvents.ProjectileMover_killProjectile(self, *a, **k)


# -------------------HELP-------------------#

@g_overrideLib.registerEvent(PlayerAvatar, 'enableServerAim')
def enableServerAim(self, *a, **k):
  wotHookEvents.PlayerAvatar_enableServerAim(self, *a, **k)


try:
  from gui.shared.gui_items.processors.loot_boxes import LootBoxSystemOpenProcessor
  @g_overrideLib.registerEvent(LootBoxSystemOpenProcessor, '_successHandler')
  def LootBoxSystemOpenProcessorResponse(self, *a, **k):
    wotHookEvents.LootBoxSystemOpenProcessorResponse(self, *a, **k)
except ImportError: pass
except Exception as e:
  print_warn('LootBoxSystemOpenProcessor hook skipped: %s' % e)


@g_overrideLib.registerEvent(LootBoxOpenProcessor, '_request')
def LootBoxOpenProcessorOpenRequest(self, *a, **k):
  wotHookEvents.LootBoxOpenProcessorOpenRequest(self, *a, **k)


@g_overrideLib.registerEvent(LootBoxOpenProcessor, '_successHandler')
def LootBoxOpenProcessorOpenResponse(self, *a, **k):
  wotHookEvents.LootBoxOpenProcessorOpenResponse(self, *a, **k)

try:
  from white_tiger.gui.game_control import loot_boxes_controller as wt_loot_boxes

  @g_overrideLib.registerEvent(wt_loot_boxes._WTLootBoxRollProcessor, '_successHandler')
  def WTLootBoxRollResponse(self, *a, **k):
    wotHookEvents.WTLootBoxRollResponse(self, *a, **k)

  @g_overrideLib.registerEvent(wt_loot_boxes._WtLootBoxClaimProcessor, '_request')
  def WTLootBoxClaimRequest(self, *a, **k):
    wotHookEvents.WTLootBoxClaimRequest(self, *a, **k)

  @g_overrideLib.registerEvent(wt_loot_boxes._WtLootBoxClaimProcessor, '_successHandler')
  def WTLootBoxClaimResponse(self, *a, **k):
    wotHookEvents.WTLootBoxClaimResponse(self, *a, **k)

  @g_overrideLib.registerEvent(wt_loot_boxes._WTLootBoxRerollProcessor, '_successHandler')
  def WTLootBoxRerollResponse(self, *a, **k):
    wotHookEvents.WTLootBoxRerollResponse(self, *a, **k)

  @g_overrideLib.registerEvent(wt_loot_boxes._WtLootBoxReRollHistoryProcessor, '_successHandler')
  def WTLootBoxHistoryResponse(self, *a, **k):
    wotHookEvents.WTLootBoxHistoryResponse(self, *a, **k)
except ImportError: pass
except Exception as e:
  print_warn('White Tiger loot box hook registration stopped: %s' % e)


try:
  from AccountWhiteTigerComponent import AccountWhiteTigerComponent
  @g_overrideLib.overrideMethod(AccountWhiteTigerComponent, 'openTankLootBox')
  def WTTankLootBoxOpened(original, self, callback=None):
    if callback is None:
      return original(self, callback)

    def onResponse(*a, **k):
      result = callback(*a, **k)
      wotHookEvents.WTTankLootBoxOpened(*a, **k)
      return result

    return original(self, onResponse)
except ImportError: pass
except Exception as e:
  print_warn('White Tiger tank loot box hook skipped: %s' % e)
