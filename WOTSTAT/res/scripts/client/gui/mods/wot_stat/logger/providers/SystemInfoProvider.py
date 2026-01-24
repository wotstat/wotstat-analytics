import BigWorld
import platform
from helpers.statistics import HARDWARE_SCORE_PARAMS
from gui.shared.utils import monitor_settings

from ...common.exceptionSending import with_exception_sending

@with_exception_sending
def getNativeResolution():
  monitorSettings = monitor_settings.g_monitorSettings
  currentMonitor = monitorSettings.currentMonitor

  try: res = BigWorld.getNativeScreenResolution(currentMonitor)
  except Exception:
    try: res =  BigWorld.wg_getNativeScreenResoulution(currentMonitor)
    except Exception: res = (0, 0, 0)

  if len(res) == 2: return (int(res[0]), int(res[1]), 0)
  elif len(res) == 3: return (int(res[0]), int(res[1]), int(res[2]))
  else: return (0, 0, 0)

@with_exception_sending
def getPlatform():
  try: system = platform.system()
  except Exception: system = 'unknown'

  try: version = platform.version()
  except Exception: version = 'unknown'

  try: machine = platform.machine()
  except Exception: machine = 'unknown'

  try: bits, linkage = platform.architecture()
  except Exception: bits, linkage = 'unknown', 'unknown'

  try: platformName = platform.platform()
  except Exception: platformName = 'unknown'

  return {
    'system': system,
    'version': version,
    'machine': machine,
    'architectureBits': bits,
    'architectureLinkage': linkage,
    'platform': platformName
  }

class SystemInfoProvider():

  def __init__(self):
    self.staticInfoCache = None

  def _getClientStatistics(self):
    try: return BigWorld.wg_getClientStatistics()
    except: return BigWorld.getClientStatistics()

  @with_exception_sending
  def getStaticInfo(self):

    if self.staticInfoCache:
      return self.staticInfoCache

    stat = self._getClientStatistics()
    self.staticInfoCache = {
      'isLaptop': bool(stat.get('isLaptop', 0)),
      'cpuVendor': stat.get('cpuVendor', 0),
      'cpuCores': stat.get('cpuCores', 0),
      'cpuFreq': stat.get('cpuFreq', 0),
      'cpuFamily': stat.get('cpuFamily', 0),
      'cpuName': stat.get('cpuName', '').strip('\x00').strip(),
      'workstationVendor': stat.get('workstationVendor', '').strip('\x00').strip(),
      'gpuVendor': stat.get('gpuVendor', 0),
      'gpuMemory': stat.get('gpuMemory', 0),
      'gpuFamily': stat.get('gpuFamily', 0),
      'gpuDriverVersion': stat.get('gpuDriverVersion', 0),
      'ramTotal': stat.get('ramTotal', 0),
      'gameDriveName': stat.get('gameHddName', '').strip(),
      'cpuScore': BigWorld.getAutoDetectGraphicsSettingsScore(HARDWARE_SCORE_PARAMS.PARAM_CPU_SCORE),
      'gpuScore': BigWorld.getAutoDetectGraphicsSettingsScore(HARDWARE_SCORE_PARAMS.PARAM_GPU_SCORE)
    }
    self.staticInfoCache.update(getPlatform())

    return self.staticInfoCache

  @with_exception_sending
  def getSystemInfo(self):

    windowMode = BigWorld.getWindowMode()
    windowModeLUT = {
      BigWorld.WindowModeWindowed: 'windowed', 
      BigWorld.WindowModeExclusiveFullscreen: 'fullscreen', 
      BigWorld.WindowModeBorderless: 'borderless'
    }

    monitorSettings = monitor_settings.g_monitorSettings
    resolutionContainer = monitorSettings.currentWindowSize
    if windowMode == BigWorld.WindowModeExclusiveFullscreen: resolutionContainer = monitorSettings.currentVideoMode
    elif windowMode == BigWorld.WindowModeBorderless: resolutionContainer = monitorSettings.currentBorderlessSize

    nativeWidth, nativeHeight, nativeRefreshRate = getNativeResolution()

    dynamicInfo = {
      'windowMode': windowModeLUT.get(windowMode, 'unknown'),
      'windowResolution': {
        'width': resolutionContainer.width,
        'height': resolutionContainer.height,
        'refreshRate': resolutionContainer.refreshRate if hasattr(resolutionContainer, 'refreshRate') else 0
      },
      'nativeResolution': {
        'width': nativeWidth,
        'height': nativeHeight,
        'refreshRate': nativeRefreshRate
      },
    }

    staticInfo = self.getStaticInfo()

    combined = {}
    combined.update(staticInfo)
    combined.update(dynamicInfo)

    return combined