import BigWorld

from constants import ARENA_BONUS_TYPE
from helpers import dependency
from PlayerEvents import g_playerEvents

from .IExtraProvider import IExtraProvider
from ...common.exceptionSending import with_exception_sending

from skeletons.gui.game_control import IBobController
from skeletons.gui.battle_session import IBattleSessionProvider
from gui.bob.bob_helpers import getShortSkillName
from gui.battle_control.controllers.bob_ctrl import BattleBobController
from skeletons.gui.shared import IItemsCache

class BobProvider(IExtraProvider):
  sessionProvider = dependency.descriptor(IBattleSessionProvider) # type: IBattleSessionProvider
  bobCtrl = dependency.descriptor(IBobController) # type: IBobController
  itemsCache = dependency.descriptor(IItemsCache) # type: IItemsCache
   
  def __init__(self):
    self.sessionProvider.onBattleSessionStart += self.onBattleSessionStart
    self.sessionProvider.onBattleSessionStop += self.onBattleSessionStop
    self.bobCtrl.onUpdated += self.onUpdated
    self.bobCtrl.onTokensUpdated += self.onUpdated
    g_playerEvents.onClientUpdated += self.onUpdated
    
    self.allySkill = None
    self.enemySkill = None
    self.allyBloggerId = 0
    self.enemyBloggerId = 0
    self.personalLevel = 0
    self.stats = {}
    self.isInited = False
    
    self.onUpdated()
    
  @with_exception_sending
  def onBattleSessionStart(self):
    self.isInited = False
    
    self.updateStats()
    
    dynamicBob = self.sessionProvider.dynamic.bob # type: BattleBobController
    if not dynamicBob: return
    
    if BigWorld.player().arenaBonusType != ARENA_BONUS_TYPE.BOB: return
    
    self.isInited = True
    
    if dynamicBob.isInited(): self.onUpdated()
    dynamicBob.onInited += self.onUpdated
    dynamicBob.onSkillUpdated += self.onUpdated
    
  @with_exception_sending
  def onBattleSessionStop(self):
    if not self.isInited: return
    
    self.isInited = False
    dynamicBob = self.sessionProvider.dynamic.bob # type: BattleBobController
    if not dynamicBob: return
    
    dynamicBob.onSkillUpdated -= self.onUpdated
    dynamicBob.onInited -= self.onUpdated
    
    BigWorld.callback(1, self.onUpdated)
    
  @with_exception_sending
  def onUpdated(self, *a, **kw):
    dynamicBob = self.sessionProvider.dynamic.bob # type: BattleBobController
    if dynamicBob:
      self.allySkill = getShortSkillName(dynamicBob.getAllySkill()) if dynamicBob.getAllySkill() else 'default'
      self.enemySkill = getShortSkillName(dynamicBob.getEnemySkill()) if dynamicBob.getEnemySkill() else 'default'
      self.allyBloggerId = dynamicBob.getAllyBloggerID()
      self.enemyBloggerId = dynamicBob.getEnemyBloggerID()
      
    if (self.itemsCache.isSynced()):
      self.personalLevel = self.bobCtrl.personalLevel

    self.updateStats()
  
  @with_exception_sending
  def updateStats(self):
    self.stats = {}
    for t in self.bobCtrl.teamsRequester.getTeamsList():
      self.stats[str(t.team)] = { 'score': t.score, 'rank': t.rank }
  
  def setup(self):
    pass
  
  def getExtraData(self):
    try:
      if self.isInited:
        return {
          'bob': {
            'allySkill': self.allySkill,
            'enemySkill': self.enemySkill,
            'allyBloggerId': self.allyBloggerId,
            'enemyBloggerId': self.enemyBloggerId,
            'personalLevel': self.personalLevel,
            'stats': self.stats,
          }
        }
      else:
        if len(self.stats.items()) > 0:
          return {
            'bob': {
              'stats': self.stats,
            }
          }
        return {}
    except Exception as e:
      return {}