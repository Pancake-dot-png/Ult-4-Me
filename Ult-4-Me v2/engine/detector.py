"""Bounded, CPU-only HUD matching. No capture, scoring, or device side effects."""
from dataclasses import dataclass
from pathlib import Path
import cv2 as cv
import numpy as np

cv.setNumThreads(1)
cv.ocl.setUseOpenCL(False)


@dataclass
class Example:
    image: np.ndarray
    mask: object
    mode: str
    filename: str
    scale: float
    pattern: object = None


@dataclass
class MaskedPattern:
    mass: float
    kernel: np.ndarray
    energy: float
    rgb_weights: np.ndarray


# Ignore near-flat patches: normalizing tiny variance otherwise amplifies noise.
MIN_VARIANCE = 3 * (2 / 255) ** 2


def compile_pattern(image, weights):
    mass = float(weights.sum())
    pixels = image.astype(np.float32) / 255
    rgb_weights = np.repeat(weights[:, :, None], 3, axis=2)
    mean = (pixels * rgb_weights).sum(axis=(0, 1), dtype=np.float64) / mass
    centered = (pixels - mean).astype(np.float32)
    energy = float((centered * centered * rgb_weights).sum())
    if energy / mass <= MIN_VARIANCE:
        raise ValueError('Masked structure needs visible contrast. Include the symbol and its light/dark details in the mask.')
    return MaskedPattern(mass, centered * rgb_weights, energy, rgb_weights)


def masked_structure(pixels, squared_pixels, example):
    """Alpha-weighted, per-channel zero-mean normalized spatial correlation.

    Removing the local channel means and normalizing contrast tolerates additive
    brightness and common contrast changes, but does not repair HDR clipping.
    Flat inputs have no structural evidence and explicitly score zero.
    """
    pattern = example.pattern
    numerator = cv.matchTemplate(pixels, pattern.kernel, cv.TM_CCORR)
    variance = cv.matchTemplate(squared_pixels, pattern.rgb_weights, cv.TM_CCORR)
    for channel in cv.split(pixels):
        total = cv.matchTemplate(channel, example.mask, cv.TM_CCORR)
        variance -= total * total / pattern.mass
    variance = np.maximum(variance, 0)
    score = np.zeros_like(numerator)
    np.divide(numerator, np.sqrt(np.maximum(pattern.energy * variance, 1e-12)),
              out=score, where=variance / pattern.mass > MIN_VARIANCE)
    return np.clip(score, 0, 1)


@dataclass
class Match:
    confidence: float = 0.0
    location: tuple = (0, 0)
    size: tuple = (0, 0)
    mode: str = "auto"
    filename: str = ""


def template_path(root, filename):
    root = Path(root).resolve()
    target = (root / filename).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Template must be inside the templates folder")
    return target


