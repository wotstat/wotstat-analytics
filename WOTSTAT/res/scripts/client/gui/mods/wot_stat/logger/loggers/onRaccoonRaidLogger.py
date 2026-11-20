import json
from copy import deepcopy
from weakref import WeakKeyDictionary

from constants import CURRENCY_TOKEN_PREFIX, LOOTBOX_TOKEN_PREFIX, RESOURCE_TOKEN_PREFIX
from gui.goodies.goodie_items import PersonalVehicleDiscount
from gui.server_events.awards_formatters import BATTLE_BONUS_X5_TOKEN, CREW_BONUS_X3_TOKEN
from gui.shared.formatters.time_formatters import RentDurationKeys
from gui.shared.money import Money
from helpers import dependency
from items import ITEM_TYPES, parseIntCompactDescr, tankmen, vehicles
from messenger.formatters.service_channel_helpers import getCustomizationItem
from skeletons.gui.game_control import ICollectionsSystemController
from skeletons.gui.goodies import IGoodiesCache
from skeletons.gui.shared import IItemsCache

from ..eventLogger import eventLogger
from ..events import OnRaccoonRaidReward
from ..utils import prepare_for_json, setup_hangar_event
from ..wotHookEvents import wotHookEvents
from ...common.crossGameUtils import PUBLISHER, gamePublisher, getLootboxKeyNameByTokenID
from ...utils import print_debug


INewYearTamagotchiController = None
if gamePublisher() == PUBLISHER.LESTA:
  try:
    from constants import LOOTBOX_KEY_PREFIX
    from gui_lootboxes.gui.bonuses.bonuses_helpers import TOKEN_COMPENSATION_PREFIX, parseCompenstaionToken
    from new_year.gui.shared.variadic_discount import VariadicDiscount
    from new_year.helpers.server_settings import getNewYearRaidConfig
    from new_year.skeletons.new_year import INewYearTamagotchiController
    from new_year_common.items import new_year
    from new_year_common.items.components.ny_constants import (PET_TYPE_BY_NAME, TOKEN_LOOTBOX_FRAGMENT, TOKEN_MANDARIN, TOKEN_VARIADIC_DISCOUNT_PREFIX)
  except ImportError:
    INewYearTamagotchiController = None


SLOT_CURRENCIES = ('gold', 'credits', 'crystal', 'freeXP', 'equipCoin')
AMOUNT_REWARDS = SLOT_CURRENCIES + ('xp', 'tankmenXP', 'eventCoin', 'bpcoin', 'premium', 'premium_plus', 'premium_vip', 'slots', 'berths')
RENT_TYPES = (RentDurationKeys.TIME, RentDurationKeys.WINS, RentDurationKeys.BATTLES, RentDurationKeys.DAYS)


def getCount(value, default=0):
  if isinstance(value, dict): return int(value.get('count', default))
  return int(value)

def addAmount(amounts, tag, amount):
  if amount > 0:  amounts[tag] = amounts.get(tag, 0) + amount

def getItemTag(intCD):
  try:
    itemType, _, _ = parseIntCompactDescr(intCD)
    if itemType == ITEM_TYPES.crewBook:
      book = tankmen.getItemByCompactDescr(intCD)
      return ('crewBook', book.getUserName()) if book is not None else None

    item = vehicles.getItemByCompactDescr(intCD)
    return ('item', item.name) if item is not None else None
  except (IndexError, KeyError):
    return None


