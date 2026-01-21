import json

import BigWorld
from events import Event, OnBattleStart, OnBattleResult
from ..common.asyncResponse import post_async_api
from ..common.exceptionSending import with_exception_sending
from ..utils import print_log, print_debug

try:
  from ..common.crypto import encrypt
  print_log('import crypto')
except:
  from ..common.cryptoPlaceholder import encrypt
  print_log('import cryptoPlaceholder')


class BattleEventSession:
  send_queue = []
  token = None
  initURL = ''
  eventURL = ''
  send_interval = 5
  arenaID = None
  enable = False

  def __init__(self, event_URL, init_URL, on_end_load_event, sendInterval=5):
    # type: (str, str, OnBattleStart, float) -> None

    self.send_queue = []
    self.token = None
    self.initURL = init_URL
    self.eventURL = event_URL
    self.send_interval = sendInterval
    self.arenaID = on_end_load_event.arenaID
    self.enable = False

    data = json.dumps(on_end_load_event.get_dict())
    print_debug(data)
    post_async_api(self.initURL, encrypt(data), {}, self.__init_send_callback, attempt=3)

  def add_event(self, event):
    # type: (Event) -> None
    self.send_queue.append(event)

  def end_event_session(self, battle_result_event):
    # type: (OnBattleResult) -> None
    self.add_event(battle_result_event)
    self.enable = False

  def __init_send_callback(self, res):
    # type: (str) -> None
    self.token = res
    print_log('setToken: ' + str(res))
    if not self.enable:
      self.enable = True
      self.__send_event_loop()

  def __send_event_loop(self):
    for event in self.send_queue:
      event.token = self.token
    self.__post_events(self.send_queue)

    self.send_queue = []

    if self.enable:
      BigWorld.callback(self.send_interval, self.__send_event_loop)

  @with_exception_sending
  def __post_events(self, events, callback=None):
    if events and len(events) > 0:
      data = {
        'events': map(lambda t: t.get_dict(), events)
      }
      print_log(json.dumps(data))
      post_async_api(self.eventURL, encrypt(json.dumps(data)), {}, callback, attempt=0)


class HangarEventSession:
  def __init__(self, hangar_event_URL, sendInterval=5):
    self.send_queue = []
    self.eventURL = hangar_event_URL
    self.send_interval = sendInterval
    self.__send_event_loop()

  def add_event(self, event):
    self.send_queue.append(event)

  def __send_event_loop(self):
    BigWorld.callback(self.send_interval, self.__send_event_loop)
    self.__post_events(self.send_queue)
    self.send_queue = []

  @with_exception_sending
  def __post_events(self, events, callback=None):
    if events and len(events) > 0:
      data = {
        'events': map(lambda t: t.get_dict(), events)
      }
      print_debug(json.dumps(data))
      post_async_api(self.eventURL, encrypt(json.dumps(data)), {}, callback, attempt=0)