# -*- coding: utf-8 -*-
import json

import BigWorld
from .common.config import Config
configPath = './mods/configs/wot_stat/config.cfg'
config = Config(configPath)  # type: Config

from gui import SystemMessages
from .common.modAutoUpdate import update_game_version, update_mod_version
from .common.modNotification import show_notification, show_open_web_browser, on_hangar_loaded, \
  OPEN_PERSONAL_WOTSTAT_EVENT
from .common.asyncResponse import get_async
from .common.i18n import t

from .utils import print_log, print_error
from .logger.wotHookEvents import wotHookEvents
from .logger.sessionStorage import sessionStorage
from .logger.extra.ExtraCollector import ExtraCollector
from .common.serverLogger import setupLogger, send
from .thirdParty.FixedBattleResultsCache import setup as setupFixedBattleResultsCache

MOD_NAME_PREFIX = 'mod.wotStat'

api_server_time = None


def mod_name_version(version):
  return MOD_NAME_PREFIX + '_' + version


def mod_name():
  return mod_name_version(config.get('version'))


def on_status_check(res):
  global api_server_time

  try:
    data = json.loads(res)
    print_log('Server status: %s' % data)
    api_server_time = data['time']
    hello_message()
  except Exception as e:
    print_error(e)
    api_server_time = None


def on_hangar_loaded_event():
  BigWorld.callback(1, on_hangar_loaded)


def on_connected(*a, **k):
  def on_account_login(*a, **k):
    wotHookEvents.Account_onBecomePlayer -= on_account_login
    hello_message()

  if not BigWorld.player():
    wotHookEvents.Account_onBecomePlayer += on_account_login
  else:
    hello_message()


def hello_message():
  if not api_server_time: return
  if not BigWorld.player(): return

  target_url = 'wotstat.info/session?mode=any&nickname=%s&from=%s' % (BigWorld.player().name, api_server_time)
  print_log(target_url)

  try:
    from gui.modsListApi import g_modsListApi

    def callback():
      show_open_web_browser('https://' + target_url)

    g_modsListApi.addModification(
      id="wotstat_info",
      name=t('modslist.title'),
      description=t('modslist.description'),
      icon='gui/maps/wot_stat/modsListApi.png',
      enabled=True,
      login=False,
      lobby=True,
      callback=callback
    )
  except:
    print_log('g_modsListApi not found')

  show_notification(t('helloNotification') % (OPEN_PERSONAL_WOTSTAT_EVENT + 'https://' + target_url, target_url),
                    message_type=SystemMessages.SM_TYPE.GameGreeting)


def init_mod():
  print_log('version ' + config.get('version'))
  setupLogger(config.get('lokiURL'), config.get('version'))

  def update_end(version):
    show_notification(t('modUpdated') % version, message_type=SystemMessages.SM_TYPE.Warning)

  def on_status_check_fail(e):
    print_log(e)
    show_notification(t('serverNotResponse'), message_type=SystemMessages.SM_TYPE.ErrorSimple)

  get_async(config.get('statusURL'), callback=on_status_check, error_callback=on_status_check_fail)

  if not config.get('disableCopyToFuture'):
    update_game_version(MOD_NAME_PREFIX, config.get('version'))
  
  if not config.get('disableAutoUpdate'):
    update_mod_version(config.get('updateURL'), MOD_NAME_PREFIX,
                       config.get('version'),
                       on_start_update=lambda version: print_log('Found new mod version ' + version),
                       on_updated=update_end)

  sessionStorage.on_load_mod()
  ExtraCollector.instance().setup()
  wotHookEvents.onConnected += on_connected
  wotHookEvents.onHangarLoaded += on_hangar_loaded_event

  BigWorld.callback(0, injectBattleResultFix)

def injectBattleResultFix():
  print_log("BattleResultFix: %s" % setupFixedBattleResultsCache())



send("INFO", 'Mod init')
