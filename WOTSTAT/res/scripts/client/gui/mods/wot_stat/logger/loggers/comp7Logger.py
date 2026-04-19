import BigWorld
import adisp

from gui.shared.personality import ServicesLocator
from gui.ClientUpdateManager import g_clientUpdateManager
from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.game_control import IComp7Controller
from Event import SafeEvent

try:
  from gui.game_control.comp7_controller import _LeaderboardDataProvider
except ImportError:
  from comp7.gui.game_control.comp7_controller import _LeaderboardDataProvider

from ..eventLogger import eventLogger
from ..events import OnComp7Info
from ..utils import setup_hangar_event
from ...common.exceptionSending import with_exception_sending

onOwnDataGet = SafeEvent()
getOwnData_old = _LeaderboardDataProvider.getOwnData

@adisp.adisp_async
@adisp.adisp_process
def getOwnData(self, callback):
  result = yield getOwnData_old(self)
  onOwnDataGet(result)
  callback(result)

_LeaderboardDataProvider.getOwnData = getOwnData

class Comp7Logger:
  
  itemsCache = dependency.descriptor(IItemsCache) # type: IItemsCache
  comp7Controller = dependency.descriptor(IComp7Controller) # type: IComp7Controller
  
  def __init__(self):
    global onOwnDataGet
    self._lastEliteTrashload = None
    self._lastRating = None
    self._leaderboardPosition = None
    self._leaderboardLoading = False

    self.itemsCache.onSyncCompleted += self.onItemsCacheSyncCompleted
    self.comp7Controller.onRankUpdated += self.onComp7RankUpdated
    g_clientUpdateManager.addCallbacks({'cache.entitlements': self.onEntitlementsUpdated})
    ServicesLocator.appLoader.onGUISpaceEntered += self.onGUISpaceEntered
    onOwnDataGet += self.onOwnDataGet

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

  @with_exception_sending
  def onOwnDataGet(self, result=None):
    # type: (_LeaderboardDataProvider._OwnData) -> None
    if self._leaderboardLoading: return
    if not result: return
    if self._leaderboardPosition == result.position: return

    BigWorld.callback(0, self.onChanged)

  @adisp.adisp_process
  def onChanged(self):
    season = self.getSeasonName()
    if season is None: return

    leaderboard = self.comp7Controller.leaderboard # type: _LeaderboardDataProvider

    self._leaderboardLoading = True
    eliteTrashload, status = yield leaderboard.getLastEliteRating()
    self._leaderboardLoading = False
    if not status: return

    self._leaderboardLoading = True
    ownData = yield leaderboard.getOwnData() # type: _LeaderboardDataProvider._OwnData
    self._leaderboardLoading = False
    if ownData is None: return
    leaderboardPosition = ownData.position if ownData.isSuccess else None

    currentRating = self.getCurrentRating()
    if currentRating is None: return

    if self._lastEliteTrashload == eliteTrashload and self._lastRating == currentRating and self._leaderboardPosition == leaderboardPosition:
      return
    
    self._lastEliteTrashload = eliteTrashload
    self._lastRating = currentRating
    self._leaderboardPosition = leaderboardPosition

    event = OnComp7Info(season, currentRating, eliteTrashload, leaderboardPosition)
    setup_hangar_event(event)
    eventLogger.emit_event(event)


comp7Logger = Comp7Logger()
