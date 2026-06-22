import BigWorld
import adisp
from BWUtil import AsyncReturn
from debug_utils import LOG_CURRENT_EXCEPTION

from gui.shared.personality import ServicesLocator
from gui.ClientUpdateManager import g_clientUpdateManager
from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.game_control import IComp7Controller
from Event import SafeEvent

try:
  from th_async import th_async as wg_async, await_callback, TimeoutError, BrokenPromiseError
except ImportError:
  from wg_async import wg_async, await_callback, TimeoutError, BrokenPromiseError

try:
  from gui.game_control.comp7_controller import _LeaderboardDataProvider
except ImportError:
  from comp7.gui.game_control.comp7_controller import _LeaderboardDataProvider

from ..eventLogger import eventLogger
from ..events import OnComp7Info
from ..utils import setup_hangar_event
from ...utils import print_warn
from ...common.exceptionSending import with_exception_sending, send_current_exception

LEADERBOARD_REQUEST_TIMEOUT = 10.0

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
  
  @wg_async
  def updateLeaderboard(self):
    leaderboard = self.comp7Controller.leaderboard # type: _LeaderboardDataProvider

    eliteTrashload = None
    leaderboardPosition = None

    self._leaderboardLoading = True
    try:
      try:
        eliteTrashload, status = yield await_callback(leaderboard.getLastEliteRating(), LEADERBOARD_REQUEST_TIMEOUT)()
        if not status: eliteTrashload = None

      except TimeoutError:
        print_warn("Timeout while getting leaderboard")
        eliteTrashload = None

      except BrokenPromiseError:
        print_warn("Failed to get leaderboard: request was cancelled")
        eliteTrashload = None

      try:
        ownData = yield await_callback(leaderboard.getOwnData(), LEADERBOARD_REQUEST_TIMEOUT)() # type: _LeaderboardDataProvider._OwnData
        leaderboardPosition = ownData.position if ownData and ownData.isSuccess else None

      except TimeoutError: print_warn("Timeout while getting ownData")
      except BrokenPromiseError: print_warn("Failed to get ownData: request was cancelled")

    finally:
      self._leaderboardLoading = False
      
    if self._lastEliteTrashload == eliteTrashload and self._leaderboardPosition == leaderboardPosition:
      raise AsyncReturn(False)

    self._lastEliteTrashload = eliteTrashload
    self._leaderboardPosition = leaderboardPosition

    raise AsyncReturn(True)

  @with_exception_sending
  def updateRating(self):
    currentRating = self.getCurrentRating()
    if self._lastRating == currentRating: return False
    self._lastRating = currentRating
    return True

  @wg_async
  def onChanged(self):
    if self._leaderboardLoading: return
    self._leaderboardLoading = True

    try:
      season = self.getSeasonName()
      if season is None: return

      leaderboardChanged = yield self.updateLeaderboard()
      ratingChanged = self.updateRating()

      if not leaderboardChanged and not ratingChanged: return
      if not self._lastEliteTrashload and not self._lastRating and not self._leaderboardPosition: return
      if self._lastRating is None: return
      if not BigWorld.player(): return
  
      event = OnComp7Info(season, self._lastRating, self._lastEliteTrashload, self._leaderboardPosition)
      setup_hangar_event(event)
      eventLogger.emit_event(event)
    except:
      send_current_exception()
      LOG_CURRENT_EXCEPTION()
    finally:
      self._leaderboardLoading = False


comp7Logger = Comp7Logger()
