from helpers import dependency

def readClientServerVersion():
  try: 
    from account_shared import readClientServerVersion
    return readClientServerVersion()
  
  except ImportError:
    from version_utils import readClientServerVersion
    from helpers import clientVersionGetter
    from constants import AUTH_REALM
    req, ver = readClientServerVersion(clientVersionGetter)
    if len(ver.split('#')) == 2: ver = ver.split('#')[0]
    
    
    prefix = ''
    
    try:
      from realm import CURRENT_REALM, IS_CT
      if CURRENT_REALM == 'RU' and IS_CT: prefix = 'rpt_'
      if CURRENT_REALM == 'RU' and not IS_CT: prefix = 'ru_'
    except ImportError:
      pass   
    
    if AUTH_REALM == 'CT' and prefix == '': prefix = 'ct_'
    return (req, prefix + ver)
  
  
def getLootboxKeyNameByTokenID(tag):
  try:
    from skeletons.gui.game_control import IGuiLootBoxesController
    guiLootbox = dependency.instance(IGuiLootBoxesController) # type: IGuiLootBoxesController
    return guiLootbox.getKeyByTokenID(tag).userName
  except Exception:
    return None
  
def getLootboxKeyNameByID(tag):
  try:
    from skeletons.gui.game_control import IGuiLootBoxesController
    guiLootbox = dependency.instance(IGuiLootBoxesController) # type: IGuiLootBoxesController
    return guiLootbox.getKeyByID(tag).userName
  except Exception:
    return None
  
def lootboxKeyPrefix():
  try:
    from constants import LOOTBOX_KEY_PREFIX
    return LOOTBOX_KEY_PREFIX
  except ImportError:
    return 'lb_key:'
  
class PUBLISHER():
  LESTA = 'LESTA'
  WARGAMING = 'WARGAMING'

def gamePublisher():
  from realm import CURRENT_REALM
  return PUBLISHER.LESTA if CURRENT_REALM == 'RU' else PUBLISHER.WARGAMING