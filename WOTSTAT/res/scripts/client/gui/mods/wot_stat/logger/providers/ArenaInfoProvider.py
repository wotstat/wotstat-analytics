import BigWorld
from ..wotHookEvents import wotHookEvents
from helpers import dependency
from skeletons.gui.battle_session import IBattleSessionProvider
from ...common.exceptionSending import with_exception_sending


class VehicleInfo():
  def __init__(self, vid, health, maxHealth, team):
    self.vid = vid
    self.health = health
    self.maxHealth = maxHealth
    self.team = team

  def updateHealth(self, health):
    target = max(0, health)
    if self.health == target: return False
    self.health = target
    return True

  def isAlive(self):
    return self.health > 0


class ArenaInfoProvider():
  vehicles = {}  # type: dict[int, VehicleInfo]
  playerTeam = -1

  __arena = None

  allyTeamHealth = [0, 0]
  enemyTeamHealth = [0, 0]
  allyTeamFragsCount = 0
  enemyTeamFragsCount = 0

  sessionProvider = dependency.descriptor(IBattleSessionProvider)

  def __init__(self):
    wotHookEvents.PlayerAvatar_onEnterWorld += self.start
    wotHookEvents.Account_onBecomeNonPlayer += self.stop
    wotHookEvents.Vehicle_onEnterWorld += self.onVehicleEnter
    wotHookEvents.Vehicle_onHealthChanged += self.onHealthChanged
    self.sessionProvider.onBattleSessionStart += self.onBattleSessionStart
    self.sessionProvider.onBattleSessionStop += self.onBattleSessionStop

  def start(self, *a, **k):

    def waitVehicles():
      vehicles = BigWorld.player().arena.vehicles.items()
      if len(vehicles) == 0:
        BigWorld.callback(0.1, waitVehicles)
        return

      for vid, v in vehicles:
        if vid not in self.vehicles:
          self.tryUpdateVehicle(vid, v['maxHealth'], v['maxHealth'])

    waitVehicles()

  def stop(self, *a, **k):
    self.vehicles = {}
    self.playerTeam = -1
    self.allyTeamFragsCount = 0
    self.enemyTeamFragsCount = 0
    self.allyTeamHealth = [0, 0]
    self.enemyTeamHealth = [0, 0]

  @with_exception_sending
  def onBattleSessionStart(self):
    arena = BigWorld.player().arena
    arena.onVehicleAdded += self.onVehicleAdded
    arena.onVehicleUpdated += self.vehicleUpdated
    arena.onVehicleKilled += self.onVehicleKilled
    self.__arena = arena

  @with_exception_sending
  def onBattleSessionStop(self):
    arena = self.__arena
    if arena is None: return
    arena.onVehicleAdded -= self.onVehicleAdded
    arena.onVehicleUpdated -= self.vehicleUpdated
    arena.onVehicleKilled -= self.onVehicleKilled
    self.__arena = None

  def onVehicleEnter(self, obj, *a, **k):
    self.tryUpdateVehicle(obj.id, obj.health, obj.maxHealth)

  def onHealthChanged(self, obj, newHealth, oldHealth, *a, **k):
    self.tryUpdateVehicle(obj.id, newHealth, obj.maxHealth)

  def tryUpdateVehicle(self, vid, health, maxHealth=None):
    if vid not in self.vehicles:
      player = BigWorld.player()
      if vid in player.arena.vehicles:
        info = player.arena.vehicles[vid]
        self.vehicles[vid] = VehicleInfo(vid, health, maxHealth if maxHealth else info['maxHealth'], info['team'])
        self.calculateTeamHealth()
    else:
      if self.vehicles[vid].updateHealth(health):
        self.calculateTeamHealth()


  @with_exception_sending
  def onVehicleAdded(self, vehicleID):
    vehicle = BigWorld.entity(vehicleID)
    if vehicle is None: return
    self.tryUpdateVehicle(vehicleID, vehicle.health)

  @with_exception_sending
  def vehicleUpdated(self, vehicleID):
    vehicle = BigWorld.entity(vehicleID)
    if vehicle is None: return
    self.tryUpdateVehicle(vehicleID, vehicle.health)

  @with_exception_sending
  def onVehicleKilled(self, targetID, *a, **k):
    self.tryUpdateVehicle(targetID, 0)
    if targetID in self.vehicles:
      team = self.vehicles[targetID].team
      if team == self.playerTeam:
        self.enemyTeamFragsCount += 1
      else:
        self.allyTeamFragsCount +=1


  def calculateTeamHealth(self):
    self.allyTeamHealth = [0, 0]
    self.enemyTeamHealth = [0, 0]

    if self.playerTeam == -1:
      self.playerTeam = BigWorld.player().team

    for vid, v in self.vehicles.items():
      if v.team == self.playerTeam:
        self.allyTeamHealth[0] += max(0, v.health)
        self.allyTeamHealth[1] += v.maxHealth
      else:
        self.enemyTeamHealth[0] += max(0, v.health)
        self.enemyTeamHealth[1] += v.maxHealth
