# coding=utf-8

import datetime

from constants import AUTH_REALM
from ..load_mod import config
from ..common.crossGameUtils import readClientServerVersion

GAME_VERSION = readClientServerVersion()[1]


class Event(object):
  class NAMES:
    ON_BATTLE_START = 'OnBattleStart'
    ON_SHOT = 'OnShot'
    ON_BATTLE_RESULT = 'OnBattleResult'
    ON_LOOTBOX_OPEN = 'OnLootboxOpen'
    ON_MOE_INFO = 'OnMoeInfo'
    ON_COMP7_INFO = 'OnComp7Info'
    ON_ACCOUNT_STATS = 'OnAccountStats'

    HANGAR_EVENTS = [ON_LOOTBOX_OPEN, ON_MOE_INFO, ON_COMP7_INFO, ON_ACCOUNT_STATS]

  def __init__(self, event_name):
    self.eventName = event_name
    self.localtime = get_current_date()
    self.region = AUTH_REALM
    self.gameVersion = GAME_VERSION
    self.modVersion = config.get('version')

  def get_dict(self):
    return self.__dict__


class PlayerInfo(object):
  def __init__(self):
    self.playerName = None
    self.accountDBID = None
    self.playerClan = None
    self.playerClanDBID = None

  def setupPlayerInfo(self, playerName, accountDBID, playerClan, playerClanDBID):
    self.playerName = playerName
    self.accountDBID = accountDBID
    self.playerClan = playerClan
    self.playerClanDBID = playerClanDBID


class SessionMeta(object):
  def __init__(self):
    self.setupSessionMeta(0, 0, 0, 0, 0, 0, [], [], [], '', 0, 0)

  def setupSessionMeta(self, battleStarts, battleResults, winCount, totalShots, totalShotsDamaged, totalShotsHit,
                       lastResult, lastDmgPlace, lastXpPlace, sessionStart, lastBattleAgo, sessionStartAgo):
    self.sessionStart = sessionStart
    self.sessionStartAgo = sessionStartAgo
    self.lastBattleAgo = lastBattleAgo
    self.battleStarts = battleStarts
    self.battleResults = battleResults
    self.winCount = winCount
    self.totalShots = totalShots
    self.totalShotsDamaged = totalShotsDamaged
    self.totalShotsHit = totalShotsHit
    self.lastResult = list(lastResult)
    self.lastDmgPlace = list(lastDmgPlace)
    self.lastXpPlace = list(lastXpPlace)

class ServerInfo(object):
  def __init__(self):
    self.setupServerInfo('', 0, 0)
  
  def setupServerInfo(self, serverName, serverOnline, regionOnline):
    self.serverName = serverName
    self.serverOnline = serverOnline
    self.regionOnline = regionOnline

class HangarEvent(Event, PlayerInfo, ServerInfo, SessionMeta):
  def __init__(self, event_name):
    Event.__init__(self, event_name)
    PlayerInfo.__init__(self)
    ServerInfo.__init__(self)
    SessionMeta.__init__(self)


class BattleExtra(object):
  
  def __init__(self):
    self.extra = {}
    
  def setupExtra(self, extra):
    self.extra = extra

class DynamicBattleInfo(BattleExtra):
  def __init__(self):
    BattleExtra.__init__(self)
    self.arenaTag = None
    self.battleMode = None
    self.battleGameplay = None
    self.team = None
    self.tankTag = None
    self.tankType = None
    self.tankRole = None
    self.tankLevel = None
    self.gunTag = None
    self.comp7SkillTag = None
    self.allyTeamHealth = None
    self.enemyTeamHealth = None
    self.allyTeamMaxHealth = None
    self.enemyTeamMaxHealth = None
    self.allyTeamFragsCount = None
    self.enemyTeamFragsCount = None
    self.mapsBlackList = None
    self.equipment = None
    self.consumables = None
    self.battleBooster = None
    self.shells = None
    self.crew = None
    self.systemInfo = None

  def setupDynamicBattleInfo(self, arenaTag, battleMode, battleGameplay,
                             team, tankTag, tankType, tankRole, tankLevel, gunTag, comp7SkillTag, allyTeamHealth, enemyTeamHealth,
                             allyTeamMaxHealth, enemyTeamMaxHealth, allyTeamFragsCount, enemyTeamFragsCount, mapsBlackList,
                             equipment, consumables, battleBooster, shells, crew):
    self.arenaTag = arenaTag
    self.battleMode = battleMode
    self.battleGameplay = battleGameplay
    self.team = team
    self.tankTag = tankTag
    self.tankType = tankType
    self.tankRole = tankRole
    self.tankLevel = tankLevel
    self.gunTag = gunTag
    self.comp7SkillTag = comp7SkillTag
    self.allyTeamHealth = allyTeamHealth
    self.enemyTeamHealth = enemyTeamHealth
    self.allyTeamMaxHealth = allyTeamMaxHealth
    self.enemyTeamMaxHealth = enemyTeamMaxHealth
    self.allyTeamFragsCount = allyTeamFragsCount
    self.enemyTeamFragsCount = enemyTeamFragsCount
    self.mapsBlackList = mapsBlackList
    self.equipment = equipment
    self.consumables = consumables
    self.battleBooster = battleBooster
    self.shells = shells
    self.crew = crew

  def setupSystemInfo(self, info):
    self.systemInfo = info

