import hashlib
import os
import time
import json
import base64
from typing import List  # noqa: F401

from constants import LOOTBOX_TOKEN_PREFIX, PREMIUM_ENTITLEMENTS
from nations import NAMES as NATIONS_NAMES

from gui.goodies.goodie_items import PersonalVehicleDiscount
from gui.server_events.awards_formatters import BATTLE_BONUS_X5_TOKEN, CREW_BONUS_X3_TOKEN
from gui.shared.money import Currency, Money
from gui.shared.utils.requesters.blueprints_requester import getUniqueBlueprints
from gui.shared.formatters.time_formatters import RentDurationKeys
from messenger.formatters.service_channel_helpers import getCustomizationItem

from helpers import dependency
from skeletons.gui.shared import IItemsCache
from skeletons.gui.goodies import IGoodiesCache

from items import vehicles as vehicles_core, ITEM_TYPES, tankmen

from ..wotHookEvents import wotHookEvents
from ...utils import print_log, print_warn, print_debug
from ...common.exceptionSending import with_exception_sending
from ..events import OnLootboxOpen
from ..eventLogger import eventLogger
from ..utils import setup_hangar_event, setup_session_meta, get_private_attr, setup_server_info
from ...common.crossGameUtils import lootboxKeyPrefix, getLootboxKeyNameByID, getLootboxKeyNameByTokenID


def prepareString(obj):
  if isinstance(obj, str):
    try:
      obj.decode('utf-8')
    except UnicodeDecodeError:
      return base64.b64encode(obj)
  return obj

def preprocessData(obj):
  if isinstance(obj, set):
    return list(obj)
  elif isinstance(obj, str):
    return prepareString(obj)
  elif isinstance(obj, dict):
    return { prepareString(str(k)): preprocessData(v) for k, v in obj.items() }
  elif isinstance(obj, list):
    return [preprocessData(i) for i in obj]
  elif isinstance(obj, tuple):
    return [preprocessData(i) for i in obj]
  return obj

ALL_CURRENCIES = [ Currency.CREDITS, Currency.GOLD, Currency.FREE_XP, Currency.CRYSTAL, Currency.EVENT_COIN, Currency.BPCOIN, Currency.EQUIP_COIN ]
LOOTBOX_KEY_PREFIX = lootboxKeyPrefix()

def getVehicleInfos(vehicles):
  addVehNames = []
  removeVehNames = []
  rentedVehNames = []
  compensatedVehicles = []

  def getRentInfo(rentData):
    # type: (dict) -> (str, int)

    timeLeft = rentData.get(RentDurationKeys.TIME, 0)
    if timeLeft:
      return ('time', int(timeLeft))
    else:
      for rentType in [RentDurationKeys.WINS, RentDurationKeys.BATTLES, RentDurationKeys.DAYS]:
        rentTypeValue = rentData.get(rentType, 0)
        if rentTypeValue > 0 and rentType != float('inf'):
          return (rentType, rentTypeValue)

  for vehicleDict in vehicles:
    for vehCompDescr, vehData in vehicleDict.iteritems():
      tankTag = vehicles_core.getVehicleType(abs(vehCompDescr)).name

      if b'rentCompensation' in vehData:
        comp = Money.makeFromMoneyTuple(vehData[b'rentCompensation'])
        compensatedVehicles.append((tankTag, 'rent', comp.gold))
        continue

      if b'customCompensation' in vehData:
        comp = Money.makeFromMoneyTuple(vehData[b'customCompensation'])
        compensatedVehicles.append((tankTag, 'normal', comp.gold))
        continue


      isNegative = vehCompDescr < 0
      isRented = 'rent' in vehData

      if isNegative:
        removeVehNames.append(tankTag)
      elif isRented:
        rentData = vehData['rent']
        rentType, rentValue = getRentInfo(rentData)
        rentedVehNames.append((tankTag, rentType, rentValue))
      else:
        addVehNames.append(tankTag)

  return (addVehNames, removeVehNames, rentedVehNames, compensatedVehicles)

def getGoodiesString(goodies, itemsCache, goodiesCache):
  # type: (dict, IItemsCache, IGoodiesCache) -> str
  boosters = []
  discounts = []
  equip = []
  
  for goodieID, ginfo in goodies.iteritems():
    if goodieID in itemsCache.items.shop.boosters:
      booster = goodiesCache.getBooster(goodieID)
      if booster is not None and booster.enabled:
        count = ginfo.get('count', 0)
        boosters.append((booster.boosterGuiType, booster.effectTime, booster.effectValue, count))

    elif goodieID in itemsCache.items.shop.discounts:
      discount = goodiesCache.getDiscount(goodieID)
      if discount is not None and discount.enabled:
        if isinstance(discount, PersonalVehicleDiscount):
          target = discount.targetValue
          tag = vehicles_core.getVehicleType(target).name
          discounts.append((tag, discount.effectValue))
          
    elif goodieID in itemsCache.items.shop.demountKits:
      dk = goodiesCache.getDemountKit(goodieID)
      if dk and dk.enabled:
        equip.append((dk.itemTypeName, ginfo.get('count', 0)))
        
    elif goodieID in itemsCache.items.shop.recertificationForms:
      rf = goodiesCache.getRecertificationForm(goodieID)
      if rf and rf.enabled:
        equip.append((rf.itemTypeName, ginfo.get('count', 0)))

  return (boosters, discounts, equip)

