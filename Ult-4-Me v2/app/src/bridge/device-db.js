/**
 * Known Lovense device capabilities.
 * Maps device name -> array of [lovenseAction, buttplugActuatorType].
 */

const KNOWN_DEVICES = {
  // Multi-actuator devices
  Nora:     [['Vibrate', 'Vibrate'], ['Rotate', 'Rotate']],
  Max:      [['Vibrate', 'Vibrate'], ['Pump', 'AirPump']],
  'Max 2':  [['Vibrate', 'Vibrate'], ['Pump', 'AirPump']],
  Edge:     [['Vibrate', 'Vibrate'], ['Vibrate2', 'DualMotor']],
  'Edge 2': [['Vibrate', 'Vibrate'], ['Vibrate2', 'DualMotor']],
  Gravity:  [['Vibrate', 'Vibrate'], ['Vibrate2', 'DualMotor']],
  Dolce:    [['Vibrate', 'Vibrate'], ['Vibrate2', 'DualMotor']],
  Gemini:   [['Vibrate', 'Vibrate'], ['Vibrate2', 'DualMotor']],
  Vulse:    [['Vibrate', 'Vibrate'], ['Vibrate2', 'DualMotor']],
  // Single-actuator devices
  Gush:     [['Vibrate', 'Vibrate']],
  Diamo:    [['Vibrate', 'Vibrate']],
  diamo:    [['Vibrate', 'Vibrate']],
  Lush:     [['Vibrate', 'Vibrate']],
  'Lush 2': [['Vibrate', 'Vibrate']],
  'Lush 3': [['Vibrate', 'Vibrate']],
  Hush:     [['Vibrate', 'Vibrate']],
  'Hush 2': [['Vibrate', 'Vibrate']],
  Domi:     [['Vibrate', 'Vibrate']],
  'Domi 2': [['Vibrate', 'Vibrate']],
  Osci:     [['Vibrate', 'Vibrate']],
  'Osci 2': [['Vibrate', 'Vibrate']],
  Ferri:    [['Vibrate', 'Vibrate']],
  Solace:   [['Vibrate', 'Vibrate']],
  'Solace 2': [['Vibrate', 'Vibrate']],
  Ambi:     [['Vibrate', 'Vibrate']],
  Flexer:   [['Vibrate', 'Vibrate']],
  Ridge:    [['Vibrate', 'Vibrate']],
  Tenera:   [['Vibrate', 'Vibrate']],
  Exomoon:  [['Vibrate', 'Vibrate']],
  Calor:    [['Vibrate', 'Vibrate']],
  Mission:  [['Vibrate', 'Vibrate']],
  Hyphy:    [['Vibrate', 'Vibrate']],
};

function getActuators(deviceName, reportedFunctions) {
  if (KNOWN_DEVICES[deviceName]) return KNOWN_DEVICES[deviceName];
  // Try capitalize
  const cap = deviceName.charAt(0).toUpperCase() + deviceName.slice(1).toLowerCase();
  if (KNOWN_DEVICES[cap]) return KNOWN_DEVICES[cap];
  // Fallback to reported
  if (reportedFunctions && reportedFunctions.length > 0) {
    return reportedFunctions.map(f => [f, 'Vibrate']);
  }
  return [['Vibrate', 'Vibrate']];
}

module.exports = { KNOWN_DEVICES, getActuators };
