import BigWorld
import adisp

from gui.shared.personality import ServicesLocator
from gui.ClientUpdateManager import g_clientUpdateManager
from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.game_control import IComp7Controller

from ..eventLogger import eventLogger
from ..events import OnComp7Info
from ..utils import setup_hangar_event
from ...common.exceptionSending import with_exception_sending

class Comp7Logger:
  
  itemsCache = dependency.descriptor(IItemsCache) # type: IItemsCache
  comp7Controller = dependency.instance(IComp7Controller) # type: IComp7Controller
  
  def __init__(self):
    self._lastEliteTrashload = None
    self._lastRating = None

    self.itemsCache.onSyncCompleted += self.onItemsCacheSyncCompleted
    self.comp7Controller.onRankUpdated += self.onComp7RankUpdated
    g_clientUpdateManager.addCallbacks({'cache.entitlements': self.onEntitlementsUpdated})
    ServicesLocator.appLoader.onGUISpaceEntered += self.onGUISpaceEntered

  @with_exception_sending
  def getSeasonName(self):
    try: 
      from comp7_common import COMP7_MASKOT_ID, COMP7_CURRENT_SEASON
      return "comp7_{}_{}".format(COMP7_MASKOT_ID, COMP7_CURRENT_SEASON)
    except:
      from comp7_common_const import COMP7_MASKOT_ID
      season = self.comp7Controller.getActualSeasonNumber(includePreannounced=False)
      if season is None: return None
      return "comp7_{}_{}".format(COMP7_MASKOT_ID, season)
    
  @with_exception_sending
  def getCurrentRating(self):
    try:
      from comp7_ranks_common import COMP7_RATING_ENTITLEMENT
      return self.itemsCache.items.stats.entitlements.get(COMP7_RATING_ENTITLEMENT, None)
    except:
      from comp7_common_const import ratingEntNameBySeasonNumber
      season = self.comp7Controller.getActualSeasonNumber(includePreannounced=False)
      if season is None: return None
      return self.itemsCache.items.stats.entitlements.get(ratingEntNameBySeasonNumber(str(season)), None)

  @with_exception_sending
  def onComp7RankUpdated(self, *a, **k):
    self.onChanged()

  @with_exception_sending
  def onItemsCacheSyncCompleted(self, *a, **k):
    self.onChanged()

  @with_exception_sending
  def onEntitlementsUpdated(self, *a, **k):
    self.onChanged()

  @with_exception_sending
  def onGUISpaceEntered(self, *a, **k):
    self.onChanged()

  @adisp.adisp_process
  def onChanged(self):
    season = self.getSeasonName()
    if season is None: return

    eliteTrashload, status = yield self.comp7Controller.leaderboard.getLastEliteRating()
    if not status: return

    currentRating = self.getCurrentRating()
    if currentRating is None: return

    if self._lastEliteTrashload == eliteTrashload and self._lastRating == currentRating:
      return
    
    self._lastEliteTrashload = eliteTrashload
    self._lastRating = currentRating

    event = OnComp7Info(season, currentRating, eliteTrashload)
    setup_hangar_event(event)
    eventLogger.emit_event(event)


comp7Logger = Comp7Logger()