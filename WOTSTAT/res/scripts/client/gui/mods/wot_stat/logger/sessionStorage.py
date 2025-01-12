import BigWorld
from .events import get_current_date
from .events import SessionMeta


def windowed_array_next(arr, length, value):
  while len(arr) >= length:
    arr.pop(0)

  arr.append(value)


class SessionStorage(object):
  _start_session_localtime = get_current_date()
  _start_session_time = BigWorld.time()
  _last_battle_start_time = 0
  _current_battle_start_time = 0

  _battle_starts = 0
  _battle_results = 0
  _win_count = 0
  _total_shots = 0
  _total_shots_damaged = 0
  _total_shots_hit = 0

  _last_10_result = []
  _last_10_dmg_place = []
  _last_10_xp_place = []

  def on_load_mod(self):
    pass

  def on_start_battle(self):
    self._battle_starts += 1
    self._last_battle_start_time = self._current_battle_start_time
    self._current_battle_start_time = BigWorld.time()

  def on_result_battle(self, result, player_team, player_bdid, players_results):
    self._battle_results += 1
    if result == 'win': self._win_count += 1
    windowed_array_next(self._last_10_result, 10, result)

    player_team = filter(lambda t: t['team'] == player_team, players_results)

    dmg_place = map(lambda t: t['bdid'], sorted(player_team, reverse=True,
                                                key=lambda t: t['damageDealt'])).index(player_bdid) + 1
    xp_place = map(lambda t: t['bdid'], sorted(player_team, reverse=True,
                                               key=lambda t: t['xp'])).index(player_bdid) + 1

    windowed_array_next(self._last_10_dmg_place, 10, dmg_place)
    windowed_array_next(self._last_10_xp_place, 10, xp_place)

  def on_shot(self, has_damage, has_direct_hit):
    self._total_shots += 1
    if has_damage: self._total_shots_damaged += 1
    if has_direct_hit: self._total_shots_hit += 1

  def setup_session_meta(self, sessionMeta): # type: (SessionMeta) -> None

    lastBattle = self._last_battle_start_time
    sessionMeta.setupSessionMeta(battleResults=self._battle_results, battleStarts=self._battle_starts,
                                 winCount=self._win_count, totalShots=self._total_shots,
                                 totalShotsDamaged=self._total_shots_damaged, totalShotsHit=self._total_shots_hit,
                                 lastResult=self._last_10_result, lastDmgPlace=self._last_10_dmg_place,
                                 lastXpPlace=self._last_10_xp_place, sessionStart=self._start_session_localtime,
                                 lastBattleAgo=int(BigWorld.time() - lastBattle) if lastBattle != 0 else 0,
                                 sessionStartAgo=int(BigWorld.time() - self._start_session_time))


sessionStorage = SessionStorage()
