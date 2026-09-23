import hashlib
import os
import time
import json
import base64
import re
from weakref import WeakKeyDictionary
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
from ..utils import setup_hangar_event, setup_session_meta, setup_server_info
from ...common.crossGameUtils import lootboxKeyPrefix, getLootboxKeyNameByID, getLootboxKeyNameByTokenID


NY_TOYS_TOKEN_PATTERN = re.compile(r'^ny([0-9]+)Toys$')
NY_MANDARIN_TOKEN_PATTERN = re.compile(r'^ny[0-9]+_mandarin$')
NY_MANDARIN_COMPENSATION_PATTERN = re.compile(r'^lb_comp:(ny[0-9]+_mandarin):([0-9]+):(.+)$')


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

  def __init__(self):
    self.wtPending = {}
    self.wtClaimRequests = WeakKeyDictionary()

    wotHookEvents.LootBoxOpenProcessorOpenResponse += self.on_response
    wotHookEvents.LootBoxSystemOpenProcessorResponse += self.on_system_response

    wotHookEvents.WTLootBoxRollResponse += self.on_wt_roll_response
    wotHookEvents.WTLootBoxRerollResponse += self.on_wt_reroll_response
    wotHookEvents.WTLootBoxHistoryResponse += self.on_wt_history_response
    wotHookEvents.WTLootBoxClaimRequest += self.on_wt_claim_request
    wotHookEvents.WTLootBoxClaimResponse += self.on_wt_claim_response
    wotHookEvents.WTTankLootBoxOpened += self.on_wt_tank_opened
    wotHookEvents.Account_onBecomeNonPlayer += self.on_wt_account_left

  def on_wt_account_left(self, obj, *a, **k):
    self.wtPending.clear()
    self.wtClaimRequests.clear()

  def on_system_response(self, obj, code, ctx=None):
    print_debug("Lootbox.on_system_response")
    if ctx is None:
      return

    box = obj._getLootBox()
    self.got_rewards(ctx.get('bonus', []), lootboxId=box.getID(), openCount=obj._getCount(), keyId=0)

  def _wt_auto_claimed(self, box, bonus):
    from white_tiger.gui.game_control.loot_boxes_controller import _preprocessAwards
    from skeletons.gui.game_control import ILootBoxesController

    controller = dependency.instance(ILootBoxesController)
    rewards = _preprocessAwards([bonus], box)
    return controller.isStopTokenAmongRewardList(rewards, box.getType())

  def _wt_store_reward(self, box, bonus, count, rerollCount):
    if not isinstance(bonus, dict):
      print_warn('OnLootboxLogger: WT bonus is not a dict')
      return

    pending = dict(bonus=bonus, count=count, rerollCount=rerollCount)
    self.wtPending[box.getID()] = pending
    if self._wt_auto_claimed(box, bonus):
      self.wtPending.pop(box.getID(), None)
      self.got_rewards([bonus], lootboxId=box.getID(), openCount=count,
                       keyId=0, rerollCount=rerollCount, recordBoxCount=count)

  def on_wt_roll_response(self, obj, code, ctx=None):
    if ctx is None:
      return

    box = obj._WTLootBoxRollProcessor__lootBox
    count = obj._WTLootBoxRollProcessor__lootBoxCount
    self._wt_store_reward(box, ctx.get('bonus'), count, 0)

  def on_wt_history_response(self, obj, code, ctx=None):
    if not ctx or not isinstance(ctx.get('bonus'), dict):
      return

    boxId = obj._WtLootBoxReRollHistoryProcessor__boxID
    if boxId in self.wtPending:
      return

    from skeletons.gui.game_control import ILootBoxesController
    box = self.itemsCache.items.tokens.getLootBoxByID(boxId)
    controller = dependency.instance(ILootBoxesController)
    self.wtPending[boxId] = dict(bonus=ctx['bonus'],
                                  count=ctx.get('boxCount', 1),
                                  rerollCount=controller.getReRollAttemptsCount(box.getType()))

  def on_wt_reroll_response(self, obj, code, ctx=None):
    if ctx is None:
      return

    boxId = obj._WTLootBoxRerollProcessor__boxID
    previous = self.wtPending.pop(boxId, None)
    if previous is not None:
      self.got_rewards([previous['bonus']], claim=False, lootboxId=boxId,
                       openCount=previous['count'], keyId=0,
                       rerollCount=previous['rerollCount'],
                       recordBoxCount=previous['count'])

    box = self.itemsCache.items.tokens.getLootBoxByID(boxId)
    count = previous['count'] if previous is not None else ctx.get('boxCount', 1)
    rerollCount = previous['rerollCount'] + 1 if previous is not None else 1
    self._wt_store_reward(box, ctx.get('bonus'), count, rerollCount)

  def on_wt_claim_request(self, obj, *a, **k):
    boxId = obj._WtLootBoxClaimProcessor__boxID
    pending = self.wtPending.get(boxId)
    if pending is not None:
      self.wtClaimRequests[obj] = (pending['count'], pending['rerollCount'])
      return

    from skeletons.gui.game_control import ILootBoxesController
    box = self.itemsCache.items.tokens.getLootBoxByID(boxId)
    controller = dependency.instance(ILootBoxesController)
    self.wtClaimRequests[obj] = (
      max(controller.getPendingBoxesCount(box.getType()), 1),
      controller.getReRollAttemptsCount(box.getType()))

  def on_wt_claim_response(self, obj, code, ctx=None):
    requestedCount, requestedRerollCount = self.wtClaimRequests.pop(obj, (1, 0))
    if ctx is None:
      return

    boxId = obj._WtLootBoxClaimProcessor__boxID
    pending = self.wtPending.pop(boxId, None)
    bonus = ctx.get('bonus') or (pending['bonus'] if pending else None)
    if not isinstance(bonus, dict):
      print_warn('OnLootboxLogger: WT claim bonus is not a dict')
      return

    count = pending['count'] if pending else requestedCount
    rerollCount = pending['rerollCount'] if pending else requestedRerollCount
    self.got_rewards([bonus], lootboxId=boxId, openCount=count, keyId=0, rerollCount=rerollCount, recordBoxCount=count)

  def on_wt_tank_opened(self, requestId, resultId, errorStr, ext):
    from AccountCommands import RES_SUCCESS
    if resultId != RES_SUCCESS or not isinstance(ext, dict) or not ext.get('vehicles'):
      return

    box = self.itemsCache.items.tokens.getLootBoxByType('wt_tank')
    if box is not None:
      self.got_rewards([ext], lootboxId=box.getID(), openCount=1, keyId=0)

  def on_response(self, obj, code, ctx=None):
    print_debug("Lootbox.on_response")
    
    if ctx is None:
      print_warn('OnLootboxLogger.on_response: ctx is None')
      return
    
    print_log("Lootbox.on_response")
    box = obj._LootBoxOpenProcessor__lootBox
    count = obj._LootBoxOpenProcessor__count
    keyId = getattr(obj, '_LootBoxOpenProcessor__keyID', 0)
    self.got_rewards(ctx.get('bonus', []), lootboxId=box.getID(), openCount=count, keyId=keyId)
    
  @with_exception_sending
  def got_rewards(self, bonuses, lootboxId, openCount, keyId=0,
                  claim=True, rerollCount=0, recordBoxCount=1):
    print_log("GOT REWARD, claim: %s" % str(claim))
    print(bonuses)

    lootboxTag = self.itemsCache.items.tokens.getLootBoxByID(lootboxId).getType()
    openByTag = lootboxTag
    
    if keyId is not None and keyId != 0:
      openByTag = getLootboxKeyNameByID(keyId)
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
      self.parseTokens(parsed, bonus, lootboxId, keyId, recordBoxCount)
      self.parseEntitlements(parsed, bonus)
      self.parseCustomizations(parsed, bonus)
      self.parseTankmen(parsed, bonus)
      self.parseEnhancements(parsed, bonus)
      self.parseBlueprints(parsed, bonus)
      self.parseSelectableCrewbook(parsed, bonus)
      self.parseDogtags(parsed, bonus)
      self.parseNewYearToys(parsed, bonus)
      
      event = OnLootboxOpen(lootboxTag, openByTag, not self.isEmptyBonus(bonus), openCount, groupId, rerollCount, recordBoxCount)
      event.setup(json.dumps(preprocessData(bonus), ensure_ascii=False), parsed, claim)
      setup_session_meta(event)
      setup_hangar_event(event)
      setup_server_info(event)

      eventLogger.emit_event(event)

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
    
    currencies = []
    for currency, countDict in platformCurrencies.iteritems():
      amount = 0
      if isinstance(countDict, dict):
        amount = countDict.get('count', 0)
      elif isinstance(countDict, int):
        amount = int(countDict)
      elif isinstance(countDict, float):
        amount = int(countDict)
      elif isinstance(countDict, str):
        try:
          amount = int(countDict)
        except ValueError:
          amount = 0
        
      currencies.append((currency, amount))
    
    parsed['currencies'] = currencies
  
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
  def parseTokens(self, parsed, bonus, lootboxId, keyId, recordBoxCount):
    parsed['lootboxesTokens'] = []
    parsed['bonusTokens'] = []
    parsed['extraTokens'] = []
    tokens = bonus.get('tokens', {})
    
    for tokenID, tokenData in tokens.iteritems():
      count = tokenData.get('count', 0)

      if tokenID.startswith(LOOTBOX_TOKEN_PREFIX):
        if str(lootboxId) == tokenID.split(':')[1]:
          count += recordBoxCount

        if count > 0:
          parsed['lootboxesTokens'].append((self.itemsCache.items.tokens.getLootBoxByTokenID(tokenID).getType(), count))
          
      elif tokenID.startswith(LOOTBOX_KEY_PREFIX):
        if str(keyId) == tokenID.split(':')[1]:
          count += recordBoxCount
          
        if count > 0:
          parsed['lootboxesTokens'].append((getLootboxKeyNameByTokenID(tokenID), count))
        
      elif tokenID.startswith(BATTLE_BONUS_X5_TOKEN):
        parsed['bonusTokens'].append(('battle_bonus_x5', count))
        
      elif tokenID.startswith(CREW_BONUS_X3_TOKEN):
        parsed['bonusTokens'].append(('crew_bonus_x3', count))
        
      elif NY_MANDARIN_TOKEN_PATTERN.match(tokenID):
        parsed['extraTokens'].append((tokenID, count))

  @with_exception_sending
  def parseEntitlements(self, parsed, bonus):
    parsed['entitlements'] = []
    entitlements = bonus.get('entitlements', {})
    for eId, data in entitlements.iteritems():
      count = data.get('count', 0)
      parsed['entitlements'].append((eId, count))

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
    
    for tokenID, toys in bonus.iteritems():
      match = NY_TOYS_TOKEN_PATTERN.match(tokenID)
      if match:
        for toyID, count in toys.iteritems():
          parsed['toys'].append(('ny{}_{}'.format(match.group(1), toyID), count))
      
    
    parsed['compensatedToys'] = []
    for tokenID, tokenValue in bonus.get('tokens', {}).iteritems():
      match = NY_MANDARIN_COMPENSATION_PATTERN.match(tokenID)
      if match:
        mandarinToken = match.group(1)
        amount = int(match.group(2))
        toy = match.group(3)
        count = tokenValue['count']
        parsed['compensatedToys'].append((toy, mandarinToken, amount * count))
        
    print(parsed['compensatedToys'])


onLootboxLogger = OnLootboxLogger()
