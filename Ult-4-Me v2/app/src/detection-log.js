// Summarize new detections, not each scan of an effect that remains active.
class DetectionLog {
  constructor() {
    this.active = new Map();
    this.pending = new Map();
  }

  observe(detections) {
    const current = new Map();
    for (const [name, count] of Object.entries(detections || {})) {
      if (!Number.isFinite(count) || count <= 0) continue;
      current.set(name, count);
      const added = Math.max(0, count - (this.active.get(name) || 0));
      if (added) this.pending.set(name, (this.pending.get(name) || 0) + added);
    }
    this.active = current;
  }

  flush() {
    const text = [...this.pending].map(([name, count]) => count > 1 ? `${name} ×${count}` : name).join(' · ');
    this.pending.clear();
    return text;
  }
}

module.exports = { DetectionLog };
