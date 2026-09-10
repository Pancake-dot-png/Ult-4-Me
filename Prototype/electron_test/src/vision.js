/**
 * Vision engine — screen capture, template matching, and scoring.
 *
 * Uses node-screenshots for fast native capture.
 * Uses opencv-wasm for template matching.
 */

const path = require('path');
const fs = require('fs');
const sharp = require('sharp');
const { Monitor } = require('node-screenshots');
const { REGIONS } = require('./config');

const { cv } = require('opencv-wasm');

class Vision {
  constructor(config, templatesDir) {
    this.config = config;
    this.templatesDir = templatesDir;

    this.lastUpdate = 0;
    this.minUpdatePeriod = 100;
    this.detectionPing = 0;

    this.scoreOverTime = 0;
    this.scoreInstant = 0;

    this._detectionRect = {};
    this._scale = 1;
    this._monitor = null;
    this._regionState = {};
    this._detState = {};
    this._ready = false;
  }

  async init() {
    this._detectResolution();
    await this._loadTemplates();
    this._ready = true;
  }

  async update() {
    if (!this._ready) return false;
    const now = Date.now();
    if (now - this.lastUpdate < this.minUpdatePeriod) return false;
    const deltaTime = Math.min(1, (now - this.lastUpdate) / 1000);
    this.lastUpdate = now;

    // Reset
    this.scoreInstant = 0;
    for (const rs of Object.values(this._regionState)) rs.matches = [];
    for (const ds of Object.values(this._detState)) ds.count = 0;

    await this._updateDetections();

    // Assist dedup
    if (this.config.get('ignoreRedundantAssists')) {
      const elimCount = this._detState.Elimination?.count || 0;
      if (this._detState.Assist) {
        this._detState.Assist.count = Math.max(0, this._detState.Assist.count - elimCount);
      }
    }

    // Score
    let frameDelta = 0;
    for (const [name, det] of Object.entries(this.config.detectables)) {
      if (name === 'KillcamOrPOTG' || det.points == null) continue;
      const count = this._detState[name]?.count || 0;
      if (det.type === 0) this.scoreInstant += count * det.points;
      else if (det.type === 1) frameDelta += count * det.points;
      else if (det.type === 2) frameDelta += count * det.points / (det.duration || 1);
    }

    this.scoreOverTime += deltaTime * frameDelta;
    this.scoreOverTime -= deltaTime * (this.config.get('decay') || 100) / 60;
    this.scoreOverTime = Math.max(0, this.scoreOverTime);

    const t1 = Date.now();
    this.detectionPing = 0.9 * this.detectionPing + 0.1 * (t1 - now);
    return true;
  }

  getScore() { return this.scoreOverTime + this.scoreInstant; }
  setScore(v) { this.scoreOverTime = v; }
  getDetectionRect() { return this._detectionRect; }

  // ── Resolution ──

  _detectResolution() {
    const monitors = Monitor.all();
    const monNum = this.config.get('monitorNumber') || 1;
    this._monitor = monitors[monNum - 1] || monitors[0];

    const ar = this.config.getAspectRatio();
    const monW = this._monitor.width;
    const monH = this._monitor.height;
    const monX = this._monitor.x;
    const monY = this._monitor.y;

    let scale = 1;
    const gameRect = { left: monX, top: monY, width: monW, height: monH };
    const monAR = monW / monH;

    if (monAR >= ar.sampleW / ar.sampleH) {
      scale = monH / ar.sampleH;
      const desiredW = Math.floor(ar.sampleW * scale);
      const blackBar = Math.floor((monW - desiredW) / 2);
      gameRect.width = desiredW;
      gameRect.left += blackBar;
    } else {
      scale = monW / ar.sampleW;
      const desiredH = Math.floor(ar.sampleH * scale);
      const blackBar = Math.floor((monH - desiredH) / 2);
      gameRect.height = desiredH;
      gameRect.top += blackBar;
    }

    this._detectionRect = gameRect;
    this._scale = scale;

    // Scale regions
    this._regionState = {};
    const resKey = `${ar.sampleW}x${ar.sampleH}`;
    for (const [name, regionData] of Object.entries(REGIONS)) {
      const rect = regionData[resKey] || regionData['1920x1080'] || { x: 0, y: 0, w: 100, h: 100 };
      this._regionState[name] = {
        scaled: this._scaleRect(rect),
        matches: [],
        maxMatches: regionData.maxMatches || 1,
      };
    }
  }

  // ── Templates ──

