# coding=utf-8
import BigWorld
from gui import SystemMessages
from gui.DialogsInterface import showDialog
from gui.Scaleform.daapi.view.dialogs import DIALOG_BUTTON_ID
from gui.Scaleform.daapi.view.dialogs import SimpleDialogMeta
from notification.actions_handlers import NotificationsActionsHandlers
from .exceptionSending import with_exception_sending
from ..utils import print_log
from .i18n import t

OPEN_PERSONAL_WOTSTAT_EVENT = 'OPEN_PERSONAL_WOTSTAT_EVENT_'

openWebBrowser = BigWorld.wg_openWebBrowser if hasattr(BigWorld, 'wg_openWebBrowser') else BigWorld.openWebBrowser 


class UrlDialogButtons(object):
  def getLabels(self):
    return [
      {'id': DIALOG_BUTTON_ID.SUBMIT, 'label': t('openDialog.openButton'), 'focused': True},
      {'id': DIALOG_BUTTON_ID.CLOSE, 'label': t('openDialog.cancelButton'), 'focused': False}
    ]


@with_exception_sending
def show_url_dialog(title=None, message=None, url=None):
  meta = SimpleDialogMeta(title=title, message=message, buttons=UrlDialogButtons())
  showDialog(meta, lambda proceed: openWebBrowser(url) if proceed else None)


def show_open_web_browser(url):
  show_url_dialog(t('openDialog.title'), t('openDialog.body'), url)


@with_exception_sending
def __wotstat_events_handleAction(self, model, typeID, entityID, actionName):
  try:
    if actionName.startswith(OPEN_PERSONAL_WOTSTAT_EVENT):
      target = actionName.split(OPEN_PERSONAL_WOTSTAT_EVENT)[1]
      show_open_web_browser(target)
    else:
      old_handleAction(self, model, typeID, entityID, actionName)
  except:
    old_handleAction(self, model, typeID, entityID, actionName)


old_handleAction = NotificationsActionsHandlers.handleAction
NotificationsActionsHandlers.handleAction = __wotstat_events_handleAction

is_hangar_loaded = False
notification_queue = []


@with_exception_sending
def show_notification(msg, message_type=SystemMessages.SM_TYPE.Information):
  if is_hangar_loaded:
    print_log('show notification: %s. With type: %s' % (msg, message_type))
    SystemMessages.pushMessage(msg, type=message_type)
  else:
    notification_queue.append((msg, message_type))


def on_hangar_loaded():
  global is_hangar_loaded

  if not is_hangar_loaded:
    is_hangar_loaded = True
    for notification in notification_queue:
      show_notification(notification[0], notification[1])
