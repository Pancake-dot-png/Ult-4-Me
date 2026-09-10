"""
Known Lovense device capabilities.

Maps device name -> list of (lovense_action, buttplug_actuator_type).
Lovense Connect reports fullFunctionsNames but it's sometimes incomplete
or uses different names (e.g. Gush reports "Oscillate" but API uses "Vibrate"),
so we maintain a known database and fall back to reported functions for unknown devices.
"""

KNOWN_DEVICES = {
    # name:     [(lovense_api_action, buttplug_actuator_type), ...]
    "Nora":     [("Vibrate", "Vibrate"), ("Rotate", "Rotate")],
    "Gush":     [("Vibrate", "Vibrate")],
    "Diamo":    [("Vibrate", "Vibrate")],
    "Lush":     [("Vibrate", "Vibrate")],
    "Lush 2":   [("Vibrate", "Vibrate")],
    "Lush 3":   [("Vibrate", "Vibrate")],
    "Hush":     [("Vibrate", "Vibrate")],
    "Hush 2":   [("Vibrate", "Vibrate")],
    "Max":      [("Vibrate", "Vibrate")],
    "Max 2":    [("Vibrate", "Vibrate")],
    "Domi":     [("Vibrate", "Vibrate")],
    "Domi 2":   [("Vibrate", "Vibrate")],
    "Osci":     [("Vibrate", "Vibrate")],
    "Osci 2":   [("Vibrate", "Vibrate")],
    "Edge":     [("Vibrate", "Vibrate")],
    "Edge 2":   [("Vibrate", "Vibrate")],
    "Ferri":    [("Vibrate", "Vibrate")],
    "Solace":   [("Vibrate", "Vibrate")],
    "Solace 2": [("Vibrate", "Vibrate")],
    "Ambi":     [("Vibrate", "Vibrate")],
    "Flexer":   [("Vibrate", "Vibrate")],
    "Gravity":  [("Vibrate", "Vibrate")],
    "Gemini":   [("Vibrate", "Vibrate")],
    "Ridge":    [("Vibrate", "Vibrate")],
    "Vulse":    [("Vibrate", "Vibrate")],
    "Tenera":   [("Vibrate", "Vibrate")],
    "Exomoon":  [("Vibrate", "Vibrate")],
    "Dolce":    [("Vibrate", "Vibrate")],
    "Calor":    [("Vibrate", "Vibrate")],
    "Mission":  [("Vibrate", "Vibrate")],
    "Hyphy":    [("Vibrate", "Vibrate")],
    "diamo":    [("Vibrate", "Vibrate")],  # lowercase variant from Lovense Remote
}


def get_actuators(device_name, reported_functions=None):
    """Get actuator definitions for a device.

    Returns list of (lovense_action, buttplug_actuator_type) tuples.
    Uses known DB first, falls back to reported functions.
    """
    if device_name in KNOWN_DEVICES:
        return KNOWN_DEVICES[device_name]

    # Capitalize and retry (Lovense Remote sometimes sends lowercase)
    capitalized = device_name.capitalize()
    if capitalized in KNOWN_DEVICES:
        return KNOWN_DEVICES[capitalized]

    # Fall back to reported functions
    if reported_functions:
        return [(f, "Vibrate") for f in reported_functions]

    return [("Vibrate", "Vibrate")]
