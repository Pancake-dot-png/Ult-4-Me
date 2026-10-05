# ULT-4-ME V2.3

[**Download for Windows**](https://github.com/Pancake-dot-png/Ult-4-Me/releases/latest)

Extract the entire ZIP and run **ULT-4-ME V2.exe**. Keep all accompanying files together, then follow setup for your display and device connection. Python and Node.js are not required.

V2.3 adds stronger idle decay and an updated masked Zen-heal template. The kill-switch hotkey starts unassigned, and the Main tab Restart button has been removed. Debug regions start off.

For development, install the Node dependencies and Python 3.11 requirements into `.venv`, then use `npm start`. Run `npm test`, `npm run build`, and `.venv\Scripts\python.exe scripts/package-release.py` to test and package a clean public download.

The current dev UI includes Discord Light and Dark under Appearance, alongside the existing Cyberpunk and Plush Pastel palettes. Saved Industrial palettes map to Discord Light or Dark. The Session page uses a single full Phone IP field, grouped session tools, and clearer navigation. Both appearance selectors use compact stacked theme rows with horizontal color dots. Each row remembers and previews its own palette, even while another theme is active. Theme styles live under `app/ui`; the desktop app uses its existing IPC and device handlers.

Run `npm run test:ui` for an isolated real Electron renderer check. It uses simulated IPC instead of device or capture services and checks startup, theme switching and migration, connection input, mute, navigation, onboarding, and color memory across reloads. Review screenshots and a result file are saved under `build/ui-review`.