class BattleEvent(Event, DynamicBattleInfo, PlayerInfo, ServerInfo, SessionMeta):
  def __init__(self, event_name, battleTime=None):
    Event.__init__(self, event_name)
    DynamicBattleInfo.__init__(self)
    PlayerInfo.__init__(self)
    ServerInfo.__init__(self)
    SessionMeta.__init__(self)
    
    if battleTime is not None:
      self.battleTime = battleTime


class OnBattleStart(BattleEvent):

  def __init__(self, arenaId, spawnPoint, battleTime,
               battlePeriod, loadTime, preBattleWaitTime, inQueueWaitTime, gameplayMask):
    BattleEvent.__init__(self, Event.NAMES.ON_BATTLE_START, battleTime)

    self.arenaID = arenaId
    self.spawnPoint = spawnPoint
    self.battlePeriod = battlePeriod
    self.loadTime = loadTime
    self.preBattleWaitTime = preBattleWaitTime
    self.inQueueWaitTime = inQueueWaitTime
    self.gameplayMask = gameplayMask


class OnShot(BattleEvent):
  class HIT_REASON:
    TANK = 'tank'
    TERRAIN = 'terrain'

  def __init__(self):
    BattleEvent.__init__(self, Event.NAMES.ON_SHOT)

    self.battleTime = None
    self.serverMarkerPoint = None
    self.clientMarkerPoint = None
    self.serverShotDispersion = None
    self.clientShotDispersion = None
    self.health = None

    self.shotId = None
    self.gunPoint = None
    self.battleDispersion = None
    self.gunDispersion = None
    self.shellTag = None
    self.shellName = None
    self.shellDamage = None
    self.damageRandomization = None
    self.shellCaliber = None
    self.shellPiercingPower = None
    self.shellSpeed = None
    self.shellMaxDistance = None
    self.ping = None
    self.fps = None
    self.serverAim = None
    self.autoAim = None

    self.tracerStart = None
    self.tracerEnd = None
    self.tracerVel = None
    self.acceleration = None

    self.hitVehicleDescr = None
    self.hitChassisDescr = None
    self.hitTurretDescr = None
    self.hitGunDescr = None
    self.hitTurretYaw = None
    self.hitTurretPitch = None
    self.hitSegment = None

    self.vehicleDescr = None
    self.chassisDescr = None
    self.turretDescr = None
    self.gunDescr = None
    self.turretYaw = None
    self.turretPitch = None

    self.shellDescr = None
    self.vehicleSpeed = None
    self.vehicleRotationSpeed = None
    self.turretSpeed = None

    self.hitPoint = None
    self.hitReason = None
    self.results = []

  def set_client_marker(self, position, dispersion):
    self.clientMarkerPoint = position
    self.clientShotDispersion = dispersion

  def set_server_marker(self, position, dispersion):
    self.serverMarkerPoint = position
    self.serverShotDispersion = dispersion

  def set_shoot(self, gun_position, health, battle_dispersion, shot_dispersion, shell_name, shell_tag, damage,
                damage_randomization, caliber, piercing_power, speed, max_distance, shell_descr, ping, fps, auto_aim,
                server_aim, vehicle_descr, chassis_descr, turret_descr, gun_descr, turret_yaw, turret_pitch,
                vehicle_speed, vehicle_rotation_speed, turret_speed):
    self.gunPoint = gun_position
    self.health = health
    self.battleDispersion = battle_dispersion
    self.gunDispersion = shot_dispersion
    self.shellTag = shell_tag
    self.shellName = shell_name
    self.shellDamage = damage
    self.damageRandomization = damage_randomization
    self.shellCaliber = caliber
    self.shellPiercingPower = piercing_power
    self.shellSpeed = speed
    self.shellMaxDistance = max_distance
    self.shellDescr = shell_descr

    self.vehicleSpeed = vehicle_speed
    self.vehicleRotationSpeed = vehicle_rotation_speed
    self.turretSpeed = turret_speed

    self.ping = ping
    self.fps = fps
    self.autoAim = auto_aim
    self.serverAim = server_aim

    self.vehicleDescr = vehicle_descr
    self.chassisDescr = chassis_descr
    self.turretDescr = turret_descr
    self.gunDescr = gun_descr
    self.turretYaw = turret_yaw
    self.turretPitch = turret_pitch

  def set_tracer(self, shot_id, start, velocity, acceleration):
    self.shotId = shot_id
    self.tracerStart = start
    self.tracerVel = velocity
    self.acceleration = acceleration

  def set_hit(self, position, reason):
    self.hitPoint = position
    self.hitReason = reason

  def set_tracer_end(self, position):
    self.tracerEnd = position

  def set_hit_extra(self, vehicle_descr, chassis_descr, turret_descr, gun_descr, turret_yaw, turret_pitch, segment):
    self.hitVehicleDescr = vehicle_descr
    self.hitChassisDescr = chassis_descr
    self.hitTurretDescr = turret_descr
    self.hitGunDescr = gun_descr
    self.hitTurretYaw = turret_yaw
    self.hitTurretPitch = turret_pitch
    self.hitSegment = segment

  def add_result(self, tankTag, flags, shotDamage, fireDamage, ammoBayDestroyed, health, fireHealth):
    self.results.append({'order': len(self.results),
                         'tankTag': tankTag,
                         'flags': flags,
                         'shotDamage': shotDamage,
                         'fireDamage': fireDamage,
                         'ammoBayDestroyed': ammoBayDestroyed,
                         'shotHealth': health,
                         'fireHealth': fireHealth})

  def set_battle_time(self, time):
    self.battleTime = time


