# ULT-4-ME V2.0.0

The current ULT-4-ME implementation. V1.3 is deprecated. V2 keeps its own configuration and templates; the Electron interface, scoring formulas, and Lovense bridge are retained, with a rebuilt detection and template-authoring pipeline.

## Launch

The portable Windows build is in `dist/win-unpacked/ULT-4-ME V2.exe`. Keep the entire `win-unpacked` folder together: the executable depends on its adjacent runtime files, `vision-worker/` and `templates/`. The Windows build is unsigned.

For development, use `Launch V2.vbs` or `npm start` from this folder. Development uses the local `.venv`, root `config.json`, and root `templates/`; the packaged app uses its own adjacent config and templates. Editing one does not update the other.

Open **Advanced → V2 Detection editor**. Choose an event, load a base-resolution template, and paint pixels to ignore or restore. Alternate examples can cover different appearances of the same event. Save, then apply to restart a running watcher. Existing main-window behavior automatically starts vision after onboarding; devices still require connection.

## Matching options

- **Automatic:** opaque images use V1 correlation and their existing threshold; transparent images use alpha-weighted structural correlation and the separate V2 threshold.
- **Masked structure:** excludes invisible pixels and compares the spatial arrangement of visible channel contrast. Local means and contrast are normalized so brightness changes are tolerated; flat backgrounds explicitly score zero. Uniform templates with no visible contrast are rejected with an error. This does not reverse HDR clipping or the game's alpha compositing, and is not an absolute hue check. Similarity scores are not probabilities; thresholds need gameplay calibration.
- **Shape:** compares template edges/silhouette with nearby screen edges, ignoring colors. Busy backgrounds can produce false positives; test negative examples.
- **V1 comparison:** explicitly reproduces the opaque/filtered matching method and ignores alpha.
- Up to six examples per event; optional bounded three-size search; configurable confirmation checks and brief release delay. Defaults require two matching scans and retain a detection through misses shorter than 200 ms. Explicit per-event timing overrides are retained. Scale search remains off by default.

Original image files are not overwritten. Imports preserve image dimensions and alpha; the editor writes a new PNG for mask edits. Use templates and test crops at the configured base resolution, usually 1920×1080. There is no guessed automatic downscaling. The image preview is enlarged for painting; that does not resize saved pixels.

The cropped-image test does not capture the screen, calculate scores or send hardware commands. It tests spatial similarity at base scale. Confirmation/release behavior is covered separately by automated tests.

## Development and tests

Use Python 3.11 on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
Copy-Item release-settings.json config.json  # first setup only
npm test
.\node_modules\.bin\electron.cmd scripts\smoke-ui.js
npm run build
```

The build assembles the worker, capture helper, Electron runtime, and templates. It preserves an existing portable configuration; on a first build it uses local settings if present, otherwise `release-settings.json`. Tests use generated images, isolated config, and an offline renderer harness; they do not connect devices.

For a public download, run `.\.venv\Scripts\python.exe scripts/package-release.py` after building. It uses the public release settings, includes only referenced templates and required runtime files, and excludes local configuration backups and logs. Do not publish a ZIP made directly from a personal installation.

## Source map

- `app/index.js`: Electron lifecycle, IPC, existing device routing, V2 template import and image testing.
- `app/detection-lab.html`: mask painting, alternate examples, matching options, offline image testing.
- `app/src/vision-worker.py`: JSON-lines worker protocol; `--analyze` for offline testing.
- `engine/detector.py`: cached examples, premultiplied-alpha resizing, masked/shape/legacy matchers, temporal presence.
- `engine/vision.py`: capture, region matching and inherited scoring loop.
- `engine/config.py` / `app/src/config.js`: Python/JS config defaults and persistence.
- `tests/test_detection.py`: transparency, scaling, shapes, examples, timing and scoring regression tests.
- `scripts/smoke-ui.js`: hidden Electron test of carried-over screens plus actual mask painting/save interaction.

## Constraints and current status

Target an older mainstream gaming PC around 16 GB RAM and GTX 1060/1650-class graphics while Overwatch runs. Avoid noticeable frame-rate loss or stuttering; dedicated AI hardware is not required. The matcher limits OpenCV to one CPU thread, caches scaled templates, and starts at 10 Hz.

V2.0.0 is the main release. Detection accuracy still depends on gameplay and display settings. Automated tests and a Windows build have passed; live Overwatch accuracy, actual game performance and hardware output have not been validated. OCR, trained models, automatic alignment and video replay/recording are not included in this release. The initial masked/shape thresholds are starting values, not calibrated replacements for V1 values.

Public settings include 41 configured events and 16 custom zones, with no device connection address. Opaque images use legacy comparison by default; the bundled Mercy and Burning alpha templates use masked structural matching. Detection thresholds still require calibration against actual gameplay.

The masked matcher now uses weighted zero-mean normalized correlation, replacing the color-error metric that gave plain gray backgrounds about 67%. Recorded Mercy tests cover the cropped symbols, both source states, live healing, and negative scenery. The debug slider follows the active matcher threshold. The receive-heal zone can still clip templates at its bottom edge; adjust its bounds to include the whole badge when testing.

## Fixes included in V2.0.0

Includes the v1.3 fixes: silent panic-page navigation, clean worker shutdown when the app disconnects, efficient waiting between the existing 10 Hz scans, confirmed-detection highlights in the debug panel, and priority for fresh matches over held matches. Stock receive-icon defaults use the original raw-color comparison; saved accidental edge filters for those stock filenames are repaired with a configuration backup. V2's alpha-aware structural matcher, custom images, thresholds, points, zones, and explicit recognition settings remain supported. Rebuilding preserves the portable app's current templates and configuration.

The user's custom `receive_discord_2.png` also uses raw-color matching with its existing 80% threshold. Its old edge filter scored a pasted reference around 67%; raw comparison passed that placement test at 100%. This is an offline regression check, not a live-game accuracy guarantee. Close the portable V2 app before rebuilding; the build now checks for a running instance before replacing files.

The tests cover alpha holes and scaling, recorded Mercy positives/negative scenery, timing, scoring, hidden-overlay output routing, panic audio, and the actual debug/editor screens. Live gameplay and the reported overlay-visibility issue still require verification.
