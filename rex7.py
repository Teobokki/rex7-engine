"""REX 7 ENGINE REAL EX - perchance.org in a bundled web engine + REX 7 ELITE image/animation board.
(c)2026 EX Inc./HYPERION DIGITAL (c)2026"""
import json, os, sys, threading, time, urllib.request, re

APP = "REX 7 ENGINE REAL EX"
APP_VERSION = "1.0.0"
COPYRIGHT = "\u00a92026 EX Inc./HYPERION DIGITAL \u00a92026"
REPO = "Teobokki/rex7-engine"
UPDATE_URL = "https://raw.githubusercontent.com/%s/main/latest.json" % REPO
HOME_URL = "https://perchance.org"


def is_wine():
    if os.name != "nt":
        return False
    try:
        import ctypes
        return hasattr(ctypes.windll.ntdll, "wine_get_version")
    except Exception:
        return False


def data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, APP)
    os.makedirs(d, exist_ok=True)
    return d


WINE = is_wine()
_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
if WINE:  # compatibility layer only: the GPU process and sandbox don't work there. Real Windows keeps the defaults.
    _flags += " --no-sandbox --disable-gpu --disable-gpu-compositing --disable-features=RendererCodeIntegrity"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _flags.strip()
if WINE:
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    os.environ.setdefault("QT_OPENGL", "software")

from PySide6.QtCore import Qt, QUrl, QTimer, Signal, QObject, QSize
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QKeySequence, QShortcut, QPainter
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                               QLineEdit, QStackedWidget, QSplashScreen, QMessageBox, QProgressBar, QSizePolicy)
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

import rex7_elite as elite
from rex7_style import (QSS, BG, PANEL, CARD, CARD2, BORDER, TXT, MUT, DIM, ACC, res_path, downloads_dir)


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


class Page(QWebEnginePage):
    def createWindow(self, _type):  # pop-ups / target=_blank open in the same view
        return self


