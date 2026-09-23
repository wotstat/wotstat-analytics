from Event import Event
from debug_utils import LOG_CURRENT_EXCEPTION
from serverLogger import send_current_exception


def _report_current_exception():
  # Logging must not let a mod callback change the result of a game method.
  try: send_current_exception()
  except: pass
  try: LOG_CURRENT_EXCEPTION()
  except: pass


def with_exception_sending(f):
  def wrapper(*args, **kwargs):
    try:
      return f(*args, **kwargs)
    except:
      _report_current_exception()

  return wrapper


class SendExceptionEvent(Event):
  __slots__ = ()

  def __init__(self, manager=None):
    super(SendExceptionEvent, self).__init__(manager)

  def __call__(self, *args, **kwargs):
    for delegate in self[:]:
      try:
        delegate(*args, **kwargs)
      except:
        _report_current_exception()
