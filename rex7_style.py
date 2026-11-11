"""REX 7 shared look: dark grey, silver, one thin cyan accent line. No glow. (c)2026 EX Inc./HYPERION DIGITAL (c)2026"""
import os, sys

BG, PANEL, CARD, CARD2, BORDER = "#141518", "#1c1d21", "#232428", "#2e3036", "#3a3c43"
TXT, MUT, DIM = "#eceef2", "#a0a4ad", "#666a73"
ACC = "#7fd8ea"          # thin cyan accent line only
SILVER, SILVER2 = "#c9ccd2", "#e3e5e9"
BOARD_RGB = (35, 36, 40)


def res_path(*n):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *n)


def downloads_dir():
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.name == "nt":
        try:  # real Downloads known folder (may be redirected)
            import ctypes
            from ctypes import wintypes
            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
            g = GUID(0x374DE290, 0x123F, 0x4565, (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p)) == 0 and p.value:
                d = p.value
        except Exception:
            pass
    os.makedirs(d, exist_ok=True)
    return d


QSS = """
* { font-family: 'Segoe UI'; font-size: 9.5pt; color: %(TXT)s; }
QMainWindow, #root, QStackedWidget, QDialog, QMessageBox { background: %(BG)s; }
#topbar { background: %(PANEL)s; }
#hline { background: %(BORDER)s; }
#navbar, #tools, #timeline { background: %(PANEL)s; }
#apptitle { font-size: 13pt; font-weight: 700; letter-spacing: 1px; }
#muted { color: %(MUT)s; }
#dim { color: %(DIM)s; font-size: 8pt; font-weight: 700; }
#foot { background: %(PANEL)s; color: %(DIM)s; font-size: 8pt; padding: 3px; }
QPushButton { background: %(CARD2)s; border: 1px solid %(BORDER)s; border-radius: 4px; padding: 5px 11px; }
QPushButton:hover { background: #3a3d44; }
QPushButton:pressed { background: #45484f; }
QPushButton:disabled { color: %(DIM)s; background: %(CARD)s; }
QPushButton:checked { background: #3d4048; border-color: %(SILVER)s; }
QPushButton#accent { background: %(SILVER)s; color: #141518; font-weight: 700; border: 1px solid %(SILVER2)s; }
QPushButton#accent:hover { background: %(SILVER2)s; }
QPushButton#flat { background: transparent; border: none; color: %(MUT)s; font-weight: 700; }
QPushButton#flat:hover { color: %(TXT)s; }
QPushButton#tab { background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0;
                  color: %(MUT)s; font-weight: 700; padding: 9px 10px; }
QPushButton#tab:checked { color: %(TXT)s; border-bottom: 2px solid %(ACC)s; }
QPushButton#tab:hover { color: %(TXT)s; }
QPushButton#nav { min-width: 30px; padding: 4px 6px; font-size: 11pt; }
QPushButton#tool { min-width: 34px; padding: 5px 6px; }
QPushButton#danger:hover { background: #5a2626; }
QLineEdit, QSpinBox, QComboBox { background: %(CARD)s; border: 1px solid %(BORDER)s; border-radius: 4px; padding: 4px 8px;
                                 selection-background-color: #4a4e57; }
QLineEdit:focus { border-color: %(SILVER)s; }
QComboBox QAbstractItemView { background: %(CARD2)s; selection-background-color: #4a4e57; border: 1px solid %(BORDER)s; }
QListWidget { background: %(CARD)s; border: 1px solid %(BORDER)s; border-radius: 4px; outline: 0; }
QListWidget::item { padding: 4px; border-radius: 3px; }
QListWidget::item:selected { background: #3d4048; border: 1px solid %(SILVER)s; color: %(TXT)s; }
QSlider::groove:horizontal { height: 4px; background: %(CARD2)s; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %(SILVER)s; border-radius: 2px; }
QSlider::handle:horizontal { background: %(SILVER2)s; width: 12px; margin: -5px 0; border-radius: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid %(BORDER)s; background: %(CARD)s; border-radius: 3px; }
QCheckBox::indicator:checked { background: %(SILVER2)s; border: 3px solid %(CARD)s; outline: none; }
QCheckBox { spacing: 6px; }
QProgressBar#thin { background: %(PANEL)s; border: none; }
QProgressBar#thin::chunk { background: %(ACC)s; }
QMenu { background: %(CARD2)s; border: 1px solid %(BORDER)s; }
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { background: #4a4e57; }
QToolTip { background: %(CARD2)s; color: %(TXT)s; border: 1px solid %(BORDER)s; }
QScrollBar:horizontal, QScrollBar:vertical { background: %(PANEL)s; height: 10px; width: 10px; }
QScrollBar::handle { background: %(BORDER)s; border-radius: 4px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
""" % dict(BG=BG, PANEL=PANEL, CARD=CARD, CARD2=CARD2, BORDER=BORDER, TXT=TXT, MUT=MUT, DIM=DIM, ACC=ACC,
           SILVER=SILVER, SILVER2=SILVER2)
