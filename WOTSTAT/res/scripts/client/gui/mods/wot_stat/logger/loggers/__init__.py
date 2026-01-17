import BigWorld

from debug_utils import LOG_CURRENT_EXCEPTION
from ...common.exceptionSending import send_current_exception    

# from ribbonsLogger import onRibbonsLogger
# from onShotReceiveLogger import onShotReceiveLogger

loggers = [
  'onBattleStartLogger',
  'onBattleResultLogger',
  'onShotLogger',
  'onLootboxLogger',
  'moeLogger',
  'comp7Logger',
  'accountStatsLogger',
]

pkg = __name__
for name in loggers:
  try: __import__(pkg + '.' + name, globals(), locals(), [name], -1)
  except Exception: 
    send_current_exception()
    LOG_CURRENT_EXCEPTION()