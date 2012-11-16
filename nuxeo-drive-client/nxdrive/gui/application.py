"""Main QT application handling OS events and system tray UI"""

import os
from threading import Thread
from nxdrive.protocol_handler import parse_protocol_url
from nxdrive.logging_config import get_logger
from nxdrive.gui.resources import find_icon
from nxdrive.gui.authentication import prompt_authentication
from nxdrive.controller import default_nuxeo_drive_folder

log = get_logger(__name__)

# Keep QT an optional dependency for now
QtGui, QApplication, QObject = None, object, object
try:
    from PySide import QtGui
    from PySide import QtCore
    QApplication = QtGui.QApplication
    QObject = QtCore.QObject
    log.debug("QT / PySide successfully imported")
except ImportError:
    log.warning("QT / PySide is not installed: GUI is disabled")
    pass


class Communicator(QObject):
    """Handle communication between sync and main GUI thread

    Use a signal to notify the main thread event loops about states update by
    the synchronization thread.

    """
    # (event name, new icon, rebuild menu)
    icon = QtCore.Signal(str)
    menu = QtCore.Signal()
    stop = QtCore.Signal()
    invalid_token = QtCore.Signal(str)


class BindingInfo(object):
    """Summarize the state of each server connection"""

    online = True

    n_pending = 0

    has_more_pending = False

    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.short_name = os.path.basename(folder_path)

    def get_status_message(self):
        # TODO: i18n
        if self.online:
            if self.n_pending != 0:
                return "%d%s pending operations" % (
                    self.n_pending, '+' if self.has_more_pending else '')
            else:
                return "Up-to-date"
        else:
            return "Offline"

    def __str__(self):
        return "%s: %s" % (self.short_name, self.get_status_message())


def sync_loop(controller, **kwargs):
    """Wrapper to log uncaught exception in the sync thread"""
    try:
        controller.loop(**kwargs)
    except Exception, e:
        log.error("Error in synchronization thread: %s", e, exc_info=True)


