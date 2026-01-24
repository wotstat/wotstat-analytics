import ArenaType

from helpers import dependency
from skeletons.gui.shared import IItemsCache

from ...common.exceptionSending import with_exception_sending

class AccountStatsProvider():
  
  itemsCache = dependency.descriptor(IItemsCache) # type: IItemsCache

  def __init__(self):
    self.mapBlackList = []
    self.itemsCache.onSyncCompleted += self.onSyncCompleted
    
  @with_exception_sending
  def onSyncCompleted(self, *a, **k):
    if not self.itemsCache.isSynced(): return
    mapsBlackListId = [ mapId for mapId, _ in self.itemsCache.items.stats.getMapsBlackList() ]
    self.mapBlackList = [ ArenaType.g_geometryCache[mapId].geometryName if mapId in ArenaType.g_geometryCache else None for mapId in mapsBlackListId ]