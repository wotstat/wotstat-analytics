# coding=utf-8

import BigWorld
from ..utils import print_debug
from constants import SPECIAL_VEHICLE_HEALTH, VEHICLE_HIT_FLAGS as VHF
import math

EVENT_TIMEOUT = 10


class ShotEventCollector:
  class Event:
    HIDE_TRACER = 0
    TERRAIN_HIT = 1
    TANK_HIT = 2
    SHOT_RESULT = 3
    SHOT_DAMAGE = 4
    FIRE_DAMAGE = 5

    def __init__(self, type, data):
      self.type = type
      self.data = data
      self.time = BigWorld.serverTime()

  class EventCollector:
    def __init__(self, shotID, velocity):
      self.shotID = shotID

      self.horizontal_speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2)

      self.vehicle_result = dict()
      self.vehicle_wait_first_direct_hit = None
      self.vehicle_wait_ricocheted_direct_hit = []
      self.vehicle_wait_damage = []
      self.vehicle_in_fire = []
      self.vehicle_wait_killed_damage = []
      self.ricochet_count = 0

      self.damages = []
      self.shot_results = []
      self.fire_damages = dict()
      self.hit_extra = None
      self.direct_hit_point = None
      self.terrain_hit_point = None
      self.hide_tracer_point = None

      self.hide_tracer_time = 0
      self.can_hit = False

      self.shot_time = BigWorld.serverTime()
      self.last_event_time = self.shot_time

    def execute(self, event):
      if self.has_result():
        return False

      data = event.data
      res = False
      if event.type == ShotEventCollector.Event.SHOT_RESULT:
        res = self._shot_result(data.get('vehicleID'), data.get('flags'), data.get('health'))
      elif event.type == ShotEventCollector.Event.SHOT_DAMAGE:
        res = self._shot_damage(data.get('vehicleID'), data.get('newHealth'), data.get('oldHealth'))
      elif event.type == ShotEventCollector.Event.TANK_HIT:
        res = self._tank_hit(data.get('vehicleID'), data.get('point'), data.get('extra'))
      elif event.type == ShotEventCollector.Event.TERRAIN_HIT:
        res = self._terrain_hit(data.get('shotID'), data.get('point'))
      elif event.type == ShotEventCollector.Event.HIDE_TRACER:
        res = self._hide_tracer(data.get('shotID'), data.get('point'))
      elif event.type == ShotEventCollector.Event.FIRE_DAMAGE:
        res = self._fire_damage(data.get('vehicleID'), data.get('newHealth'), data.get('oldHealth'))

      if res:
        self.last_event_time = BigWorld.serverTime()
      return res

    def _hide_tracer(self, shotID, point):
      if self.shotID == abs(shotID):
        if not self.hide_tracer_point:
          self.hide_tracer_point = point
          self.hide_tracer_time = BigWorld.serverTime()
        return True
      return False

    def _terrain_hit(self, shotID, point):
      if self.shotID == shotID:
        if not self.terrain_hit_point:
          self.terrain_hit_point = point
        return True
      return False

    def _tank_hit(self, vehicleID, point, extra):
      if self.vehicle_wait_first_direct_hit == vehicleID and not self.direct_hit_point:
        self.direct_hit_point = point
        self.hit_extra = extra
        return True

      if self.vehicle_wait_ricocheted_direct_hit == vehicleID:
        return True

      return False

    def _shot_result(self, vehicleID, flags, health):

      def add_result():
        self.vehicle_result[vehicleID] = flags
        self.shot_results.append({'vehicleID': vehicleID, 'flags': flags})
        self.ricochet_count += is_ricochet
        if flags & (
            VHF.MATERIAL_WITH_POSITIVE_DF_PIERCED_BY_PROJECTILE | VHF.MATERIAL_WITH_POSITIVE_DF_PIERCED_BY_EXPLOSION):
          if flags & VHF.VEHICLE_KILLED:
            self.vehicle_wait_killed_damage.append(vehicleID)
          else:
            self.vehicle_wait_damage.append(vehicleID)
        else:
          print_debug("NOT PIERCED")
          self.damages.append(
            {'vehicleID': vehicleID, 'newHealth': max(0, health), 'damage': 0, 'ammo_bay_destr': False})
        return True

      after_ricochet = bool(flags & VHF.ATTACK_IS_RICOCHET_PROJECTILE)

      if vehicleID in self.vehicle_result \
          and after_ricochet \
          and self.ricochet_count > 0 \
          and self.vehicle_result[vehicleID] == flags:
        return True

      if vehicleID not in self.vehicle_result:
        is_ricochet = bool(flags & VHF.RICOCHET)
        direct = bool(flags & VHF.ATTACK_IS_DIRECT_PROJECTILE)
        explosion = bool(flags & VHF.ATTACK_IS_EXTERNAL_EXPLOSION)
        fire_start = bool(flags & VHF.FIRE_STARTED)

        if fire_start and fire_start not in self.vehicle_in_fire:
          self.vehicle_in_fire.append(vehicleID)

        if direct and not after_ricochet:
          if not self.vehicle_wait_first_direct_hit:
            self.vehicle_wait_first_direct_hit = vehicleID
            return add_result()

        elif direct and after_ricochet:
          if self.ricochet_count > 0:
            self.vehicle_wait_ricocheted_direct_hit.append(vehicleID)
            return add_result()

        elif explosion:
          return add_result()

      return False

    def _shot_damage(self, vehicleID, newHealth, oldHealth):
      damage = oldHealth - max(0, newHealth)
      kill = newHealth <= 0

      collection = None
      if kill and vehicleID in self.vehicle_wait_killed_damage:
        collection = self.vehicle_wait_killed_damage

      if not kill and vehicleID in self.vehicle_wait_damage:
        collection = self.vehicle_wait_damage

      if collection:
        collection.remove(vehicleID)
        ammo_bay_destr = SPECIAL_VEHICLE_HEALTH.IS_AMMO_BAY_DESTROYED(
          newHealth) or SPECIAL_VEHICLE_HEALTH.IS_TURRET_DETACHED(newHealth)
        self.damages.append({'vehicleID': vehicleID,
                             'newHealth': max(0, newHealth),
                             'damage': damage,
                             'ammo_bay_destr': ammo_bay_destr})
        return True

      return False

    def _fire_damage(self, vehicleID, newHealth, oldHealth):
      if vehicleID in self.vehicle_in_fire:
        if vehicleID not in self.fire_damages:
          self.fire_damages[vehicleID] = {'vehicleID': vehicleID,
                                          'newHealth': max(0, newHealth),
                                          'damage': 0,
                                          'ammo_bay_destr': False}

        damage = oldHealth - max(0, newHealth)
        ammo_bay_destr = SPECIAL_VEHICLE_HEALTH.IS_AMMO_BAY_DESTROYED(
          newHealth) or SPECIAL_VEHICLE_HEALTH.IS_TURRET_DETACHED(newHealth)
        self.fire_damages[vehicleID]['damage'] += damage
        self.fire_damages[vehicleID]['newHealth'] = max(0, newHealth)

        if ammo_bay_destr:
          self.fire_damages[vehicleID]['ammo_bay_destr'] = True

        return True
      return False

    def has_result(self):
      dam = len(self.damages)
      wait_dam = len(self.vehicle_wait_damage)
      wait_kill_dam = len(self.vehicle_wait_killed_damage)
      wait_dmg = wait_dam + wait_kill_dam
      delta = BigWorld.serverTime() - self.last_event_time
      if delta > 0.2:
        if wait_dmg == 0:
          if dam > 0:
            if self.vehicle_wait_first_direct_hit and self.direct_hit_point or not self.vehicle_wait_first_direct_hit and self.terrain_hit_point:
              if self.hide_tracer_point:
                if len(self.vehicle_in_fire) == 0:
                  return 1
                elif delta > 0.8:
                  return 2
              elif delta > 0.4:
                return 3

            if self.vehicle_wait_first_direct_hit and not self.direct_hit_point and delta > 1:
              return 4

          elif len(self.vehicle_result) == 0 or not self.vehicle_wait_first_direct_hit:
            if self.hide_tracer_point and self.terrain_hit_point:
              return 5
            if self.hide_tracer_point:
              if self.can_hit and delta > 2.5:
                return 6
              elif not self.can_hit and delta > 0.4:
                return 7
            if not self.hide_tracer_point and delta > self.horizontal_speed * 1000 + 0.4:
              return 8

          elif self.vehicle_wait_first_direct_hit:
            if self.hide_tracer_point and self.direct_hit_point:
              return 9
            if self.direct_hit_point and delta > 0.4:
              return 10

      if delta > 5:
        return 400
      return False

    def get_result(self):
      status = self.has_result()
      if status:
        return {
          'shotID': self.shotID,
          'status': status,
          'tank_hit_point': self.direct_hit_point,
          'tank_hit_extra': self.hit_extra,
          'terrain_hit_point': None if self.direct_hit_point else self.terrain_hit_point,
          'tracer_end_point': self.hide_tracer_point,
          'total_damage': sum(map(lambda t: t['damage'], self.damages)),
          'damages': self.damages,
          'fire_damages': self.fire_damages.values(),
          'shot_results': self.shot_results
        }

      return None

  def __init__(self):
    self.on_shot_loggers = dict()
    self.on_shot_loggers_order = []

    self.session_events = []

  def get_result(self):
    need_to_remove = []
    results = []
    for t in self.on_shot_loggers:
      res = self.on_shot_loggers[t].get_result()
      if res:
        need_to_remove.append(t)
        results.append(res)

    for t in need_to_remove:
      self.on_shot_loggers.pop(t)
      self.on_shot_loggers_order.remove(t)

    return results

  def process_events(self):
    need_to_remove = []
    time = BigWorld.serverTime()

    for event in self.session_events:
      if time - event.time > EVENT_TIMEOUT:
        print_debug("event timeout: %s" % str(event.type))
        need_to_remove.append(event)
        continue

      for shot_logger in self.on_shot_loggers_order:
        if self.on_shot_loggers[shot_logger].execute(event):
          need_to_remove.append(event)
          break

      if event.type == ShotEventCollector.Event.TANK_HIT:
        for shot_logger in self.on_shot_loggers_order:
          t = self.on_shot_loggers[shot_logger]
          if abs(event.time - t.hide_tracer_time) < 0.3 and abs(event.time - t.shot_time) > 0:
            self.on_shot_loggers[shot_logger].can_hit = True
            break

    for event in need_to_remove:
      self.session_events.remove(event)

  def append_event(self, event):
    if event:
      self.session_events.append(event)
      self.process_events()

  def show_tracer(self, shotID, start, velocity, shot_click_time):

    print_debug('[show_tracer] shotID: %d' % shotID)
    if BigWorld.serverTime() - shot_click_time < 5 and shotID not in self.on_shot_loggers:
      self.on_shot_loggers[shotID] = self.EventCollector(shotID, velocity)
      self.on_shot_loggers_order.append(shotID)

  def hide_tracer(self, shotID, point):
    print_debug('[hide_tracer] shotID: %d' % shotID)
    self.append_event(ShotEventCollector.Event(
      ShotEventCollector.Event.HIDE_TRACER, {'shotID': shotID, 'point': point}))

  def terrain_hit(self, shotID, point):
    print_debug('[terrain_hit] shotID: %d' % shotID)
    self.append_event(ShotEventCollector.Event(
      ShotEventCollector.Event.TERRAIN_HIT, {'shotID': shotID, 'point': point}))

  def tank_hit(self, vehicleID, point, extra=None):
    print_debug('[tank_hit] vehicle: %s' % vehicleID)
    self.append_event(ShotEventCollector.Event(ShotEventCollector.Event.TANK_HIT,
                                               {'vehicleID': vehicleID, 'point': point, 'extra': extra}))

  def shot_result(self, vehicleID, flags, health):
    print_debug(
      '[shot_result] vehicle: %s; isDead: %s, direct: %s; ricochet: %s; damage: %s; crits: %s; kill: %s; fire: %s; flags: %d' % (
        vehicleID,
        not bool(flags & VHF.VEHICLE_WAS_DEAD_BEFORE_ATTACK),
        not bool(flags & VHF.ATTACK_IS_RICOCHET_PROJECTILE),
        bool(flags & VHF.RICOCHET),
        bool(flags & (VHF.MATERIAL_WITH_POSITIVE_DF_PIERCED_BY_PROJECTILE |
                      VHF.MATERIAL_WITH_POSITIVE_DF_PIERCED_BY_EXPLOSION)),
        bool(flags & (VHF.DEVICE_PIERCED_BY_PROJECTILE | VHF.DEVICE_PIERCED_BY_EXPLOSION)),
        bool(flags & VHF.VEHICLE_KILLED),
        bool(flags & VHF.FIRE_STARTED),
        flags
      ))

    if flags & VHF.VEHICLE_WAS_DEAD_BEFORE_ATTACK: return
    self.append_event(ShotEventCollector.Event(ShotEventCollector.Event.SHOT_RESULT,
                                               {'vehicleID': vehicleID, 'flags': flags, 'health': health}))

  def shot_damage(self, vehicleID, newHealth, oldHealth):
    print_debug('[shot_damage] vehicle: %s; damage: %s; kill: %s; ammo_bay_destr: %s; newHealth: %s; oldHealth: %s' % (
      vehicleID,
      oldHealth - max(0, newHealth),
      newHealth <= 0,
      SPECIAL_VEHICLE_HEALTH.IS_AMMO_BAY_DESTROYED(
        newHealth) or SPECIAL_VEHICLE_HEALTH.IS_TURRET_DETACHED(newHealth),
      newHealth,
      oldHealth
    ))
    self.append_event(ShotEventCollector.Event(ShotEventCollector.Event.SHOT_DAMAGE, {
      'vehicleID': vehicleID, 'newHealth': newHealth, 'oldHealth': oldHealth}))

  def fire_damage(self, vehicleID, newHealth, oldHealth):
    print_debug('[fire_damage] vehicle: %s; damage: %s; kill: %s; ammo_bay_destr: %s; newHealth: %s; oldHealth: %s' % (
      vehicleID,
      oldHealth - max(0, newHealth),
      newHealth <= 0,
      SPECIAL_VEHICLE_HEALTH.IS_AMMO_BAY_DESTROYED(
        newHealth) or SPECIAL_VEHICLE_HEALTH.IS_TURRET_DETACHED(newHealth),
      newHealth,
      oldHealth
    ))
    self.append_event(ShotEventCollector.Event(ShotEventCollector.Event.FIRE_DAMAGE, {
      'vehicleID': vehicleID, 'newHealth': newHealth, 'oldHealth': oldHealth}))


shotEventCollector = ShotEventCollector()
