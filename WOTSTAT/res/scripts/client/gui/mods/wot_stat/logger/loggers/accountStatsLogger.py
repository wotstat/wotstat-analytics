import BigWorld
import json

from gui.ClientUpdateManager import g_clientUpdateManager
from PlayerEvents import g_playerEvents
from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.lobby_context import ILobbyContext
from skeletons.gui.game_control import IWotPlusController, IGameSessionController
from datetime import datetime

from ..eventLogger import eventLogger
from ..events import OnAccountStats
from ..utils import setup_hangar_event
from ...common.exceptionSending import with_exception_sending
from constants import PREMIUM_TYPE


import typing
if typing.TYPE_CHECKING:
  from gui.shared.money import Money

class AccountStatsLogger:
  
  itemsCache = dependency.descriptor(IItemsCache) # type: IItemsCache
  lobbyContext = dependency.descriptor(ILobbyContext) # type: ILobbyContext
  wotPlusController = dependency.instance(IWotPlusController) # type: IWotPlusController
  gameSession = dependency.descriptor(IGameSessionController) # type: IGameSessionController


  def __init__(self):
    self.credits = 0
    self.gold = 0
    self.crystal = 0
    self.equipCoin = 0
    self.bpCoin = 0
    self.eventCoin = 0
    self.freeXP = 0
    self.piggyBankCredits = 0
    self.piggyBankGold = 0

    self.isPremiumPlus = False
    self.premiumPlusExpiryTime = None

    self.isWotPlus = False
    self.wotPlusExpiryTime = None

    self.telecom = ''

    self.lastData = None
    self.callbackId = None

    self.gameSession.onPremiumNotify += self.onChanged
    self.gameSession.onPremiumTypeChanged += self.onChanged
    self.itemsCache.onSyncCompleted += self.onChanged
    self.wotPlusController.onDataChanged += self.onChanged
    self.lobbyContext.getServerSettings().onServerSettingsChange += self.onChanged
    g_clientUpdateManager.addMoneyCallback(self.onChanged)
    g_playerEvents.onClientUpdated += self.onChanged

    try: self.wotPlusController.onStateUpdate += self.onChanged
    except Exception: pass

  def onChanged(self, *a, **k):
    if self.callbackId is not None:
      BigWorld.cancelCallback(self.callbackId)
      self.callbackId = None

    def call():
      self.callbackId = None
      self.update()
    
    self.callbackId = BigWorld.callback(0, call)

  @with_exception_sending
  def update(self, *a, **k):
    if not self.itemsCache.isSynced(): return
    self.updateMoney()
    self.updateXP()
    self.updatePremium()
    self.updateWotPlus()
    self.updateTelekom()
    self.send()

  def updateMoney(self):
    money = self.itemsCache.items.stats.actualMoney # type: Money
    self.credits = money.credits
    self.gold = money.gold
    self.crystal = money.crystal
    self.equipCoin = money.equipCoin
    self.bpCoin = money.bpcoin
    self.eventCoin = money.eventCoin

    self.piggyBankCredits = self.itemsCache.items.stats.piggyBank.get('credits', 0)
    self.piggyBankGold = self.itemsCache.items.stats.piggyBank.get('gold', 0)

  def updateXP(self):
    self.freeXP = self.itemsCache.items.stats.actualFreeXP

  def updatePremium(self):
    premiumInfo = self.itemsCache.items.stats.premiumInfo
    premiumPlus = premiumInfo.get(PREMIUM_TYPE.PLUS, {})

    self.isPremiumPlus = premiumPlus.get('active', False)
    time = premiumPlus.get('expiryTime', 0)
    self.premiumPlusExpiryTime = datetime.utcfromtimestamp(time).isoformat() if self.isPremiumPlus else None

  def updateWotPlus(self):
    self.isWotPlus = self.wotPlusController.isEnabled()
    time = self.wotPlusController.getExpiryTime()
    self.wotPlusExpiryTime = datetime.utcfromtimestamp(time).isoformat() if self.isWotPlus else None

  def updateTelekom(self):
    serverSettings = self.lobbyContext.getServerSettings()
    telecomId = self.itemsCache.items.stats.getTelecomBundleId()
    if telecomId is None:
      self.telecom = ''
    else:
      self.telecom = serverSettings.telecomConfig.getInternetProvider(telecomId)

  def isAllZero(self):
    return (self.credits == 0 and self.gold == 0 and self.crystal == 0 and
            self.equipCoin == 0 and self.bpCoin == 0 and self.eventCoin == 0 and
            self.freeXP == 0 and self.piggyBankCredits == 0 and self.piggyBankGold == 0 and
            self.premiumPlusExpiryTime is None and self.wotPlusExpiryTime is None and
            not self.isPremiumPlus and not self.isWotPlus and
            self.telecom == '')

  def send(self):
    if self.isAllZero():
      return
    
    data = {
      'credits': self.credits,
      'gold': self.gold,
      'crystal': self.crystal,
      'equipCoin': self.equipCoin,
      'bpCoin': self.bpCoin,
      'eventCoin': self.eventCoin,
      'freeXP': self.freeXP,
      'premiumPlusExpiryTime': self.premiumPlusExpiryTime,
      'isPremiumPlus': self.isPremiumPlus,
      'isWotPlus': self.isWotPlus,
      'wotPlusExpiryTime': self.wotPlusExpiryTime,
      'telecom': self.telecom,
      'piggyBankCredits': self.piggyBankCredits,
      'piggyBankGold': self.piggyBankGold
    }

    dataSrt = json.dumps(data)

    if dataSrt == self.lastData: return
    self.lastData = dataSrt

    event = OnAccountStats(
      self.credits, self.gold, self.crystal, self.equipCoin, self.bpCoin, self.eventCoin, self.freeXP,
      self.piggyBankCredits, self.piggyBankGold,
      self.premiumPlusExpiryTime, self.isPremiumPlus, self.isWotPlus, self.wotPlusExpiryTime, self.telecom,
    )
    setup_hangar_event(event)
    eventLogger.emit_event(event)


accountStatsLogger = AccountStatsLogger()