class Emblem(QLabel):
    clicked = Signal()

    def __init__(self, h=42):
        super().__init__()
        self._h = h
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("About " + APP)
        self.setFixedSize(int(h * 150 / 48), h)
        self._pm = {k: QPixmap(res_path("assets", "emblem@%dx.png" % k)) for k in (1, 2, 3)}

    def paintEvent(self, e):
        dpr = self.devicePixelRatioF()
        pm = self._pm[3] if dpr * self._h > 96 else (self._pm[2] if dpr * self._h > 48 else self._pm[1])
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(self.rect(), pm)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class Updater(QObject):
    found = Signal(dict)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP)
        self.setWindowIcon(QIcon(res_path("assets", "logo.ico")))
        self.resize(1360, 860)
        self.profile = QWebEngineProfile("REX7ENGINE", self)
        dd = data_dir()
        self.profile.setPersistentStoragePath(os.path.join(dd, "WebData"))
        self.profile.setCachePath(os.path.join(dd, "Cache"))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        self.profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        ua = re.sub(r"\s*QtWebEngine/\S+", "", self.profile.httpUserAgent())
        self.profile.setHttpUserAgent(ua)
        self.profile.downloadRequested.connect(self._download)
        st = self.profile.settings()
        for a in (QWebEngineSettings.LocalStorageEnabled, QWebEngineSettings.JavascriptCanOpenWindows,
                  QWebEngineSettings.FullScreenSupportEnabled, QWebEngineSettings.ScrollAnimatorEnabled):
            st.setAttribute(a, True)

        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        top = QWidget(); top.setObjectName("topbar"); th = QHBoxLayout(top); th.setContentsMargins(12, 6, 12, 6); th.setSpacing(8)
        self.emblem = Emblem(42); self.emblem.clicked.connect(self.about); th.addWidget(self.emblem)
        t = QLabel(APP); t.setObjectName("apptitle"); th.addWidget(t)
        vl = QLabel("v" + APP_VERSION); vl.setObjectName("muted"); th.addWidget(vl)
        th.addSpacing(18)
        self.tabs = {}
        for key, label in (("web", "\u25ce  WEB"), ("elite", "\u270e  REX 7 ELITE")):
            b = QPushButton(label); b.setObjectName("tab"); b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.show_tab(k)); th.addWidget(b); self.tabs[key] = b
        th.addStretch(1)
        self.b_upd = QPushButton("\u27f3  Check for updates"); self.b_upd.setObjectName("flat"); self.b_upd.clicked.connect(self.check_updates)
        th.addWidget(self.b_upd)
        b_ab = QPushButton("About"); b_ab.setObjectName("flat"); b_ab.clicked.connect(self.about); th.addWidget(b_ab)
        v.addWidget(top)
        line = QWidget(); line.setFixedHeight(1); line.setObjectName("hline"); v.addWidget(line)

        self.stack = QStackedWidget(); v.addWidget(self.stack, 1)
        # ---- web page
        web = QWidget(); wv = QVBoxLayout(web); wv.setContentsMargins(0, 0, 0, 0); wv.setSpacing(0)
        nav = QWidget(); nav.setObjectName("navbar"); nh = QHBoxLayout(nav); nh.setContentsMargins(10, 5, 10, 5); nh.setSpacing(6)
        self.view = QWebEngineView()
        self.page = Page(self.profile, self.view)
        self.page.fullScreenRequested.connect(lambda r: (r.accept(), self.showFullScreen() if r.toggleOn() else self.showNormal()))
        self.view.setPage(self.page)
        def nb(txt, tip, fn):
            b = QPushButton(txt); b.setObjectName("nav"); b.setToolTip(tip); b.clicked.connect(fn); nh.addWidget(b); return b
        self.b_back = nb("\u25c0", "Back (Alt+Left)", self.view.back)
        self.b_fwd = nb("\u25b6", "Forward (Alt+Right)", self.view.forward)
        nb("\u27f3", "Reload (F5)", self.view.reload)
        nb("\u2302", "Home \u2014 perchance.org", self.home)
        self.addr = QLineEdit(); self.addr.setObjectName("addr"); self.addr.returnPressed.connect(self.go); nh.addWidget(self.addr, 1)
        self.title = QLabel(""); self.title.setObjectName("muted"); self.title.setMaximumWidth(320); nh.addWidget(self.title)
        b_imp = QPushButton("\u2b07  Import to board"); b_imp.setObjectName("accent"); b_imp.setToolTip("Capture this page onto the current REX 7 ELITE frame")
        b_imp.clicked.connect(self.import_to_board); nh.addWidget(b_imp)
        wv.addWidget(nav)
        self.prog = QProgressBar(); self.prog.setObjectName("thin"); self.prog.setTextVisible(False); self.prog.setFixedHeight(2)
        self.prog.setRange(0, 100); wv.addWidget(self.prog)
        wv.addWidget(self.view, 1)
        self.view.urlChanged.connect(lambda u: (self.addr.setText(u.toString()), self._navstate()))
        self.view.titleChanged.connect(self._title)
        self.view.loadProgress.connect(lambda p: (self.prog.setValue(p), self.prog.setVisible(p < 100)))
        self.view.loadFinished.connect(lambda ok: (self.prog.setVisible(False), self._navstate()))
        self.stack.addWidget(web)
        # ---- board
        self.board = elite.EliteBoard(self)
        self.stack.addWidget(self.board)
        foot = QLabel(COPYRIGHT); foot.setObjectName("foot"); foot.setAlignment(Qt.AlignCenter); v.addWidget(foot)

        QShortcut(QKeySequence("Alt+Left"), self, self.view.back)
        QShortcut(QKeySequence("Alt+Right"), self, self.view.forward)
        QShortcut(QKeySequence("F5"), self, self.view.reload)
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: (self.show_tab("web"), self.addr.setFocus(), self.addr.selectAll()))
        self.upd = Updater(); self.upd.found.connect(self._upd_found)
        self.show_tab("web")
        self.home()
        threading.Thread(target=self._bg_update, args=(False,), daemon=True).start()

    # ---- web
    def home(self):
        self.view.setUrl(QUrl(HOME_URL))

    def go(self):
        t = self.addr.text().strip()
        if not t:
            return
        if not re.match(r"^https?://", t, re.I):
            t = "https://" + t
        self.view.setUrl(QUrl(t))

    def _title(self, t):
        self.title.setText(t[:60])
        self.setWindowTitle((t + " \u2014 " if t else "") + APP)

    def _navstate(self):
        h = self.view.history()
        self.b_back.setEnabled(h.canGoBack()); self.b_fwd.setEnabled(h.canGoForward())

    def _download(self, item):
        item.setDownloadDirectory(downloads_dir())
        item.accept()
        self.title.setText("Saving to Downloads: " + item.downloadFileName())

    def import_to_board(self):
        img = self.view.grab().toImage()
        self.board.import_image(img, "Web capture")
        self.show_tab("elite")

    # ---- shell
    def show_tab(self, key):
        self.stack.setCurrentIndex(0 if key == "web" else 1)
        for k, b in self.tabs.items():
            b.setChecked(k == key)
        if key == "elite":
            self.board.enter()
        else:
            self.board.leave()

    def about(self):
        m = QMessageBox(self)
        m.setWindowTitle("About " + APP)
        m.setIconPixmap(QPixmap(res_path("assets", "emblem@2x.png")).scaledToHeight(64, Qt.SmoothTransformation))
        m.setText("<b>%s</b> &nbsp; v%s" % (APP, APP_VERSION))
        m.setInformativeText("REX ENGINE with its own bundled web engine (no separate runtime needed) and the "
                             "REX 7 ELITE image &amp; animation board.\n\n" + COPYRIGHT)
        m.exec()

    def check_updates(self):
        self.b_upd.setText("Checking\u2026")
        threading.Thread(target=self._bg_update, args=(True,), daemon=True).start()

    def _bg_update(self, manual):
        info = {"manual": manual}
        try:
            req = urllib.request.Request(UPDATE_URL + "?t=%d" % time.time(), headers={"User-Agent": "REX7/" + APP_VERSION})
            with urllib.request.urlopen(req, timeout=10) as r:
                info.update(json.loads(r.read().decode("utf-8")))
        except Exception as ex:
            info["error"] = str(ex)
        self.upd.found.emit(info)

    def _upd_found(self, info):
        newer = "version" in info and vtuple(info["version"]) > vtuple(APP_VERSION)
        if newer:
            self.b_upd.setText("\u2b06  Update %s available" % info["version"])
            try: self.b_upd.clicked.disconnect()
            except Exception: pass
            self.b_upd.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(info.get("release_url") or info.get("url"))))
        else:
            self.b_upd.setText("\u27f3  Check for updates")
            if info.get("manual"):
                QMessageBox.information(self, APP, "Couldn't check right now." if "error" in info else "You have the latest version.")


