const path = require('path');
function validateOptions(o) {
  const allowed = new Set(['filename', 'examples', 'match_mode', 'v2_threshold', 'scale_tolerance', 'confirm_frames', 'release_ms', 'edge_tolerance']);
  if (!o || typeof o !== 'object' || Object.keys(o).some(k => !allowed.has(k))) throw new Error('Invalid detection options');
  if (!['auto', 'masked', 'shape', 'legacy'].includes(o.match_mode)) throw new Error('Choose a matching method');
  for (const [key, min, max] of [['v2_threshold', .01, 1], ['scale_tolerance', 0, .1], ['confirm_frames', 1, 5], ['release_ms', 0, 300], ['edge_tolerance', .5, 5]]) {
    if (!Number.isFinite(o[key]) || o[key] < min || o[key] > max) throw new Error(`Invalid ${key}`);
  }
  if (!Number.isInteger(o.confirm_frames)) throw new Error('Confirmation must be whole frames');
  if (!Array.isArray(o.examples) || o.examples.length > 5) throw new Error('Use at most five alternate examples');
  for (const f of [o.filename, ...o.examples]) {
    if (typeof f !== 'string' || !f || path.basename(f) !== f || /[\\/]/.test(f)) throw new Error('Select valid templates');
  }
}
module.exports = {validateOptions};
