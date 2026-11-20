import BigWorld
import adisp
from BWUtil import AsyncReturn
from debug_utils import LOG_CURRENT_EXCEPTION

from gui.shared.personality import ServicesLocator
from gui.ClientUpdateManager import g_clientUpdateManager
from helpers import dependency, isPlayerAccount
from skeletons.gui.app_loader import GuiGlobalSpaceID
from skeletons.gui.shared import IItemsCache
from skeletons.gui.game_control import IComp7Controller
from Event import SafeEvent

try:
  from th_async import th_async as wg_async, await_callback, TimeoutError, BrokenPromiseError
except ImportError:
  from wg_async import wg_async, await_callback, TimeoutError, BrokenPromiseError

try:
  from gui.game_control.comp7_controller import _LeaderboardDataProvider
  from gui.impl.lobby.comp7 import comp7_shared
except ImportError:
  from comp7.gui.game_control.comp7_controller import _LeaderboardDataProvider
  from comp7.gui.impl.lobby.comp7_helpers import comp7_shared

from ..eventLogger import eventLogger
from ..events import OnComp7Info
from ..utils import get_comp7_rank_tag, setup_hangar_event
from ...utils import print_warn
from ...common.exceptionSending import with_exception_sending, send_current_exception

LEADERBOARD_REQUEST_TIMEOUT = 10.0


def get_current_comp7_rank(controller):
  # type: (IComp7Controller) -> str | None

  if controller.qualificationState is None: return None
  if controller.isQualificationActive(): return 'qual'

  division = comp7_shared.getPlayerDivision()
  if division is None: return None

  rank = comp7_shared.getRankEnumValue(division)
  divisionIdx = division.index
  if divisionIdx > 0: divisionIdx = comp7_shared.getDivisionEnumValue(division)
  
  return get_comp7_rank_tag((rank, divisionIdx), False)


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
    self._lastState = None
    self._leaderboardPosition = None
    self._leaderboardLoading = False
    self._updatePending = False
    self._updateCallbackId = None

    self.itemsCache.onSyncCompleted += self.onItemsCacheSyncCompleted
    self.comp7Controller.onRankUpdated += self.onComp7RankUpdated
    self.comp7Controller.onQualificationStateUpdated += self.onComp7RankUpdated
    g_clientUpdateManager.addCallbacks({'cache.entitlements': self.onEntitlementsUpdated})
    ServicesLocator.appLoader.onGUISpaceEntered += self.onGUISpaceEntered
    onOwnDataGet += self.onOwnDataGet

  @with_exception_sending
  def getSeasonName(self):
    try:
      from comp7_common import COMP7_MASKOT_ID, COMP7_CURRENT_SEASON
      return "comp7_{}_{}".format(COMP7_MASKOT_ID, COMP7_CURRENT_SEASON)
    except ImportError:
      from comp7_common_const import COMP7_MASKOT_ID
      season = self.comp7Controller.getActualSeasonNumber(includePreannounced=False)
      if season is None: return None
      return "comp7_{}_{}".format(COMP7_MASKOT_ID, season)

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
  def onGUISpaceEntered(self, spaceID, *a, **k):
    if spaceID != GuiGlobalSpaceID.LOBBY: return
    self.onChanged()

  @with_exception_sending
  def onOwnDataGet(self, result=None):
    # type: (_LeaderboardDataProvider._OwnData) -> None
    if self._leaderboardLoading: return
    if not result or not result.isSuccess: return
    if self._leaderboardPosition == result.position: return
    self.onChanged()

  @wg_async
  def getLeaderboardPosition(self):
    try:
      ownData = yield await_callback(self.comp7Controller.leaderboard.getOwnData(), LEADERBOARD_REQUEST_TIMEOUT)()
      raise AsyncReturn(ownData.position if ownData and ownData.isSuccess else None)
    except TimeoutError:
      print_warn("Timeout while getting ownData")
    except BrokenPromiseError:
      print_warn("Failed to get ownData: request was cancelled")
    raise AsyncReturn(None)

  @with_exception_sending
  def onChanged(self):
    if self._leaderboardLoading:
      self._updatePending = True
      return
    if self._updateCallbackId is None:
      # Rank and qualification are updated sequentially during a cache sync.
      self._updateCallbackId = BigWorld.callback(0, self.update)

  @wg_async
  def update(self):
    self._updateCallbackId = None
    self._leaderboardLoading = True
    self._updatePending = False

    try:
      if not isPlayerAccount() or not self.itemsCache.isSynced(): return
      accountDBID = BigWorld.player().databaseID
      season = self.getSeasonName()
      if season is None: return

      position = yield self.getLeaderboardPosition()
      if not isPlayerAccount() or not self.itemsCache.isSynced(): return
      if accountDBID != BigWorld.player().databaseID or season != self.getSeasonName():
        self._updatePending = True
        return

      rating = self.comp7Controller.rating
      rank = get_current_comp7_rank(self.comp7Controller)
      if rating is None or rank is None: return

      self._leaderboardPosition = position
      state = (accountDBID, season, rating, rank, position)
      if self._lastState != state:
        event = OnComp7Info(*state[1:])
        setup_hangar_event(event)
        eventLogger.emit_event(event)
        self._lastState = state
    except:
      send_current_exception()
      LOG_CURRENT_EXCEPTION()
    finally:
      self._leaderboardLoading = False
      if self._updatePending:
        self.onChanged()


comp7Logger = Comp7Logger()
