# REX 7 ENGINE REAL EX

perchance.org/ai-photo-generator (start page and Home) runs in a bundled web engine, so no system browser runtime is needed. The app also includes **REX 7 ELITE**, an image board with optional frame animation.

**Engine choice:** a self-contained Chromium-based engine (PySide6 6.7.3 / QtWebEngine) ships inside the app folder. It doesn't use the system WebView2 Evergreen runtime. Profile data (cookies, local storage, cache) is kept in `%LOCALAPPDATA%\REX 7 ENGINE REAL EX`.

To build, run `./build.sh` (Wine + Python 3.11 + PyInstaller + Inno Setup). It produces the Setup installer and a one-file portable exe.

The bundled UI fallback font is DejaVu Sans; its license is in `assets/fonts/LICENSE-fonts.txt`.

©2026 EX Inc./HYPERION DIGITAL ©2026