def selftest(win, out):
    """--selftest <dir>: screenshots of the web view and REX 7 ELITE (used for QA builds)."""
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(out, "selftest.log"), "w", encoding="utf-8")
    def L(*a):
        log.write(" ".join(str(x) for x in a) + "\n"); log.flush()
    win.resize(1600, 900)
    L("wine", WINE, "flags", os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS"))
    state = {"loaded": False}
    win.view.loadFinished.connect(lambda ok: (L("loadFinished", ok, win.view.url().toString()), state.__setitem__("loaded", ok)))
    steps = []
    def shot(name):
        win.grab().save(os.path.join(out, name)); L("shot", name)
    def s1():
        shot("web.png"); win.import_to_board()
    def s2():
        win.board.selftest_fill(); shot("elite_board.png")
    def s3():
        win.board.selftest_anim(out); shot("elite_animation.png")
    def s4():
        win.show_tab("web"); shot("web2.png"); L("done"); log.close(); QApplication.quit()
    t = 0
    for dt, fn in ((25000, s1), (3000, s2), (4000, s3), (6000, s4)):
        t += dt; QTimer.singleShot(t, fn)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP); app.setOrganizationName("EX Inc.")
    app.setWindowIcon(QIcon(res_path("assets", "logo.ico")))
    from PySide6.QtGui import QFontDatabase, QFont
    for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        QFontDatabase.addApplicationFont(res_path("assets", "fonts", f))
    QFont.insertSubstitutions("Segoe UI", ["Segoe UI Symbol", "DejaVu Sans"])
    app.setStyleSheet(QSS)
    sp = QSplashScreen(QPixmap(res_path("assets", "splash.png")))
    sp.show(); app.processEvents()
    win = Main()
    def reveal():
        win.show(); sp.finish(win)
    QTimer.singleShot(1400, reveal)
    if "--selftest" in sys.argv:
        selftest(win, sys.argv[sys.argv.index("--selftest") + 1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