  async _loadTemplates() {
    const ar = this.config.getAspectRatio();
    const templateScaling = ar.templateScaling || 1;

    this._detState = {};
    for (const [name, det] of Object.entries(this.config.detectables)) {
      if (!det.filename) continue;
      const filePath = path.join(this.templatesDir, det.filename);
      if (!fs.existsSync(filePath)) continue;

      try {
        const imgData = await sharp(filePath).removeAlpha().raw().toBuffer({ resolveWithObject: true });
        const newW = Math.max(1, Math.round(imgData.info.width * this._scale * templateScaling));
        const newH = Math.max(1, Math.round(imgData.info.height * this._scale * templateScaling));

        const scaledData = await sharp(imgData.data, {
          raw: { width: imgData.info.width, height: imgData.info.height, channels: 3 }
        }).resize(newW, newH).raw().toBuffer();

        let mat = new cv.Mat(newH, newW, cv.CV_8UC3);
        mat.data.set(scaledData);

        const filterFn = this._getFilter(det.filter);
        if (filterFn) {
          const filtered = filterFn(mat);
          mat.delete();
          mat = filtered;
        }

        this._detState[name] = { template: mat, count: 0 };
      } catch (e) {
        console.warn(`Template ${name}: ${e.message}`);
      }
    }
  }

  // ── Detection ──

  async _updateDetections() {
    let frame = await this._captureRegions(['KillcamOrPOTG', 'Prompt']);
    if (!frame) return;

    if (this.config.get('ignoreSpectate')) {
      this._matchRegion(frame, 'KillcamOrPOTG', ['KillcamOrPOTG']);
      if ((this._detState.KillcamOrPOTG?.count || 0) > 0) { frame.delete(); return; }
    }

    const promptDets = Object.entries(this.config.detectables)
      .filter(([, d]) => d.region === 'Prompt').map(([n]) => n);
    this._matchRegion(frame, 'Prompt', promptDets);
    frame.delete();

    const lowerRegions = Object.keys(REGIONS).filter(r => r !== 'KillcamOrPOTG' && r !== 'Prompt');
    frame = await this._captureRegions(lowerRegions);
    if (!frame) return;

    const popupDets = Object.entries(this.config.detectables)
      .filter(([, d]) => d.region === 'Popup').map(([n]) => n);
    for (const popup of ['Popup1', 'Popup2', 'Popup3']) {
      this._matchRegion(frame, popup, popupDets);
    }

    for (const [name, det] of Object.entries(this.config.detectables)) {
      if ((det.region || '').startsWith('Give ')) this._matchRegion(frame, det.region, [name]);
    }

    const healDets = Object.entries(this.config.detectables)
      .filter(([, d]) => d.region === 'Receive Heal').map(([n]) => n);
    this._matchRegion(frame, 'Receive Heal', healDets);

    const statusDets = Object.entries(this.config.detectables)
      .filter(([, d]) => d.region === 'Receive Status Effect').map(([n]) => n);
    this._matchRegion(frame, 'Receive Status Effect', statusDets);

    frame.delete();
  }

  async _captureRegions(regionNames) {
    let top = this._detectionRect.height;
    let left = this._detectionRect.width;
    let bottom = 0;
    let right = 0;

    for (const name of regionNames) {
      const rs = this._regionState[name];
      if (!rs) continue;
      const r = rs.scaled;
      top = Math.min(top, r.y);
      bottom = Math.max(bottom, r.y + r.h);
      left = Math.min(left, r.x);
      right = Math.max(right, r.x + r.w);
    }

    this._frameOffset = { top, left };
    const absLeft = left + this._detectionRect.left;
    const absTop = top + this._detectionRect.top;
    const w = right - left;
    const h = bottom - top;
    if (w <= 0 || h <= 0) return null;

    try {
      const img = this._monitor.captureImageSync();
      const pngBuf = img.toPngSync();

      const rawData = await sharp(pngBuf)
        .extract({ left: absLeft - (this._monitor.x || 0), top: absTop - (this._monitor.y || 0), width: w, height: h })
        .removeAlpha()
        .raw()
        .toBuffer();

      const mat = new cv.Mat(h, w, cv.CV_8UC3);
      mat.data.set(rawData);
      return mat;
    } catch (e) {
      console.warn(`Capture: ${e.message}`);
      return null;
    }
  }

  // ── Matching ──