class OnLootboxLogger:

  itemsCache = dependency.descriptor(IItemsCache)
  goodiesCache = dependency.descriptor(IGoodiesCache)

  lastOpenId = None
  lastOpenKeyId = None
  lastOpenCount = None
  lastRerollCtx = None
  lastRerollCount = -1
  lastRerollClaimed = True

  def __init__(self):
    wotHookEvents.LootBoxOpenProcessorOpenRequest += self.on_request
    wotHookEvents.LootBoxOpenProcessorOpenResponse += self.on_response
    
    wotHookEvents.LootBoxRerollProcessorOpenRequest += self.on_reroll_request
    wotHookEvents.LootBoxRerollProcessorOpenResponse += self.on_reroll_response
    
    wotHookEvents.LootBoxSystemOpenProcessorRequest += self.on_system_request
    wotHookEvents.LootBoxSystemOpenProcessorResponse += self.on_system_response
    
  def on_reroll_request(self, obj, *a, **k):
    print_debug("Lootbox.on_reroll_request")
    
    self.lastOpenKeyId = 0
    self.lastOpenId = obj._LootBoxReRollProcessor__lootBox.getID()
    self.lastOpenCount = 1
    self.lastRerollClaimed = False
  
  def on_request(self, obj, *a, **k):
    print_debug("Lootbox.on_request")
    
    self.lastOpenKeyId = 0
    if self.lastRerollClaimed: self.resetReroll()
    
    try: self.lastOpenKeyId = obj._LootBoxOpenProcessor__keyID
    except AttributeError: pass
  
    self.lastOpenId = obj._LootBoxOpenProcessor__lootBox.getID()
    self.lastOpenCount = obj._LootBoxOpenProcessor__count

  def on_reroll_response(self, obj, code, ctx=None):
    print_debug("Lootbox.on_reroll_response")
    
    if ctx is None:
      print_warn('OnLootboxLogger.on_reroll_response: ctx is None')
      return
    
    rerollCount = ctx.get('reRollCount', 0)
    if self.lastRerollCount + 1 == rerollCount:
      print_log("Lootbox.reroll (continue)[{}]".format(rerollCount))
      if self.lastRerollCtx is not None:
        self.got_rewards([self.lastRerollCtx.get('rewards', {})], claim=False, rerollCount=self.lastRerollCount)
    else:
      print_log("Lootbox.reroll (new)")
      
    self.lastRerollCount = rerollCount
    self.lastRerollCtx = ctx
    self.lastRerollClaimed = False
    
    if self.check_is_auto_claimed(obj, ctx):
      print_log("Lootbox.reroll (auto-claim)")
      self.got_rewards([ctx.get('rewards', {})], rerollCount=rerollCount)
      self.resetReroll()
        
  def check_is_auto_claimed(self, obj, ctx):
    controller = get_private_attr(obj, '__lootBoxesController')
    boxType = get_private_attr(obj, '__boxType')

    if not controller or not boxType: return False
    if not hasattr(controller, 'isStopTokenAmongRewardList'): return False
    
    try:
      from white_tiger.gui.game_control.loot_boxes_controller import _preprocessAwards
      rewards = _preprocessAwards([ctx.get('rewards', {})])
      return controller.isStopTokenAmongRewardList(rewards, boxType)
    except: pass
    
    return False

  def on_system_request(self, obj, *a, **k):
    print_debug("Lootbox.on_system_request")

  def on_system_response(self, obj, code, ctx=None):
    print_debug("Lootbox.on_system_response")

  def on_response(self, obj, code, ctx=None):
    print_debug("Lootbox.on_response")
    
    if ctx is None:
      print_warn('OnLootboxLogger.on_response: ctx is None')
      return
    
    if self.lastOpenId is None or self.lastOpenCount is None:
      print_warn('OnLootboxLogger.on_response: lastOpenId or lastOpenCount is None')
      return

    print_log("Lootbox.on_response")
    self.got_rewards(ctx.get('bonus', []), rerollCount=max(self.lastRerollCount, 0))
    self.resetReroll()
    
  @with_exception_sending
  def got_rewards(self, bonuses, claim=True, rerollCount=0):
    print_log("GOT REWARD, claim: %s" % str(claim))
    print(bonuses)
    
    if claim: self.lastRerollClaimed = True
    
    lootboxTag = self.itemsCache.items.tokens.getLootBoxByID(self.lastOpenId).getType()
    openByTag = lootboxTag
    
    if self.lastOpenKeyId is not None and self.lastOpenKeyId != 0:
      openByTag = getLootboxKeyNameByID(self.lastOpenKeyId)
      if openByTag is None: openByTag = lootboxTag

    unique_bytes = str(time.time()).encode('utf-8') + os.urandom(16)
    groupId = hashlib.md5(unique_bytes).hexdigest()

    for bonus in bonuses:
      parsed = {}

      self.parseCurrency(parsed, bonus)
      self.parsePremium(parsed, bonus)
      self.parseVehicles(parsed, bonus)
      self.parseSlots(parsed, bonus)
      self.parseBerths(parsed, bonus)
      self.parseItems(parsed, bonus)
      self.parseGoodies(parsed, bonus)
      self.parseTokens(parsed, bonus)
      self.parseEntitlements(parsed, bonus)
      self.parseCustomizations(parsed, bonus)
      self.parseTankmen(parsed, bonus)
      self.parseEnhancements(parsed, bonus)
      self.parseBlueprints(parsed, bonus)
      self.parseSelectableCrewbook(parsed, bonus)
      self.parseDogtags(parsed, bonus)
      self.parseNewYearToys(parsed, bonus)
      
      event = OnLootboxOpen(lootboxTag, openByTag, not self.isEmptyBonus(bonus), self.lastOpenCount, groupId, rerollCount)
      event.setup(json.dumps(preprocessData(bonus), ensure_ascii=False), parsed, claim)
      setup_session_meta(event)
      setup_hangar_event(event)
      setup_server_info(event)

      eventLogger.emit_event(event)

  def resetReroll(self):
    self.lastRerollCount = -1
    self.lastRerollCtx = None
    self.lastRerollClaimed = True

  @with_exception_sending
  def isEmptyBonus(self, bonus):
    if not bonus: return True
    
    def checkIsKeyRemove(key, value):
      if not key.startswith(LOOTBOX_KEY_PREFIX) and not key.startswith(LOOTBOX_TOKEN_PREFIX): return False
      return value.get('count', 1) <= 0
    
    if len(bonus) == 1 and 'tokens' in bonus:
      tokens = bonus['tokens']
      if all(checkIsKeyRemove(key, value) for key, value in tokens.items()):
        return True
      
    return False

  @with_exception_sending
  def parseCurrency(self, parsed, bonus):
    for currenciesKey in ALL_CURRENCIES:
      parsed[currenciesKey] = bonus.get(currenciesKey, 0)

    platformCurrencies = bonus.get('currencies', {})
    parsed['currencies'] = [[currency, int(countDict)] for currency, countDict in platformCurrencies.iteritems()]
  
  @with_exception_sending
  def parsePremium(self, parsed, bonus):
    for premiumType in PREMIUM_ENTITLEMENTS.ALL_TYPES:
      parsed[premiumType] = bonus.get(premiumType, 0)

  @with_exception_sending
  def parseVehicles(self, parsed, bonus):
    vehiclesList = bonus.get('vehicles', [])
    addVehNames, removeVehNames, rentedVehNames, compensatedVehicles = getVehicleInfos(vehiclesList)
    parsed['addedVehicles'] = addVehNames
    parsed['rentedVehicles'] = rentedVehNames
    parsed['compensatedVehicles'] = compensatedVehicles

  @with_exception_sending
  def parseSlots(self, parsed, bonus):
    parsed['slots'] = bonus.get('slots', 0)

  @with_exception_sending
  def parseBerths(self, parsed, bonus):
    parsed['berths'] = bonus.get('berths', 0)

  @with_exception_sending
  def parseItems(self, parsed, bonus):
    parsed['items'] = []
    parsed['crewBooks'] = []
    items = bonus.get('items', {})

    for intCD, count in items.iteritems():
      itemTypeID, _, _ = vehicles_core.parseIntCompactDescr(intCD)
      if itemTypeID == ITEM_TYPES.crewBook:
        crewBook = tankmen.getItemByCompactDescr(intCD)
        parsed['crewBooks'].append((crewBook.getUserName(), count))
      else:
        parsed['items'].append((vehicles_core.getItemByCompactDescr(intCD).name, count))

  @with_exception_sending
  def parseGoodies(self, parsed, bonus):
      goodies = bonus.get('goodies', {})
      boosters, discounts, equip = getGoodiesString(goodies, self.itemsCache, self.goodiesCache)
      parsed['boosters'] = boosters
      parsed['discounts'] = discounts
      parsed['equip'] = equip

  @with_exception_sending
  def parseTokens(self, parsed, bonus):
    parsed['lootboxesTokens'] = []
    parsed['bonusTokens'] = []
    parsed['extraTokens'] = []
    tokens = bonus.get('tokens', {})
    
    for tokenID, tokenData in tokens.iteritems():
      count = tokenData.get('count', 0)

      if tokenID.startswith(LOOTBOX_TOKEN_PREFIX):
        if str(self.lastOpenId) == tokenID.split(':')[1]:
          count += 1

        if count != 0:
          parsed['lootboxesTokens'].append((self.itemsCache.items.tokens.getLootBoxByTokenID(tokenID).getType(), count))
          
      elif tokenID.startswith(LOOTBOX_KEY_PREFIX):
        if str(self.lastOpenKeyId) == tokenID.split(':')[1]:
          count += 1
          
        if count != 0:
          parsed['lootboxesTokens'].append((getLootboxKeyNameByTokenID(tokenID), count))
        
      elif tokenID.startswith(BATTLE_BONUS_X5_TOKEN):
        parsed['bonusTokens'].append(('battle_bonus_x5', count))
        
      elif tokenID.startswith(CREW_BONUS_X3_TOKEN):
        parsed['bonusTokens'].append(('crew_bonus_x3', count))
        
      elif tokenID == 'ny25_mandarin':
        parsed['extraTokens'].append(('ny25_mandarin', count))

  # TODO: Entitlements
  @with_exception_sending
  def parseEntitlements(self, parsed, bonus):
    # entitlementsList = [ (eID, eData.get('count', 0)) for eID, eData in bonus.get('entitlements', {}).iteritems() ]
    pass

  @with_exception_sending
  def parseCustomizations(self, parsed, bonus):
    parsed['customizations'] = []
    customizations = bonus.get('customizations', [])
    for customizationItem in customizations:
      splittedCustType = customizationItem.get('custType', '').split(':')
      custType = splittedCustType[0]
      count = customizationItem['value']
      if len(splittedCustType) == 2 and 'progression' in splittedCustType[1]:
          continue

      item = getCustomizationItem(customizationItem['id'], custType)

      parsed['customizations'].append((item.itemFullTypeName, item.descriptor.userKey, count))

  # TODO: Tankmen 
  @with_exception_sending
  def parseTankmen(self, parsed, bonus):
    # tankmen = bonus.get('tankmen', {})
    pass

  # TODO: Enhancements
  @with_exception_sending
  def parseEnhancements(self, parsed, bonus):
    # enhancements = bonus.get('enhancements', {})
    pass
    
  @with_exception_sending
  def parseBlueprints(self, parsed, bonus):
    parsed['blueprints'] = []
    blueprints = bonus.get('blueprints', {})
    vehicleFragments, nationFragments, universalFragments = getUniqueBlueprints(blueprints)
    for fragmentCD, count in vehicleFragments.iteritems():
      parsed['blueprints'].append(('VEHICLE', vehicles_core.getVehicleType(fragmentCD).name, count))

    for nationID, count in nationFragments.iteritems():
      parsed['blueprints'].append(('NATION', NATIONS_NAMES[nationID], count))

    if universalFragments:
      parsed['blueprints'].append(('UNIVERSAL', 'ANY', universalFragments))

  @with_exception_sending
  def parseSelectableCrewbook(self, parsed, bonus):
    selectableCrewbook = bonus.get('selectableCrewbook', {})
    parsed['selectableCrewbook'] = [crewbookName for crewbookName, data in selectableCrewbook.iteritems()]
  
  # TODO: dogtags
  @with_exception_sending
  def parseDogtags(self, parsed, bonus):
    # dogtags = bonus.get('dogTagComponents', {})
    pass
  
  @with_exception_sending
  def parseNewYearToys(self, parsed, bonus):
    parsed['toys'] = []
    
    toys = bonus.get('ny25Toys', {})
    for toyID, count in toys.iteritems():
      parsed['toys'].append(('ny25_' + str(toyID), count))
      
    
    parsed['compensatedToys'] = []
    for tokenID, tokenValue in bonus.get('tokens', {}).iteritems():
      if tokenID.startswith('lb_comp:ny25_mandarin:'):
        amount = int(tokenID.split(':')[2])
        toy = tokenID.split(':')[3]
        count = tokenValue['count']
        parsed['compensatedToys'].append((toy, 'ny25_mandarin', amount * count))
        
    print(parsed['compensatedToys'])


onLootboxLogger = OnLootboxLogger()
