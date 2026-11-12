# REX 7 ENGINE REAL EX

perchance.org/ai-photo-generator (start page and Home) runs on the system WebView2 Evergreen runtime. The app also includes **REX 7 ELITE**, an image board with optional frame animation.

**Engine (1.0.2+):** the system-installed WebView2 Evergreen runtime is hosted in a native child window of the Qt UI via pythonnet and Microsoft.Web.WebView2.Core (CoreWebView2Environment / CoreWebView2Controller). The user data folder is `%LOCALAPPDATA%\REX 7 ENGINE REAL EX`. Setup checks the EdgeUpdate client key {F3017226-FE2A-4295-8BDF-00C3A9A7E4C5} (HKLM 32/64-bit, HKCU) and, if the runtime is missing, runs Microsoft's Evergreen bootstrapper (`wv2lib/webruntime_setup.exe`, from go.microsoft.com/fwlink/p/?LinkId=2124703) with `/silent /install`. The portable exe offers the same install from inside the app. 1.0.0 and 1.0.1 bundled QtWebEngine instead.

To build, run `./build.sh` (Wine + Python 3.11 + PyInstaller + Inno Setup). It produces the Setup installer and a one-file portable exe.

The bundled UI fallback font is DejaVu Sans; its license is in `assets/fonts/LICENSE-fonts.txt`.

©2026 EX Inc./HYPERION DIGITAL ©2026