class OnRaccoonRaidLogger:
  itemsCache = dependency.descriptor(IItemsCache)
  goodiesCache = dependency.descriptor(IGoodiesCache)

  def __init__(self):
    self.pending = WeakKeyDictionary()
    wotHookEvents.RaccoonRaidRewardRequest += self.on_reward_request
    wotHookEvents.RaccoonRaidRewardResponse += self.on_reward_response
    wotHookEvents.Account_onBecomeNonPlayer += self.on_account_left

  def on_account_left(self, *args, **kwargs):
    self.pending.clear()

  def on_reward_request(self, processor):
    raid = dependency.instance(INewYearTamagotchiController).getRaidData()
    componentIDs = raid.get('componentIDs', ())
    startTime = raid.get('startTime')
    if len(componentIDs) != 3 or not startTime: return

    duration = raid.get('duration')
    primaryDuration = raid.get('primaryDuration')
    if duration is None or primaryDuration is None: return

    components = getNewYearRaidConfig().get('components', {})
    rawSlots = []
    for componentID in componentIDs:
      bonus = components.get(componentID, {}).get('bonus')
      rawSlots.append({'componentID': componentID, 'bonus': deepcopy(bonus)})

    self.pending[processor] = (startTime, duration, primaryDuration, rawSlots)

  def on_reward_response(self, processor, ctx):
    snapshot = self.pending.pop(processor, None)
    bonuses = ctx.get('bonus') if ctx else None
    if snapshot is None or not bonuses: return

    startTime, duration, primaryDuration, rawSlots = snapshot
    slots = [self.parseSlot(slot['bonus']) for slot in rawSlots]
    if None in slots:
      print_debug('Raccoon raid reward skipped: cannot resolve all ingredients')
      return

    parsed = self.parseRewards(bonuses)
    raw = json.dumps(prepare_for_json({'slots': rawSlots, 'bonus': bonuses}), ensure_ascii=False)

    event = OnRaccoonRaidReward(startTime, duration, primaryDuration, slots, parsed, raw)
    setup_hangar_event(event)
    eventLogger.emit_event(event)

  def parseSlot(self, bonus):
    if not bonus or len(bonus) != 1: return None

    resource, value = next(bonus.iteritems())
    if resource in SLOT_CURRENCIES: return ('currency', resource, value)

    if resource not in ('items', 'goodies', 'tokens') or len(value) != 1: return None

    itemID, amount = next(value.iteritems())
    if resource == 'items':
      item = getItemTag(itemID)
      return item + (amount,) if item is not None else None

    if resource == 'tokens':
      token = self._getTokenTag(itemID)
      if token is None: return None

      _, tag = token
      return ('token', tag, getCount(amount, 1))

    goodie = self._parseGoodie(itemID, getCount(amount, 1))
    if goodie is None: return None
    
    field, data = goodie
    if field == 'boosters': return ('booster',) + data
    if field == 'equip': return ('equip',) + data
    return None

  def parseRewards(self, bonuses):
    parsed = {}
    vehicleCompensations = {}
    itemCompensations = {}
    for bonus in bonuses:
      for field in AMOUNT_REWARDS: addAmount(parsed, field, bonus.get(field, 0))
      addAmount(parsed, 'lootboxFragments', getCount(bonus.get(TOKEN_LOOTBOX_FRAGMENT, 0)))

      for tag, amount in bonus.get('currencies', {}).iteritems():
        count = getCount(amount)
        if count > 0: parsed.setdefault('currencies', []).append((tag, count))

      for field in ('items', 'crewBooks'):
        for intCD, count in bonus.get(field, {}).iteritems():
          item = getItemTag(intCD)
          if item is None or count <= 0: continue

          kind, tag = item
          rewardField = 'crewBooks' if kind == 'crewBook' else 'items'
          parsed.setdefault(rewardField, []).append((tag, count))

      for goodieID, data in bonus.get('goodies', {}).iteritems():
        count = getCount(data, 1)
        if count <= 0: continue

        goodie = self._parseGoodie(goodieID, count)
        if goodie is None: continue

        rewardField, reward = goodie
        parsed.setdefault(rewardField, []).append(reward)

      for field in ('tokens', 'lootBoxToken', 'tmanToken'):
        for token, value in bonus.get(field, {}).iteritems():
          count = getCount(value)
          if count > 0:
            self._parseToken(parsed, itemCompensations, token, count)

      for tag, value in bonus.get('entitlements', {}).iteritems():
        count = getCount(value)
        if count > 0:
          parsed.setdefault('entitlements', []).append((tag, count))

      self._parseVehicles(parsed, vehicleCompensations, bonus.get('vehicles', []))
      self._parseCustomizations(parsed, itemCompensations, bonus.get('customizations', []))

    if vehicleCompensations:
      parsed['compensatedVehicles'] = [
        (tag, variant, amounts)
        for (tag, variant), amounts in sorted(vehicleCompensations.iteritems())
        if amounts
      ]

    if itemCompensations:
      parsed['compensatedItems'] = [
        (kind, tag, currency, amount)
        for (kind, tag, currency), amount in sorted(itemCompensations.iteritems())
      ]

    return parsed

  def _parseGoodie(self, goodieID, count):
    shop = self.itemsCache.items.shop
    if goodieID in shop.boosters:
      booster = self.goodiesCache.getBooster(goodieID)
      return ('boosters', (booster.boosterGuiType, booster.effectTime, booster.effectValue, count))

    if goodieID in shop.demountKits:
      kit = self.goodiesCache.getDemountKit(goodieID)
      return ('equip', (kit.itemTypeName, count, kit.demountKitGuiType))

    if goodieID in shop.recertificationForms:
      form = self.goodiesCache.getRecertificationForm(goodieID)
      return ('equip', (form.itemTypeName, count, ''))

    if goodieID not in shop.discounts:
      return None
    discount = self.goodiesCache.getDiscount(goodieID)

    if not isinstance(discount, PersonalVehicleDiscount): return None

    tag = vehicles.getVehicleType(discount.targetValue).name
    return ('discounts', (tag, discount.effectValue, count))

  def _getTokenTag(self, token):
    if token.startswith(LOOTBOX_TOKEN_PREFIX):
      box = self.itemsCache.items.tokens.getLootBoxByTokenID(token)
      return ('lootboxesTokens', box.getType()) if box is not None else None

    if token.startswith(LOOTBOX_KEY_PREFIX):
      tag = getLootboxKeyNameByTokenID(token)
      return ('lootboxKeys', tag) if tag else None

    if token.startswith(tankmen.RECRUIT_TMAN_TOKEN_PREFIX):
      recruit = tankmen.getRecruitInfoFromToken(token)
      return ('recruits', recruit['sourceID']) if recruit is not None else None

    if token.startswith(BATTLE_BONUS_X5_TOKEN): return ('bonusTokens', 'battle_bonus_x5')
    if token.startswith(CREW_BONUS_X3_TOKEN): return ('bonusTokens', 'crew_bonus_x3')
    if token in PET_TYPE_BY_NAME or token == TOKEN_MANDARIN: return ('currencies', token)
    if token == TOKEN_LOOTBOX_FRAGMENT: return ('lootboxFragments', TOKEN_LOOTBOX_FRAGMENT)
    if token.startswith(RESOURCE_TOKEN_PREFIX): return ('bonusTokens', token[len(RESOURCE_TOKEN_PREFIX):])
    if token.startswith(CURRENCY_TOKEN_PREFIX):
      currency = token[len(CURRENCY_TOKEN_PREFIX):]
      if currency in AMOUNT_REWARDS: return (currency, currency)

    return None

  def _parseToken(self, parsed, compensations, token, count):
    if token.startswith(TOKEN_COMPENSATION_PREFIX):
      self._parseCompensationToken(compensations, token, count)
      return

    if token.startswith(TOKEN_VARIADIC_DISCOUNT_PREFIX):
      discount = VariadicDiscount(token, useCache=True)
      value = discount.getDiscountValue()
      if value is None: return

      tag = 'level:{}'.format(discount.getTankLevel())
      parsed.setdefault('discounts', []).append((tag, value, count))
      return

    resource = self._getTokenTag(token)
    if resource is None: return

    field, tag = resource
    if field in AMOUNT_REWARDS or field == 'lootboxFragments':
      addAmount(parsed, field, count)
      return
    
    parsed.setdefault(field, []).append((tag, count))

  def _parseCompensationToken(self, compensations, token, count):
    currency, value, kind, itemID = parseCompenstaionToken(token)
    if kind == 'cllc':
      collections = dependency.instance(ICollectionsSystemController)
      collection = collections.getCollection(int(itemID))
      if collection is not None:
        addAmount(compensations, ('collection', collection.name, currency), value * count)
      return

    if kind == 'toy':
      toy = new_year.g_cache.toys.get(int(itemID))
      if toy is not None and toy.hasName():
        addAmount(compensations, ('toy', toy.name, currency), value * count)

  def _parseVehicles(self, parsed, compensations, batches):
    if isinstance(batches, dict):
      batches = (batches,)

    for batch in batches:
      for intCD, data in batch.iteritems():
        self._parseVehicle(parsed, compensations, intCD, data)

  def _parseVehicle(self, parsed, compensations, intCD, data):
    try: tag = vehicles.getVehicleType(abs(intCD)).name
    except (IndexError, KeyError): return

    compensated = False
    count = data.get('compensatedNumber', 1)
    for field, variant in (('rentCompensation', 'rent'), ('customCompensation', 'normal')):
      compensation = data.get(field)
      if not compensation or count <= 0: continue

      compensated = True
      amounts = compensations.setdefault((tag, variant), {})
      for currency, amount in Money.makeMoney(compensation).iteritems():
        addAmount(amounts, currency, (amount or 0) * count)

    if compensated: return
    if intCD < 0:
      parsed.setdefault('removedVehicles', []).append(tag)
      return

    rent = data.get('rent')
    if not rent:
      parsed.setdefault('addedVehicles', []).append(tag)
      return
    
    for rentType in RENT_TYPES:
      rentValue = rent.get(rentType)
      if rentValue:
        parsed.setdefault('rentedVehicles', []).append((tag, rentType, str(rentValue)))
        return

  def _parseCustomizations(self, parsed, compensations, customizations):
    for customization in customizations:
      if customization.get('boundToCurrentVehicle'):
        continue

      kind = customization['custType'].split(':', 1)[0]
      item = getCustomizationItem(customization['id'], kind)
      if item is None: continue

      tag = item.descriptor.userKey
      count = customization['value']
      if count > 0:
        parsed.setdefault('customizations', []).append((item.itemFullTypeName, tag, count))

      if 'customCompensation' not in customization: continue

      compensatedNumber = customization.get('compensatedNumber', 1)
      compensation = Money.makeMoney(customization['customCompensation'])

      for currency, amount in compensation.iteritems():
        target = (item.itemFullTypeName, tag, currency)
        addAmount(compensations, target, (amount or 0) * compensatedNumber)


if INewYearTamagotchiController is not None:
  onRaccoonRaidLogger = OnRaccoonRaidLogger()
