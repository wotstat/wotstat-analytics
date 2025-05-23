import BigWorld
import json
import re
import os
import shutil
import random
from datetime import datetime

from asyncResponse import get_async
from helpers import getShortClientVersion
from ..utils import print_log, print_warn, print_error
from .exceptionSending import with_exception_sending
from .crossGameUtils import gamePublisher, PUBLISHER


modExtension = '.mtmod' if gamePublisher() == PUBLISHER.LESTA else '.wotmod'

def num_game_version():
  return getShortClientVersion().split('v.')[1].strip()


@with_exception_sending
def update_game_version(modName, modVersion):
  
  def enumerateNextVersions(x, y):
    return '.'.join(
      [str(int(c) + 1 if i == y else 0) if i >= y else c for i, c in enumerate(x.split('.'))])

  def copyToVersion(targetVersion, sourcePath):
    if not os.path.exists(sourcePath): return
    
    targetName = os.path.basename(sourcePath)
    targetFolder = os.path.join(os.path.abspath('./mods/'), targetVersion)
    targetPath = os.path.join(targetFolder, targetName)
    
    if not os.path.exists(targetFolder): os.mkdir(targetFolder)
    if not os.path.exists(targetPath): shutil.copyfile(sourcePath, targetPath)
    
    oldModVersions = filter(lambda fileName: fileName.startswith(modName) and fileName.endswith(modExtension) and fileName != targetName, os.listdir(targetFolder))
    for oldModName in oldModVersions:
      os.remove(os.path.join(targetFolder, oldModName))
    

  gameVersion = num_game_version()
  nextGameVersions = [enumerateNextVersions(gameVersion, i) for i in range(1, len(gameVersion.split('.')))]
    
  for version in nextGameVersions:
    copyToVersion(version, os.path.join(os.path.abspath('./mods/'), gameVersion, modName + '_' + modVersion + modExtension))  


GH_headers = {
  'X-GitHub-Api-Version': '2022-11-28',
  'Accept': 'application/vnd.github+json'
}


@with_exception_sending
def update_mod_version(url, mod_name, current_version, on_start_update=None, on_updated=None, is_latest_version=None):
  latest_version = ''

  def end_load_mod(res):
    global latest_version

    gameVersion = num_game_version()
    newMod = os.path.join(os.path.abspath(
      './mods/'), gameVersion, mod_name + '_' + latest_version + modExtension)
    if not os.path.exists(newMod):
      with open(newMod, "wb") as f:
        f.write(res)

    if on_updated:
      on_updated(latest_version)

  @with_exception_sending
  def end_load_info(res):
    global latest_version

    data = json.loads(res)
    latest_version = data['tag_name']
    print_log('detect latest version: ' + latest_version)

    needDownloadLestaMigration = modExtension == '.mtmod' and num_game_version() == '1.34.0.0' and \
      not os.path.exists(os.path.join(os.path.abspath('./mods/'), '1.34.0.0', mod_name + '_' + latest_version + '.mtmod'))
      
    if current_version == latest_version and not needDownloadLestaMigration:
      if is_latest_version: is_latest_version()
      return

    if 'body' in data and data['body'] \
        and 'published_at' in data and data['published_at']:
      body = data['body']
      published_at = data['published_at']

      match = re.search('`canary_upgrade=(\d+|\d+.\d+)?`', body)
      num_canary_upgrade = float(match.group(1)) if match else None

      if num_canary_upgrade is not None:
        parsed_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.now()
        delta = now - parsed_date
        day_since_release = max(delta.days + 1, 1)

        update_fraction_today = 1 - (1 - num_canary_upgrade) ** day_since_release
        rnd = random.random()

        print_log('Update canary fraction today: %s; RND=%s' % (update_fraction_today, rnd))

        if rnd > update_fraction_today:
          if is_latest_version: is_latest_version()
          return

      else:
        print_error('can not parse canary upgrade')

    assets = data['assets']
    asset = filter(lambda x: ('name' in x) and (x['name'] == 'mod.wotStat_' + latest_version + modExtension), assets)
    if not len(asset) > 0: return

    firstAsset = asset[0]
    if 'browser_download_url' not in firstAsset: return

    downloadUrl = firstAsset['browser_download_url']
    print_log('Start download new version from: ' + downloadUrl)

    if on_start_update:
      on_start_update(latest_version)
    get_async(downloadUrl, None, end_load_mod)

  get_async(url, None, end_load_info, GH_headers)
