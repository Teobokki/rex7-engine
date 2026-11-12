"""REX 7 web view on the system web runtime (Evergreen), hosted inside a native child window of the Qt UI.
(c)2026 EX Inc./HYPERION DIGITAL (c)2026"""
import os, subprocess, sys, threading, traceback
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedLayout
from rex7_style import res_path, downloads_dir

CLIENT = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def runtime_version():
    """Installed Evergreen runtime version from the EdgeUpdate client keys (HKLM 32/64-bit view, HKCU), or None."""
    if os.environ.get("REX7_FORCE_NO_RUNTIME"):
        return None
    if os.environ.get("REX7_FORCE_RUNTIME"):
        return "forced"
    try:
        import winreg
    except Exception:
        return None
    keys = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\\" + CLIENT),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\\" + CLIENT),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\\" + CLIENT)]
    for root, k in keys:
        try:
            with winreg.OpenKey(root, k.replace("\\\\", "\\")) as h:
                v, _ = winreg.QueryValueEx(h, "pv")
                if v and v != "0.0.0.0":
                    return v
        except OSError:
            pass
    return None


def bootstrapper():
    return res_path("wv2lib", "webruntime_setup.exe")


class NativeHost(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setAttribute(Qt.WA_NativeWindow); self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NoSystemBackground); self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self, e):
        pass

    def resizeEvent(self, e):
        self.owner._bounds()

    def moveEvent(self, e):
        self.owner._moved()

    def showEvent(self, e):
        self.owner._visible(True)

    def hideEvent(self, e):
        self.owner._visible(False)

    def focusInEvent(self, e):
        self.owner._focus()


