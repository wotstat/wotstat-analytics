import BigWorld
from .common.serverLogger import send, LEVELS


def print_log(log):
  print("%s [WOTSTAT_ANALYTICS]: %s" % (BigWorld.serverTime(), str(log)))
  send(LEVELS.INFO, str(log))


def print_error(log):
  print("%s [WOTSTAT_ANALYTICS ERROR]: %s" % (BigWorld.serverTime(), str(log)))
  send(LEVELS.ERROR, str(log))


def print_warn(log):
  print("%s [WOTSTAT_ANALYTICS WARN]: %s" % (BigWorld.serverTime(), str(log)))
  send(LEVELS.WARN, str(log))


def print_debug(log):
  if DEBUG_MODE:
    print("%s [WOTSTAT_ANALYTICS DEBUG]: %s" % (BigWorld.serverTime(), str(log)))
