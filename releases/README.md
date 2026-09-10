# Portable release settings

`v1.3-settings.json` is the shareable configuration for the v1.3 Windows package, including the tuned detection zones. Copy it beside `ULT-4-ME.exe` as `config.json` when assembling a fresh release, before creating the ZIP.

Preserve `user_regions` when resetting onboarding or clearing the device address. The tuned 1920x1080 popup rectangles are:

- Popup1: x=732, y=754, width=244, height=45
- Popup2: x=731, y=806, width=245, height=30
- Popup3: x=731, y=839, width=247, height=30

The Python and JavaScript source defaults also contain these rectangles. Existing installations can keep their own settings; do not overwrite a user's configuration automatically.