class OnBattleResult(BattleEvent):
  def __init__(self):
    BattleEvent.__init__(self, Event.NAMES.ON_BATTLE_RESULT)
    self.result = None

  def set_result(self, result):
    self.result = result


class OnLootboxOpen(HangarEvent):
  def __init__(self, containerTag, openByTag, isOpenSuccess, openCount, openGroup, rerollCount, recordBoxCount=1):
    HangarEvent.__init__(self, Event.NAMES.ON_LOOTBOX_OPEN)
    self.containerTag = containerTag
    self.openCount = openCount
    self.recordBoxCount = recordBoxCount
    self.openGroup = openGroup
    self.openByTag = openByTag
    self.isOpenSuccess = isOpenSuccess
    self.rerollCount = rerollCount

  def setup(self, raw, parsed, claimed):
    self.raw = raw
    self.parsed = parsed
    self.claimed = claimed

class OnMoeInfo(HangarEvent):
  def __init__(self, tankTag, battleCount, moeDistribution):
    HangarEvent.__init__(self, Event.NAMES.ON_MOE_INFO)
    self.tankTag = tankTag
    self.battleCount = battleCount
    self.moeDistribution = moeDistribution

class OnComp7Info(HangarEvent):
  def __init__(self, season, rating, rank, leaderboardPosition):
    HangarEvent.__init__(self, Event.NAMES.ON_COMP7_INFO)
    self.season = season
    self.rating = rating
    self.rank = rank
    self.leaderboardPosition = leaderboardPosition

class OnAccountStats(HangarEvent):
  def __init__(self, credits, gold, crystal, equipCoin, bpCoin, eventCoin, freeXP, piggyBankCredits, piggyBankGold,
               premiumPlusExpiryTime, isPremiumPlus, isWotPlus, wotPlusTier, wotPlusExpiryTime, telecom):
    HangarEvent.__init__(self, Event.NAMES.ON_ACCOUNT_STATS)
    self.credits = credits
    self.gold = gold
    self.crystal = crystal
    self.equipCoin = equipCoin
    self.bpCoin = bpCoin
    self.eventCoin = eventCoin
    self.freeXP = freeXP
    self.isPremiumPlus = isPremiumPlus
    self.premiumPlusExpiryTime = premiumPlusExpiryTime
    self.isWotPlus = isWotPlus
    self.wotPlusTier = wotPlusTier
    self.wotPlusExpiryTime = wotPlusExpiryTime
    self.telecom = telecom
    self.piggyBankCredits = piggyBankCredits
    self.piggyBankGold = piggyBankGold

def get_current_date():
  return datetime.datetime.now().isoformat()  # TODO: Лучше брать серверное время танков, если такое есть