def load_examples(root, det, scale, filter_fn=None):
    """Compile once per configuration/resolution. Alpha is never discarded."""
    reference_height = float(det.get("template_height", 1080))
    if not np.isfinite(reference_height) or not 480 <= reference_height <= 4320:
        raise ValueError("Template reference height must be between 480 and 4320")
    scale *= 1080 / reference_height
    filenames = list(dict.fromkeys([det.get("filename", ""), *det.get("examples", [])]))
    filenames = [f for f in filenames if f]
    if len(filenames) > 6:
        raise ValueError("Use at most six examples per event")
    tolerance = float(det.get("scale_tolerance", 0))
    if not 0 <= tolerance <= 0.1:
        raise ValueError("Size tolerance must be between 0 and 10 percent")
    factors = [1.0] if tolerance == 0 else [1.0, 1.0 - tolerance, 1.0 + tolerance]
    examples = []
    for filename in filenames:
        raw = cv.imdecode(np.fromfile(template_path(root, filename), dtype=np.uint8), cv.IMREAD_UNCHANGED)
        if raw is None:
            raise ValueError(f"Cannot read template: {filename}")
        box = det.get("template_crop")
        if box is not None:
            if (not isinstance(box, list) or len(box) != 4
                    or not all(isinstance(v, int) for v in box)):
                raise ValueError("Template crop must be [x, y, width, height]")
            x, y, width, height = box
            if min(x, y) < 0 or min(width, height) < 2 or x + width > raw.shape[1] or y + height > raw.shape[0]:
                raise ValueError("Template crop is outside the image")
            raw = raw[y:y + height, x:x + width]
        if raw.ndim == 2:
            raw = cv.cvtColor(raw, cv.COLOR_GRAY2BGR)
        alpha = raw[:, :, 3] if raw.shape[2] == 4 else np.full(raw.shape[:2], 255, np.uint8)
        if np.count_nonzero(alpha) < 8:
            raise ValueError(f"Template has fewer than eight visible pixels: {filename}")
        mode = det.get("match_mode", "auto")
        if mode not in ("auto", "shape", "masked", "legacy"):
            raise ValueError(f"Unknown match mode: {mode}")
        if mode == "auto":
            mode = "masked" if np.any(alpha < 255) else "legacy"
        for factor in factors:
            pattern = None
            w = max(2, round(raw.shape[1] * scale * factor))
            h = max(2, round(raw.shape[0] * scale * factor))
            if w > 2048 or h > 2048:
                raise ValueError("Template exceeds the 2048-pixel size limit")
            rgb = cv.resize(raw[:, :, :3], (w, h), interpolation=cv.INTER_LINEAR)
            weights = cv.resize(alpha.astype(np.float32) / 255, (w, h), interpolation=cv.INTER_LINEAR)
            if mode != "legacy" and np.any(alpha < 255):
                # Resize premultiplied RGB, then unpremultiply. Invisible source
                # colors must not contaminate the visible boundary during scaling.
                premultiplied = raw[:, :, :3].astype(np.float32) * (alpha[:, :, None] / 255.0)
                resized = cv.resize(premultiplied, (w, h), interpolation=cv.INTER_LINEAR)
                rgb = np.rint(resized / np.maximum(weights[:, :, None], 1e-8)).clip(0, 255).astype(np.uint8)
            if mode == "shape":
                gray = cv.cvtColor(rgb, cv.COLOR_BGR2GRAY)
                edges = cv.Canny(gray, 80, 160)
                # Exclude invisible RGB and the arbitrary RGB/alpha boundary.
                visible = (weights > 0.5).astype(np.uint8)
                interior = cv.erode(visible, np.ones((3, 3), np.uint8))
                edges *= interior
                if np.any(alpha < 255):
                    silhouette = cv.Canny(visible * 255, 80, 160)
                    edges = cv.bitwise_or(edges, silhouette)
                if np.count_nonzero(edges) < 8:
                    raise ValueError(f"Too few edges for shape matching: {filename}")
                image = edges.astype(np.float32) / 255
                mask = None
            elif mode == "masked":
                # Alpha controls statistical weight, not a pixel-color target.
                mask = weights
                image = rgb
                if np.sum(weights) < 8:
                    raise ValueError(f"Not enough visible pixels after scaling: {filename}")
                pattern = compile_pattern(image, mask)
            else:
                image = filter_fn(rgb) if filter_fn else rgb
                mask = None
            examples.append(Example(image, mask, mode, filename, factor, pattern))
    return examples


def match_examples(crop, examples, filter_fn=None, edge_tolerance=2.0):
    """Return best spatial match; all masked scores are finite and bounded.

    Masked mode compares the spatial arrangement of visible channel contrast.
    Flat backgrounds score zero. Similarity is not a probability.
    Shape mode uses mean distance from template edges to screen edges.
    """
    best = Match(mode=examples[0].mode if examples else 'auto')
    if crop is None or crop.size == 0:
        return best
    filtered = None
    distance = None
    pixels = squared_pixels = None
    for ex in examples:
        h, w = ex.image.shape[:2]
        if h > crop.shape[0] or w > crop.shape[1]:
            continue
        if ex.mode == "legacy":
            if filtered is None:
                filtered = filter_fn(crop.copy()) if filter_fn else crop
            result = cv.matchTemplate(filtered, ex.image, cv.TM_CCOEFF_NORMED)
        elif ex.mode == "masked":
            if pixels is None:
                pixels = crop.astype(np.float32) / 255
                squared_pixels = pixels * pixels
            result = masked_structure(pixels, squared_pixels, ex)
        else:
            if distance is None:
                edges = cv.Canny(cv.cvtColor(crop, cv.COLOR_BGR2GRAY), 80, 160)
                distance = cv.distanceTransform(255 - edges, cv.DIST_L2, 3)
            distance_sum = cv.matchTemplate(distance, ex.image, cv.TM_CCORR)
            result = 1 - distance_sum / (float(ex.image.sum()) * max(0.5, edge_tolerance))
        result = np.nan_to_num(result, nan=-1, posinf=-1, neginf=-1)
        _, confidence, _, location = cv.minMaxLoc(result)
        confidence = max(0.0, min(1.0, confidence))
        if confidence > best.confidence:
            best = Match(confidence, location, (w, h), ex.mode, ex.filename)
    return best


class Presence:
    """Per-event/region confirmation and release hysteresis, using scan timestamps."""
    def __init__(self):
        self.state = {}

    def update(self, key, confidence, threshold, now, confirm_frames=2, release_ms=200):
        count, active, last_hit, last_scan = self.state.get(key, (0, False, -1e9, -1e9))
        if now - last_scan > 0.5:
            count, active = 0, False
        if confidence >= threshold:
            count = min(confirm_frames, count + 1)
            last_hit = now
            active = active or count >= confirm_frames
        else:
            count = 0
            active = active and now - last_hit < release_ms / 1000 - 1e-9
        self.state[key] = (count, active, last_hit, now)
        return active
