import hashlib
import json
import os
import sys
import time
from traceback import format_exception

from typing import List

import BigWorld
import excepthook
from constants import AUTH_REALM
from debug_utils import _addTagsToMsg, _makeMsgHeader, LOG_CURRENT_EXCEPTION, _src_file_trim_to, _g_logLock
from .asyncResponse import post_async
from .crossGameUtils import readClientServerVersion

logger = None  # type: ServerLogger
modVersion = 'unknown'
__logs_queue = []

GAME_VERSION = readClientServerVersion()[1]

SERVERS_URL = [
  'https://loki.wotstat.info/loki/api/v1/push',
  'https://ru.loki.wotstat.info/loki/api/v1/push',
  'https://teleport-msk-1.openwg.net/loki.wotstat.info/loki/api/v1/push',
  'https://teleport-spb-1.openwg.net/loki.wotstat.info/loki/api/v1/push',
  'http://teleport-msk-1.openwg.net/loki.wotstat.info/loki/api/v1/push'
]
JSON_HEADERS = {'Content-type': 'application/json', 'Accept': 'application/json'}


def setupLogger(version):
  global logger, modVersion
  modVersion = version
  logger = ServerLogger()
  for log in __logs_queue:
    logger.send(log[0], log[1])


def send(level, msg):
  if logger:
    logger.send(level, msg)
  else:
    __logs_queue.append((level, msg))


def send_current_exception(tags=None, frame=1):
  msg = _makeMsgHeader(sys._getframe(frame)) + '\n'
  etype, value, tb = sys.exc_info()
  msg += ''.join(format_exception(etype, value, tb, None))
  with _g_logLock:
    line = ''
    line += '[EXCEPTION]' + _addTagsToMsg(tags, msg)
    extMsg = excepthook.extendedTracebackAsString(_src_file_trim_to, None, None, etype, value, tb)
    if extMsg:
      line += '[EXCEPTION]' + _addTagsToMsg(tags, extMsg)

  send(LEVELS.EXCEPTION, line)


def withExceptionHandling(l):
  try:
    l()
  except:
    send_current_exception()
    LOG_CURRENT_EXCEPTION()


def _generate_session_id():
  current_time = str(time.time()).encode('utf-8')
  random_bytes = os.urandom(16)
  unique_bytes = current_time + random_bytes
  session_id = hashlib.sha256(unique_bytes).hexdigest()

  return session_id


def _get_player_name():
  player = BigWorld.player()

  if not player: return 'unknown_player'
  if not hasattr(player, 'name'): return 'unknown_name'
  if not player.name: return 'unknown_name'
  return player.name


def _get_game_version():
  if not GAME_VERSION: return 'unknown_version'
  return GAME_VERSION


def _get_mod_version():
  return modVersion


def _get_region():
  return AUTH_REALM


class LEVELS:
  DEBUG = 'DEBUG'
  INFO = 'INFO'
  WARN = 'WARN'
  ERROR = 'ERROR'
  EXCEPTION = 'EXCEPTION'


LEVELS_NAMES = [LEVELS.DEBUG, LEVELS.INFO, LEVELS.WARN, LEVELS.ERROR, LEVELS.EXCEPTION]


class Message:
  def __init__(self, level, message):
    self.level = level if level in LEVELS_NAMES else LEVELS.INFO
    self.message = message if message else "empty"
    self.time = int(time.time() * 1e9)


class ServerLogger:

  def __init__(self):
    print("[WOTSTAT LOGGER]: Init server logger")
    self.session_id = _generate_session_id()
    self.logs_queue = []  # type: List[Message]
    self.urlIndex = 0

    self._sending_loop()

  def send(self, level, msg):
    self.logs_queue.append(Message(level, msg))

  def getUrl(self):
    return SERVERS_URL[self.urlIndex]

  def __onSendError(self, res):
    # type: (BigWorld.PyURLResponse) -> None
    print('[WOTSTAT LOGGER] sending error [%s] to %s' % (res.responseCode, self.getUrl()))
    self.urlIndex = (self.urlIndex + 1) % len(SERVERS_URL)

  def _sending_loop(self):
    BigWorld.callback(10, self._sending_loop)

    try:
      if len(self.logs_queue) == 0: return

      defaultStreamLabels = {
        "source": "mod",
        "region": _get_region(),
        "modVersion": _get_mod_version(),
      }

      defaultStreamMeta = {
        "playerName": _get_player_name(),
        "gameVersion": _get_game_version(),
        "session": self.session_id
      }

      streams = []

      for level in LEVELS_NAMES:
        current = filter(lambda l: l.level == level, self.logs_queue)
        if len(current) == 0: continue

        streams.append({
          "stream": dict(defaultStreamLabels, level=level),
          "values": map(lambda l: [str(l.time), l.message, defaultStreamMeta], current)
        })

      data = {"streams": streams}

      serializedData = json.dumps(data, ensure_ascii=False)
      post_async(self.getUrl(), headers=JSON_HEADERS, data=serializedData, error_callback=self.__onSendError)

    except:
      print("[WOTSTAT LOGGER EXCEPTION]")
      LOG_CURRENT_EXCEPTION()

    finally:
      self.logs_queue = []
