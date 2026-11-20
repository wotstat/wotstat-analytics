import BigWorld

from ...common.exceptionSending import with_exception_sending

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
  'onRaccoonRaidLogger',
]


@with_exception_sending
def _load_logger(name):
  __import__(__name__ + '.' + name, globals(), locals(), [name], -1)


for name in loggers:
  _load_logger(name)
