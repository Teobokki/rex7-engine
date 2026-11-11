# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all
ONEFILE = "--onefile" in sys.argv or bool(__import__("os").environ.get("REX_ONEFILE"))
d, b, h = collect_all('imageio_ffmpeg')
excl = ['matplotlib', 'scipy', 'pandas', 'IPython', 'pytest', 'torch', 'cv2', 'tkinter',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtMultimedia',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtBluetooth', 'PySide6.QtSensors',
        'PySide6.QtSerialPort', 'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtSpatialAudio', 'PySide6.QtGraphs',
        'PySide6.QtQuick3D', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtStateMachine', 'PySide6.QtTextToSpeech',
        'PySide6.QtVirtualKeyboard', 'PySide6.QtNfc', 'PySide6.QtHttpServer', 'PySide6.QtLocation', 'PySide6.QtAxContainer']
a = Analysis(['rex7.py'],
             datas=[('assets', 'assets')] + d,
             binaries=b,
             hiddenimports=['PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore', 'PIL.Image'] + h,
             excludes=excl, noarchive=False)
def _keep(entry):
    dst = entry[0].replace('/', '\\').lower()
    if 'pyside6\\qml\\' in dst:
        return False
    if 'pyside6\\translations\\' in dst:
        return dst.endswith('en-us.pak')
    if dst.endswith('qtwebengine_devtools_resources.pak'):
        return False
    return True
a.datas = [e for e in a.datas if _keep(e)]
a.binaries = [e for e in a.binaries if _keep(e)]
pyz = PYZ(a.pure)
import os
if os.environ.get("REX_ONEFILE"):
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='REX 7 ENGINE REAL EX Portable', console=False, upx=False,
              version='version.txt', icon=['assets/logo.ico'])
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='REX 7 ENGINE REAL EX', console=False, upx=False,
              version='version.txt', icon=['assets/logo.ico'])
    coll = COLLECT(exe, a.binaries, a.datas, upx=False, name='REX 7 ENGINE REAL EX')
