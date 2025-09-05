
from operator import le
import BigWorld
import random

from gui.shared.personality import ServicesLocator
from skeletons.gui.app_loader import GuiGlobalSpaceID
from helpers import dependency
from skeletons.gui.shared import IItemsCache

from ..eventLogger import eventLogger
from ..events import OnMoeInfo
from ...common.crossGameUtils import gamePublisher, PUBLISHER
from ..utils import setup_hangar_event
from ...common.exceptionSending import with_exception_sending

class MoeLogger:
  
  itemsCache = dependency.descriptor(IItemsCache) # type: IItemsCache
  
  def __init__(self):
    self.requested = dict()
    self.vehicles = [v for v in self.itemsCache.items.getVehicles().values() if v.level >= 5]
    
    if(gamePublisher() != PUBLISHER.LESTA): return
    
    self.itemsCache.onSyncCompleted += self.onItemsCacheSyncCompleted
    ServicesLocator.appLoader.onGUISpaceEntered += self.onGUISpaceEntered

  @with_exception_sending
  def onItemsCacheSyncCompleted(self, reason, diff):
    self.vehicles = [v for v in self.itemsCache.items.getVehicles().values() if v.level >= 5]
  
    if len(self.vehicles) != 0:
      self.itemsCache.onSyncCompleted -= self.onItemsCacheSyncCompleted

  @with_exception_sending
  def onGUISpaceEntered(self, spaceID):
    from AccountCommands import CMD_GET_VEHICLE_DAMAGE_DISTRIBUTION
    
    if spaceID != GuiGlobalSpaceID.LOBBY: return
    
    playerAccount = BigWorld.player()
    if not playerAccount: return
    
    if len(self.vehicles) == 0: return
    
    randomVehicle = self.vehicles[random.randint(0, len(self.vehicles) - 1)]
    
    requestId = playerAccount._doCmdInt(CMD_GET_VEHICLE_DAMAGE_DISTRIBUTION, randomVehicle.intCD, self.onDamageDistributionReceived)
    self.requested[requestId] = randomVehicle.name

  @with_exception_sending
  def onDamageDistributionReceived(self, requestID, responseID, errorStr, ext=None):
    
    vehicleName = self.requested.pop(requestID, None)

    if not vehicleName: return
    if not ext: return

    event = OnMoeInfo(vehicleName, ext.get('battleCount', 0), ext.get('damageBetterThanNPercent', []))
    setup_hangar_event(event)
    eventLogger.emit_event(event)

moeLogger = MoeLogger()