class Application(QApplication):
    """Main Nuxeo drive application controlled by a system tray icon + menu"""

    sync_thread = None

    def __init__(self, controller, options, argv=()):
        super(Application, self).__init__(list(argv))
        self.controller = controller
        self.options = options

        # Put communication channel in place for intra and inter-thread
        # communication for UI change notifications
        self.communicator = Communicator()
        self.communicator.icon.connect(self.set_icon)
        self.communicator.menu.connect(self.rebuild_menu)
        self.communicator.stop.connect(self.handle_stop)
        self.communicator.invalid_token.connect(self.update_credentials)

        # This is a windowless application mostly using the system tray
        self.setQuitOnLastWindowClosed(False)
        self.state = 'paused'
        self.quit_on_stop = False
        self.binding_info = {}
        self._setup_systray()
        self.rebuild_menu()

        # Start long running synchronization thread
        self.start_synchronization_thread()

    def get_info(self, local_folder):
        info = self.binding_info.get(local_folder, None)
        if info is None:
            info = BindingInfo(local_folder)
            self.binding_info[local_folder] = info
        return info

    @QtCore.Slot(str)
    def set_icon(self, state):
        """Execute systray icon change operations triggered by state change

        The synchronization thread can update the state info but cannot
        directly call QtGui widget methods. The should be executed by the main
        thread event loop, hence the delegation to this method that is
        triggered by a signal to allow for message passing between the 2
        threads.

        """
        icon = find_icon('nuxeo_drive_systray_icon_%s_18.png' % state)
        if icon is not None:
            self._tray_icon.setIcon(QtGui.QIcon(icon))
        else:
            log.warning('Icon not found: %s', icon)

    def action_quit(self):
        self.communicator.icon.emit('stopping')
        self.state = 'quitting'
        self.quit_on_stop = True
        self.communicator.menu.emit()
        if self.sync_thread is not None and self.sync_thread.isAlive():
            # Ask the conntroller to stop: the synchronization loop will in turn
            # call notify_sync_stopped and finally handle_stop
            self.controller.stop()
        else:
            # quit directly
            self.quit()

    @QtCore.Slot()
    def handle_stop(self):
        if self.quit_on_stop:
            self.quit()

    def update_running_icon(self):
        if self.state != 'running':
            self.communicator.icon.emit('disabled')
            return
        infos = self.binding_info.values()
        if len(infos) > 0 and any(i.online for i in infos):
            self.communicator.icon.emit('enabled')
        else:
            self.communicator.icon.emit('disabled')

    def notify_local_folders(self, local_folders):
        """Cleanup unbound server bindings if any"""
        refresh = False
        for registered_folder in self.binding_info.keys():
            if registered_folder not in local_folders:
                del self.binding_info[registered_folder]
                refresh = True
        for local_folder in local_folders:
            if local_folder not in self.binding_info:
                self.binding_info[local_folder] = BindingInfo(local_folder)
                refresh = True
        if refresh:
            self.communicator.menu.emit()
            self.update_running_icon()

    def notify_sync_started(self):
        self.state = 'running'
        self.communicator.menu.emit()
        self.update_running_icon()

    def notify_sync_stopped(self):
        self.state = 'paused'
        self.sync_thread = None
        self.update_running_icon()
        self.communicator.menu.emit()
        self.communicator.stop.emit()

    def notify_offline(self, local_folder, exception):
        info = self.get_info(local_folder)
        if info.online:
            # Mark binding as offline and update UI
            info.online = False
            self.update_running_icon()
            self.communicator.menu.emit()
        if getattr(exception, 'code', None) == 401:
            self.communicator.invalid_token.emit(local_folder)

    def notify_pending(self, local_folder, n_pending, or_more=False):
        info = self.get_info(local_folder)
        info.online = True
        if not info.online:
            # Mark binding as online and update UI
            self.update_running_icon()
            self.communicator.menu.emit()

    def _setup_systray(self):
        self._tray_icon = QtGui.QSystemTrayIcon()
        self.update_running_icon()
        self._tray_icon.show()

    @QtCore.Slot(str)
    def update_credentials(self, local_folder):
        sb = self.controller.get_server_binding(local_folder)
        prompt_authentication(
            self.controller, local_folder, app=self, is_url_readonly=True,
            url=sb.server_url, username=sb.remote_user)

    @QtCore.Slot()
    def rebuild_menu(self):
        tray_icon_menu = QtGui.QMenu()
        # TODO: iterate over current binding info to build server specific menu
        # sections
        # TODO: i18n action labels

        for binding_info in self.binding_info.values():
            open_folder = lambda: self.controller.open_local_file(
                binding_info.folder_path)
            open_folder_action = QtGui.QAction(
                binding_info.short_name, tray_icon_menu, triggered=open_folder)
            tray_icon_menu.addAction(open_folder_action)
            tray_icon_menu.addSeparator()

        # TODO: add pause action if in running state
        # TODO: add start action if in paused state
        quit_action = QtGui.QAction("&Quit", tray_icon_menu,
                                    triggered=self.action_quit)
        if self.state == 'quitting':
            quit_action.setEnabled(False)
        tray_icon_menu.addAction(quit_action)
        self._tray_icon.setContextMenu(tray_icon_menu)

    def start_synchronization_thread(self):
        if len(self.controller.list_server_bindings()) == 0:
            if prompt_authentication(
                self.controller, default_nuxeo_drive_folder(), app=self):
                self.communicator.icon.emit('enabled')

        if self.sync_thread is None or not self.sync_thread.isAlive():
            fault_tolerant = not getattr(self.options, 'stop_on_error', True)
            delay = getattr(self.options, 'delay', 5.0)
            # Controller and its database session pool should be thread safe,
            # hence reuse it directly
            self.sync_thread = Thread(target=sync_loop,
                                      args=(self.controller,),
                                      kwargs={"frontend": self,
                                              "fault_tolerant": fault_tolerant,
                                              "delay": delay})
            self.sync_thread.start()

    def event(self, event):
        """Handle URL scheme events under OSX"""
        if hasattr(event, 'url'):
            url = event.url().toString()
            try:
                info = parse_protocol_url(url)
                if info is not None:
                    log.debug("Received nxdrive URL scheme event: %s", url)
                    if info.get('command') == 'edit':
                        # This is a quick operation, no need to fork a QThread
                        self.controller.launch_file_editor(
                            info['server_url'], info['repository'], info['docref'])
            except:
                log.error("Error handling URL event: %s", url, exc_info=True)
        return super(Application, self).event(event)