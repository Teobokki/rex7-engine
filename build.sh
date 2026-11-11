#!/bin/sh
# ONE Windows build: PyInstaller onedir -> Inno Setup installer, plus a standalone one-file portable .exe (no zip)
set -e
export PATH=/workspace/wine-portable/current/bin:$PATH WINEPREFIX=/workspace/exwifi/.wine WINEDEBUG=-all
cd /workspace/rex7-engine
V=1.0.0
rm -rf build dist
wine 'C:\Python311\python.exe' -m PyInstaller --noconfirm rex7.spec > pyi.log 2>&1; echo PYI_DONE
wine 'C:\InnoSetup\ISCC.exe' installer.iss > iss.log 2>&1; echo ISS_DONE
REX_ONEFILE=1 wine 'C:\Python311\python.exe' -m PyInstaller --noconfirm --workpath build1f rex7.spec > pyi1f.log 2>&1; echo PYI1F_DONE
cd dist && mv "REX 7 ENGINE REAL EX Portable.exe" "REX-7-ENGINE-REAL-EX-Portable-$V.exe"
ls -la
sha256sum "REX-7-ENGINE-REAL-EX-Setup-$V.exe" "REX-7-ENGINE-REAL-EX-Portable-$V.exe"