class WebHost(QWidget):
    urlChanged = Signal(str)
    titleChanged = Signal(str)
    navState = Signal(bool, bool)
    loading = Signal(bool)
    status = Signal(str)
    _installed = Signal(int)

    def __init__(self, home, data_dir):
        super().__init__()
        self.home_url, self.data_dir = home, data_dir
        self.ctrl = None; self.wv = None; self.pending = None; self.error = ""
        self.lay = QStackedLayout(self)
        self.host = NativeHost(self); self.lay.addWidget(self.host)
        self.panel = QWidget(); pv = QVBoxLayout(self.panel); pv.addStretch(1)
        self.p_title = QLabel(""); self.p_title.setAlignment(Qt.AlignCenter); self.p_title.setObjectName("apptitle"); pv.addWidget(self.p_title)
        self.p_text = QLabel(""); self.p_text.setAlignment(Qt.AlignCenter); self.p_text.setWordWrap(True); self.p_text.setObjectName("muted")
        pv.addWidget(self.p_text)
        row = QHBoxLayout(); row.addStretch(1)
        self.b_inst = QPushButton("\u2b07  Install web runtime"); self.b_inst.setObjectName("accent"); self.b_inst.clicked.connect(self.install)
        self.b_retry = QPushButton("\u27f3  Retry"); self.b_retry.clicked.connect(self.start)
        row.addWidget(self.b_inst); row.addWidget(self.b_retry); row.addStretch(1); pv.addLayout(row)
        self.p_note = QLabel("REX 7 ELITE works without it."); self.p_note.setAlignment(Qt.AlignCenter); self.p_note.setObjectName("dim")
        pv.addWidget(self.p_note); pv.addStretch(2)
        self.lay.addWidget(self.panel)
        self._installed.connect(self._after_install)

    # ---------- states
    def _panel(self, title, text, install=True):
        self.p_title.setText(title); self.p_text.setText(text); self.b_inst.setVisible(install)
        self.lay.setCurrentWidget(self.panel); self.status.emit(title)

    def ready(self):
        return self.wv is not None

    def start(self):
        if self.wv is not None:
            return
        ver = runtime_version()
        if not ver:
            self._panel("The web runtime isn't installed",
                        "REX 7 ENGINE REAL EX shows web pages with the system web runtime, which is missing on this PC.\n"
                        "Click Install web runtime (free, about a minute, needs internet), then the page opens here.")
            return
        self.lay.setCurrentWidget(self.host)
        try:
            import pythonnet
            try:
                pythonnet.load("netfx")
            except Exception:
                pass
            import clr
            lib = res_path("wv2lib")
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(lib)
            os.environ["PATH"] = lib + os.pathsep + os.environ.get("PATH", "")
            clr.AddReference(os.path.join(lib, "Microsoft.Web.WebView2.Core.dll"))
            clr.AddReference("System.Drawing")
            from Microsoft.Web.WebView2.Core import CoreWebView2Environment
            self._mods = __import__("Microsoft.Web.WebView2.Core", fromlist=["*"])
            os.makedirs(self.data_dir, exist_ok=True)
            task = CoreWebView2Environment.CreateAsync(None, self.data_dir, None)
        except Exception as ex:
            self._fail(ex); return
        self._wait(task, self._env_ready)

    def _fail(self, ex):
        self.error = "".join(traceback.format_exception_only(type(ex), ex)).strip() if isinstance(ex, BaseException) else str(ex)
        self._panel("The web runtime couldn't start",
                    "The web page can't be shown right now (%s).\nInstalling or repairing the web runtime usually fixes this."
                    % self.error[:220])

    def _wait(self, task, then):
        def poll():
            try:
                if not task.IsCompleted:
                    QTimer.singleShot(40, poll); return
                if task.IsFaulted or task.IsCanceled:
                    self._fail(str(task.Exception.InnerException if task.Exception else "cancelled")); return
                then(task.Result)
            except Exception as ex:
                self._fail(ex)
        QTimer.singleShot(40, poll)

    def _env_ready(self, env):
        from System import IntPtr
        self.env = env
        self._wait(env.CreateCoreWebView2ControllerAsync(IntPtr(int(self.host.winId()))), self._ctrl_ready)

    def _ctrl_ready(self, ctrl):
        self.ctrl = ctrl; wv = self.wv = ctrl.CoreWebView2
        self._bounds()
        wv.SourceChanged += lambda s, e: self.urlChanged.emit(str(s.Source))
        wv.DocumentTitleChanged += lambda s, e: self.titleChanged.emit(str(s.DocumentTitle))
        wv.HistoryChanged += lambda s, e: self.navState.emit(bool(s.CanGoBack), bool(s.CanGoForward))
        wv.NavigationStarting += lambda s, e: self.loading.emit(True)
        wv.NavigationCompleted += lambda s, e: self.loading.emit(False)
        def newwin(s, e):
            e.Handled = True; s.Navigate(e.Uri)
        wv.NewWindowRequested += newwin
        try:
            def dl(s, e):
                name = os.path.basename(str(e.ResultFilePath)) or "download"
                e.ResultFilePath = os.path.join(downloads_dir(), name)
                self.status.emit("Saving to Downloads: " + name)
            wv.DownloadStarting += dl
        except Exception:
            pass
        url, self.pending = self.pending or self.home_url, None
        wv.Navigate(url)
        self.status.emit("")

    # ---------- host plumbing
    def _bounds(self):
        if self.ctrl is not None:
            from System.Drawing import Rectangle
            d = self.host.devicePixelRatioF()
            self.ctrl.Bounds = Rectangle(0, 0, max(1, int(self.host.width() * d)), max(1, int(self.host.height() * d)))

    def _moved(self):
        if self.ctrl is not None:
            try: self.ctrl.NotifyParentWindowPositionChanged()
            except Exception: pass

    def _visible(self, on):
        if self.ctrl is not None:
            self.ctrl.IsVisible = on

    def _focus(self):
        if self.ctrl is not None:
            try: self.ctrl.MoveFocus(self._mods.CoreWebView2MoveFocusReason.Programmatic)
            except Exception: pass

    def close_runtime(self):
        if self.ctrl is not None:
            try: self.ctrl.Close()
            except Exception: pass
            self.ctrl = self.wv = None

    # ---------- navigation
    def navigate(self, url):
        if self.wv is not None:
            self.wv.Navigate(url)
        else:
            self.pending = url

    def back(self):
        if self.wv is not None and self.wv.CanGoBack: self.wv.GoBack()

    def forward(self):
        if self.wv is not None and self.wv.CanGoForward: self.wv.GoForward()

    def reload(self):
        if self.wv is not None: self.wv.Reload()
        else: self.start()

    def capture(self, cb):
        """PNG snapshot of the page -> cb(QImage or None)."""
        if self.wv is None:
            cb(None); return
        try:
            from System.IO import MemoryStream
            ms = MemoryStream()
            t = self.wv.CapturePreviewAsync(self._mods.CoreWebView2CapturePreviewImageFormat.Png, ms)
        except Exception:
            cb(None); return
        def poll():
            if not t.IsCompleted:
                QTimer.singleShot(40, poll); return
            img = None
            if not t.IsFaulted:
                img = QImage.fromData(bytes(ms.ToArray()), "PNG")
            cb(img if img is not None and not img.isNull() else None)
        QTimer.singleShot(40, poll)

    # ---------- install
    def install(self):
        exe = bootstrapper()
        if not os.path.exists(exe):
            self._panel("Installer missing", "The web runtime installer isn't included in this copy."); return
        self.b_inst.setEnabled(False); self.b_retry.setEnabled(False)
        self._panel("Installing the web runtime\u2026", "This takes about a minute. The page opens here when it's done.", install=True)
        def run():
            try:
                rc = subprocess.call([exe, "/silent", "/install"], creationflags=NO_WINDOW)
            except Exception:
                rc = -1
            self._installed.emit(rc)
        threading.Thread(target=run, daemon=True).start()

    def _after_install(self, rc):
        self.b_inst.setEnabled(True); self.b_retry.setEnabled(True)
        if runtime_version():
            self.start()
        else:
            self._panel("The web runtime isn't installed yet",
                        "The installer finished with code %d but the runtime wasn't found. Check your internet connection and try again." % rc)