  _matchRegion(frame, regionName, detNames) {
    const rs = this._regionState[regionName];
    if (!rs) return;

    detNames = detNames.filter(n =>
      (this.config.detectables[n]?.points || 0) !== 0 && this._detState[n]
    );
    if (detNames.length === 0) return;

    const r = rs.scaled;
    const cropTop = r.y - this._frameOffset.top;
    const cropLeft = r.x - this._frameOffset.left;
    if (cropTop < 0 || cropLeft < 0 || cropTop + r.h > frame.rows || cropLeft + r.w > frame.cols) return;

    const crop = frame.roi(new cv.Rect(cropLeft, cropTop, r.w, r.h));

    const filteredCrops = {};
    for (const name of detNames) {
      const filterName = this.config.detectables[name]?.filter;
      if (filterName && !filteredCrops[filterName]) {
        const fn = this._getFilter(filterName);
        if (fn) filteredCrops[filterName] = fn(crop.clone());
      }
    }

    for (const name of detNames) {
      if (rs.matches.length >= rs.maxMatches) break;
      const ds = this._detState[name];
      const det = this.config.detectables[name];
      const selectedCrop = filteredCrops[det.filter] || crop;

      if (ds.template.rows > selectedCrop.rows || ds.template.cols > selectedCrop.cols) continue;

      const result = new cv.Mat();
      cv.matchTemplate(selectedCrop, ds.template, result, cv.TM_CCOEFF_NORMED);
      const minMax = cv.minMaxLoc(result);
      result.delete();

      if (minMax.maxVal > (det.threshold || 0.8)) {
        ds.count++;
        rs.matches.push(name);
      }
    }

    for (const fc of Object.values(filteredCrops)) fc.delete();
    crop.delete();
  }

  // ── Filters ──

  _getFilter(name) {
    return { sobel: this._filterSobel, popup: this._filterPopup, prompt: this._filterPrompt }[name]?.bind(this) || null;
  }

  _filterSobel(mat) {
    const out = new cv.Mat();
    cv.Sobel(mat, out, cv.CV_8U, 0, 1, 3);
    return out;
  }

  _filterPopup(mat) {
    const gray = new cv.Mat();
    cv.cvtColor(mat, gray, cv.COLOR_RGB2GRAY);
    const cols = gray.cols;
    const left = Math.max(0, cols - 50);
    const roi = gray.roi(new cv.Rect(left, 0, cols - left, gray.rows));
    const meanVal = cv.mean(roi)[0];
    roi.delete();

    const low = new cv.Mat(gray.rows, gray.cols, cv.CV_8UC1, new cv.Scalar(Math.floor(meanVal - 50)));
    const high = new cv.Mat(gray.rows, gray.cols, cv.CV_8UC1, new cv.Scalar(Math.floor(0.5 * meanVal + 130)));
    const mask = new cv.Mat();
    cv.inRange(gray, low, high, mask);

    const result = mat.clone();
    for (let i = 0; i < mask.data.length; i++) {
      const idx = i * 3;
      if (mask.data[i] === 0) { result.data[idx] = 255; result.data[idx+1] = 255; result.data[idx+2] = 255; }
      else { result.data[idx] = 0; result.data[idx+1] = 0; result.data[idx+2] = 0; }
    }

    gray.delete(); low.delete(); high.delete(); mask.delete();
    return result;
  }

  _filterPrompt(mat) {
    const hsv = new cv.Mat();
    cv.cvtColor(mat, hsv, cv.COLOR_RGB2HSV);
    const channels = new cv.MatVector();
    cv.split(hsv, channels);
    let v = channels.get(2);
    const s = channels.get(1);
    if (cv.mean(v)[0] > 200) { v.delete(); v = s.clone(); }

    const edges = new cv.Mat();
    cv.Canny(v, edges, 200, 0);
    const kernel = cv.Mat.ones(3, 3, cv.CV_8UC1);
    const dilated = new cv.Mat();
    cv.dilate(edges, dilated, kernel);

    const merged = new cv.Mat();
    const vec = new cv.MatVector();
    vec.push_back(dilated); vec.push_back(dilated.clone()); vec.push_back(dilated.clone());
    cv.merge(vec, merged);

    hsv.delete(); channels.delete(); v.delete(); edges.delete(); kernel.delete(); dilated.delete(); vec.delete();
    return merged;
  }

  _scaleRect(rect) {
    return {
      x: Math.floor(rect.x * this._scale),
      y: Math.floor(rect.y * this._scale),
      w: Math.floor(rect.w * this._scale),
      h: Math.floor(rect.h * this._scale),
    };
  }
}

module.exports = { Vision, cv };
