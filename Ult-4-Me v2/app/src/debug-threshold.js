// Runtime mode is authoritative: auto can select a different matcher per example.
function getThreshold(det = {}, detail = {}, edit) {
  if (det.type === 8) return {mode: 'passive', field: null, value: det.threshold ?? .9};
  if (det.type === 6) return {mode: 'color', field: null, value: 0};
  const mode = detail.mode || det.match_mode || 'auto';
  const field = mode === 'legacy' ? 'threshold'
    : ['masked', 'shape'].includes(mode) ? 'v2_threshold' : null;
  const fallback = mode === 'legacy' ? .8 : mode === 'shape' ? .75 : .9;
  const value = edit?.value ?? detail.threshold ??
    (field ? det[field] : det.v2_threshold ?? det.threshold) ?? fallback;
  return { mode, field, value };
}
module.exports = { getThreshold };
