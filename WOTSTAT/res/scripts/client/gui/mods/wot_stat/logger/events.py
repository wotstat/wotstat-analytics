# coding=utf-8

import datetime

import BigWorld  
from constants import AUTH_REALM
from ..load_mod import config
from ..common.crossGameUtils import readClientServerVersion

GAME_VERSION = readClientServerVersion()[1]


class Event:
  class NAMES:
    ON_BATTLE_START = 'OnBattleStart'
    ON_SHOT = 'OnShot'
    ON_BATTLE_RESULT = 'OnBattleResult'
    ON_LOOTBOX_OPEN = 'OnLootboxOpen'

    HANGAR_EVENTS = [ON_LOOTBOX_OPEN]
    

  def __init__(self, event_name):
    self.eventName = event_name
    self.localtime = get_current_date()
    self.region = AUTH_REALM
    self.gameVersion = GAME_VERSION
    self.modVersion = config.get('version')


  def get_dict(self):
    return self.__dict__


class SessionMeta(object):
  sessionStart = ''
  lastBattleAgo = 0
  sessionStartAgo = 0

  battleStarts = 0
  battleResults = 0
  winCount = 0
  totalShots = 0
  totalShotsDamaged = 0
  totalShotsHit = 0

  lastResult = []
  lastDmgPlace = []
  lastXpPlace = []

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


class BattleEvent(Event):
  def __init__(self, event_name, battleTime):
    Event.__init__(self, event_name)
    self.battleTime = battleTime


class HangarEvent(Event):
  def __init__(self, event_name):
    Event.__init__(self, event_name)

    self.playerName = None

  def setupHangarEvent(self, playerName):
    self.playerName = playerName


class BattleExtra():
  
  def __init__(self):
    self.extra = {}
    
  def setupExtra(self, extra):
    self.extra = extra

class DynamicBattleEvent(BattleEvent, BattleExtra):
  def __init__(self, event_name, battleTime):
    BattleEvent.__init__(self, event_name, battleTime)
    self.arenaTag = None
    self.playerName = None
    self.playerClan = None
    self.accountDBID = None
    self.battleMode = None
    self.battleGameplay = None
    self.serverName = None
    self.team = None
    self.tankTag = None
    self.tankType = None
    self.tankRole = None
    self.tankLevel = None
    self.gunTag = None
    self.allyTeamHealth = None
    self.enemyTeamHealth = None
    self.allyTeamMaxHealth = None
    self.enemyTeamMaxHealth = None
    self.allyTeamFragsCount = None
    self.enemyTeamFragsCount = None

  def setupDynamicBattleInfo(self, arenaTag, playerName, playerClan, accountDBID, battleMode, battleGameplay,
                             serverName, team, tankTag, tankType, tankRole, tankLevel,
                             gunTag, allyTeamHealth, enemyTeamHealth, allyTeamMaxHealth, enemyTeamMaxHealth,
                             allyTeamFragsCount, enemyTeamFragsCount):
    self.arenaTag = arenaTag
    self.playerName = playerName
    self.playerClan = playerClan
    self.accountDBID = accountDBID
    self.battleMode = battleMode
    self.battleGameplay = battleGameplay
    self.serverName = serverName
    self.team = team
    self.tankTag = tankTag
    self.tankType = tankType
    self.tankRole = tankRole
    self.tankLevel = tankLevel
    self.gunTag = gunTag
    self.allyTeamHealth = allyTeamHealth
    self.enemyTeamHealth = enemyTeamHealth
    self.allyTeamMaxHealth = allyTeamMaxHealth
    self.enemyTeamMaxHealth = enemyTeamMaxHealth
    self.allyTeamFragsCount = allyTeamFragsCount
    self.enemyTeamFragsCount = enemyTeamFragsCount


class OnBattleStart(DynamicBattleEvent, SessionMeta):

  def __init__(self, arenaId, spawnPoint, battleTime,
               battlePeriod, loadTime, preBattleWaitTime, inQueueWaitTime, gameplayMask):
    DynamicBattleEvent.__init__(self, Event.NAMES.ON_BATTLE_START, battleTime)

    self.arenaID = arenaId
    self.spawnPoint = spawnPoint
    self.battlePeriod = battlePeriod
    self.loadTime = loadTime
    self.preBattleWaitTime = preBattleWaitTime
    self.inQueueWaitTime = inQueueWaitTime
    self.gameplayMask = gameplayMask


class OnShot(DynamicBattleEvent, SessionMeta):
  class HIT_REASON:
    TANK = 'tank'
    TERRAIN = 'terrain'

  def __init__(self):
    DynamicBattleEvent.__init__(self, Event.NAMES.ON_SHOT, 0)

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
    self.gravity = None

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

  def set_tracer(self, shot_id, start, velocity, gravity):
    self.shotId = shot_id
    self.tracerStart = start
    self.tracerVel = velocity
    self.gravity = gravity

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


class OnBattleResult(DynamicBattleEvent, SessionMeta):
  result = None

  def __init__(self):
    DynamicBattleEvent.__init__(self, Event.NAMES.ON_BATTLE_RESULT, 0)

  def set_result(self, result):
    self.result = result


class OnLootboxOpen(HangarEvent, SessionMeta):
  def __init__(self, containerTag, openByTag, isOpenSuccess, openCount, openGroup, rerollCount):
    HangarEvent.__init__(self, Event.NAMES.ON_LOOTBOX_OPEN)
    self.containerTag = containerTag
    self.openCount = openCount
    self.openGroup = openGroup
    self.openByTag = openByTag
    self.isOpenSuccess = isOpenSuccess
    self.rerollCount = rerollCount

  def setup(self, raw, parsed, claimed):
    self.raw = raw
    self.parsed = parsed
    self.claimed = claimed

    
def get_current_date():
  return datetime.datetime.now().isoformat()  # TODO: Лучше брать серверное время танков, если такое есть
