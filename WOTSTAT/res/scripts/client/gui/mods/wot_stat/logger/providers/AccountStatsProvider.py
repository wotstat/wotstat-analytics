import ArenaType

from helpers import dependency
from skeletons.gui.shared import IItemsCache

from ...common.exceptionSending import with_exception_sending
from ...utils import print_error

class AccountStatsProvider():
  
  itemsCache = dependency.descriptor(IItemsCache) # type: IItemsCache

  def __init__(self):
    self.mapBlackList = []
    self.itemsCache.onSyncCompleted += self.onSyncCompleted
    
  @with_exception_sending
  def onSyncCompleted(self, *a, **k):
    if not self.itemsCache.isSynced(): return
    maps = self.itemsCache.items.stats.getMapsBlackList()

    if maps is None:
      self.mapBlackList = []
      return
    
    if isinstance(maps, list):
      mapsBlackListId = [ mapId for mapId, _ in maps ]
    elif isinstance(maps, dict):
      mapsBlackListId = [ mapID for _, _, mapID, _, _ in maps.values() ]
    else:
      print_error("Invalid type for mapBlackList")
      self.mapBlackList = []

    self.mapBlackList = [ ArenaType.g_geometryCache[mapId].geometryName if mapId in ArenaType.g_geometryCache else None for mapId in mapsBlackListId ]