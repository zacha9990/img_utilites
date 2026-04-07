#!/usr/bin/env python3
"""
imgconv.py - Image resize, smart crop, convert, and color grading tool
Usage: python imgconv.py <input> [options]
"""

import argparse
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageStat
except ImportError:
    print("Error: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

SUPPORTED_FORMATS = {
    "jpg": "JPEG", "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "gif": "GIF",
    "tiff": "TIFF", "tif": "TIFF",
    "ico": "ICO",
}

TONE_PRESETS = {
    "warm":     {"temperature": -40, "saturation": 1.1},
    "cool":     {"temperature":  40, "saturation": 1.05},
    "vintage":  {"temperature": -20, "saturation": 0.7,  "contrast": 0.9,  "brightness": 0.95},
    "fade":     {"contrast": 0.8,    "brightness": 1.05, "saturation": 0.85},
    "vibrant":  {"saturation": 1.5,  "contrast": 1.1},
    "dramatic": {"contrast": 1.4,    "saturation": 0.55},
    "matte":    {"contrast": 0.75,   "saturation": 0.9,  "brightness": 1.1},
}

CROP_PRESETS = {
    "landscape": 16 / 9,
    "portrait":  9 / 16,
    "square":    1 / 1,
    "4:3":       4 / 3,
    "3:4":       3 / 4,
    "16:9":     16 / 9,
    "9:16":      9 / 16,
    "3:2":       3 / 2,
    "2:3":       2 / 3,
    "1:1":       1 / 1,
    "21:9":     21 / 9,
    "5:4":       5 / 4,
    "4:5":       4 / 5,
}


# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------

def parse_size(size_str):
    """Parse size string: '800x600', '800x', 'x600', '50%'"""
    if size_str.endswith("%"):
        pct = float(size_str[:-1])
        if pct <= 0:
            raise ValueError("Percentage must be > 0")
        return ("percent", pct)
    if "x" in size_str.lower():
        parts = size_str.lower().split("x")
        if len(parts) != 2:
            raise ValueError("Size must be WxH, e.g. 800x600")
        w = int(parts[0]) if parts[0] else None
        h = int(parts[1]) if parts[1] else None
        if w is None and h is None:
            raise ValueError("At least one dimension required")
        return ("pixels", w, h)
    return ("pixels", int(size_str), None)


def parse_crop_ratio(crop_str):
    """
    Parse crop ratio. Returns float (width/height).
    Accepts: '16:9', '4:3', '1:1', 'landscape', 'portrait', 'square', '1.5'
    """
    key = crop_str.lower().strip()
    if key in CROP_PRESETS:
        return CROP_PRESETS[key]
    if ":" in key:
        parts = key.split(":")
        if len(parts) == 2:
            w, h = float(parts[0]), float(parts[1])
            if h == 0:
                raise ValueError("Height in ratio cannot be 0")
            return w / h
    # Try plain float
    return float(key)


# ---------------------------------------------------------------------------
# Smart crop
# ---------------------------------------------------------------------------

def _region_entropy(img_region):
    """Shannon entropy of a grayscale image region — higher = more detail."""
    gray = img_region.convert("L")
    hist = gray.histogram()
    total = sum(hist)
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in hist:
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def _best_crop_by_entropy(img, crop_w, crop_h, axis, num_steps=30):
    """
    Slide a (crop_w x crop_h) window along `axis` ('x' or 'y'),
    return the (x, y, x2, y2) box with the highest entropy.
    """
    orig_w, orig_h = img.size
    best_score = -1.0
    best_box = (0, 0, crop_w, crop_h)

    if axis == "y":
        max_offset = orig_h - crop_h
        if max_offset <= 0:
            return best_box
        step = max(1, max_offset // num_steps)
        offsets = list(range(0, max_offset + 1, step))
        if offsets[-1] != max_offset:
            offsets.append(max_offset)
        for y in offsets:
            box = (0, y, crop_w, y + crop_h)
            score = _region_entropy(img.crop(box))
            if score > best_score:
                best_score = score
                best_box = box
    else:  # axis == "x"
        max_offset = orig_w - crop_w
        if max_offset <= 0:
            return best_box
        step = max(1, max_offset // num_steps)
        offsets = list(range(0, max_offset + 1, step))
        if offsets[-1] != max_offset:
            offsets.append(max_offset)
        for x in offsets:
            box = (x, 0, x + crop_w, crop_h)
            score = _region_entropy(img.crop(box))
            if score > best_score:
                best_score = score
                best_box = box

    return best_box


def _detect_faces(img):
    """
    Try face detection via OpenCV. Returns list of (cx, cy) face centers,
    or None if OpenCV is not installed.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    img_rgb = img.convert("RGB")
    img_np = np.array(img_rgb)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    if len(faces) == 0:
        return []

    centers = [(int(x + w / 2), int(y + h / 2)) for (x, y, w, h) in faces]
    return centers


def _box_centered_on(cx, cy, crop_w, crop_h, orig_w, orig_h):
    """Return a crop box centered at (cx, cy), clamped to image bounds."""
    x = cx - crop_w // 2
    y = cy - crop_h // 2
    x = max(0, min(x, orig_w - crop_w))
    y = max(0, min(y, orig_h - crop_h))
    return (x, y, x + crop_w, y + crop_h)


def smart_crop(img, target_ratio, method="auto"):
    """
    Crop `img` to `target_ratio` (w/h) using the specified method.

    method:
      'auto'    — face detection if OpenCV available, else entropy
      'faces'   — face detection (falls back to entropy if no faces found)
      'entropy' — entropy-based sliding window
      'center'  — simple center crop
    """
    orig_w, orig_h = img.size
    orig_ratio = orig_w / orig_h

    if abs(orig_ratio - target_ratio) < 0.005:
        return img  # Already correct ratio, skip crop

    # Determine crop box dimensions
    if target_ratio > orig_ratio:
        # Target wider than source → constrain by width, reduce height
        crop_w = orig_w
        crop_h = max(1, int(round(orig_w / target_ratio)))
        slide_axis = "y"
    else:
        # Target taller (or same width) → constrain by height, reduce width
        crop_h = orig_h
        crop_w = max(1, int(round(orig_h * target_ratio)))
        slide_axis = "x"

    # Clamp to image size
    crop_w = min(crop_w, orig_w)
    crop_h = min(crop_h, orig_h)

    use_faces = method in ("auto", "faces")
    use_entropy = method in ("auto", "entropy")

    face_centers = None
    if use_faces:
        face_centers = _detect_faces(img)
        if face_centers is None and method == "faces":
            # OpenCV not available, warn and fall back
            print("  Warning: OpenCV not installed, falling back to entropy crop")
            face_centers = None

    box = None

    # --- Strategy 1: faces ---
    if face_centers:
        cx = int(sum(c[0] for c in face_centers) / len(face_centers))
        cy = int(sum(c[1] for c in face_centers) / len(face_centers))
        box = _box_centered_on(cx, cy, crop_w, crop_h, orig_w, orig_h)
        n = len(face_centers)
        print(f"  Crop  : face-aware ({n} face{'s' if n > 1 else ''} detected), "
              f"box {box[0]},{box[1]}→{box[2]},{box[3]}")

    # --- Strategy 2: entropy ---
    if box is None and (use_entropy or face_centers == []):
        box = _best_crop_by_entropy(img, crop_w, crop_h, slide_axis)
        print(f"  Crop  : entropy-based, "
              f"box {box[0]},{box[1]}→{box[2]},{box[3]}")

    # --- Strategy 3: center ---
    if box is None:
        box = _box_centered_on(orig_w // 2, orig_h // 2, crop_w, crop_h, orig_w, orig_h)
        print(f"  Crop  : center, box {box[0]},{box[1]}→{box[2]},{box[3]}")

    cropped = img.crop(box)
    print(f"          {orig_w}x{orig_h} → {cropped.width}x{cropped.height}  "
          f"(ratio {cropped.width/cropped.height:.3f})")
    return cropped


# ---------------------------------------------------------------------------
# Color grading and tone
# ---------------------------------------------------------------------------

def _apply_temperature(img, value):
    """
    Shift color temperature. Negative = warmer (more red), positive = cooler (more blue).
    value range: -100 to +100
    """
    src = img.convert("RGB")
    r, g, b = src.split()
    strength = abs(value) / 100.0
    shift = int(strength * 30)
    if value < 0:  # Warmer
        r = r.point(lambda x: min(255, x + shift))
        b = b.point(lambda x: max(0,   x - shift))
    else:          # Cooler
        r = r.point(lambda x: max(0,   x - shift))
        b = b.point(lambda x: min(255, x + shift))
    result = Image.merge("RGB", (r, g, b))
    return result.convert(img.mode) if img.mode != "RGB" else result


def apply_color_adjustments(img, brightness=1.0, contrast=1.0, saturation=1.0, temperature=0):
    """Apply brightness, contrast, saturation, and temperature adjustments."""
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)
    if temperature != 0:
        img = _apply_temperature(img, temperature)
    return img


def apply_tone_preset(img, preset_name):
    """Apply a named tone preset to the image."""
    preset = TONE_PRESETS.get(preset_name.lower())
    if preset is None:
        names = ", ".join(TONE_PRESETS)
        raise ValueError(f"Unknown tone preset '{preset_name}'. Available: {names}")
    return apply_color_adjustments(
        img,
        brightness=preset.get("brightness", 1.0),
        contrast=preset.get("contrast",   1.0),
        saturation=preset.get("saturation", 1.0),
        temperature=preset.get("temperature", 0),
    )


def _rgb_to_lab(img_np):
    """Convert RGB numpy array (H x W x 3, uint8) to CIE LAB float array."""
    import numpy as np
    rgb = img_np.astype(np.float64) / 255.0
    # Linearize sRGB gamma
    rgb = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    # RGB → XYZ (sRGB / D65 illuminant)
    M = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = rgb @ M.T
    xyz /= [0.95047, 1.00000, 1.08883]
    # XYZ → f(t)
    f = np.where(xyz > 0.008856, xyz ** (1.0 / 3.0), (903.3 * xyz + 16.0) / 116.0)
    L = 116.0 * f[:, :, 1] - 16.0
    a = 500.0 * (f[:, :, 0] - f[:, :, 1])
    b = 200.0 * (f[:, :, 1] - f[:, :, 2])
    return np.stack([L, a, b], axis=-1)


def _lab_to_rgb(lab):
    """Convert CIE LAB float array (H x W x 3) back to RGB uint8."""
    import numpy as np
    L, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0
    x = np.where(fx ** 3 > 0.008856, fx ** 3, (116.0 * fx - 16.0) / 903.3)
    y = np.where(L  > 903.3 * 0.008856, fy ** 3, L / 903.3)
    z = np.where(fz ** 3 > 0.008856, fz ** 3, (116.0 * fz - 16.0) / 903.3)
    xyz = np.stack([x, y, z], axis=-1) * [0.95047, 1.00000, 1.08883]
    M_inv = np.array([
        [ 3.2404542, -1.5371385, -0.4985314],
        [-0.9692660,  1.8760108,  0.0415560],
        [ 0.0556434, -0.2040259,  1.0572252],
    ])
    rgb_lin = np.clip(xyz @ M_inv.T, 0, None)
    rgb = np.where(rgb_lin > 0.0031308,
                   1.055 * (rgb_lin ** (1.0 / 2.4)) - 0.055,
                   12.92 * rgb_lin)
    return np.clip(rgb * 255.0, 0, 255).astype(np.uint8)


def _color_transfer_lab(src_np, ref_np):
    """LAB-space color transfer: match src statistics to ref (Reinhard et al. 2001)."""
    import numpy as np
    src_lab = _rgb_to_lab(src_np)
    ref_lab = _rgb_to_lab(ref_np)
    result  = src_lab.copy()
    for i in range(3):
        s_mean, s_std = src_lab[:, :, i].mean(), src_lab[:, :, i].std()
        r_mean, r_std = ref_lab[:, :, i].mean(), ref_lab[:, :, i].std()
        if s_std > 1e-6:
            result[:, :, i] = (src_lab[:, :, i] - s_mean) * (r_std / s_std) + r_mean
    return _lab_to_rgb(result)


def _color_transfer_rgb(src_img, ref_img):
    """Fallback color transfer: per-channel mean/std matching in RGB space."""
    src_stat = ImageStat.Stat(src_img)
    ref_stat = ImageStat.Stat(ref_img)
    channels = src_img.split()
    result_ch = []
    for i, ch in enumerate(channels):
        s_mean, s_std = src_stat.mean[i], src_stat.stddev[i]
        r_mean, r_std = ref_stat.mean[i], ref_stat.stddev[i]
        if s_std > 1e-6:
            lut = [int(min(255, max(0, (v - s_mean) * (r_std / s_std) + r_mean + 0.5)))
                   for v in range(256)]
        else:
            shift = int(r_mean - s_mean)
            lut = [int(min(255, max(0, v + shift))) for v in range(256)]
        result_ch.append(ch.point(lut))
    return Image.merge("RGB", result_ch)


def match_color(img, ref_path):
    """
    Transfer color/tone from reference image to img.
    Uses LAB color transfer if numpy is available, otherwise RGB channel matching.
    """
    ref = Image.open(ref_path).convert("RGB")
    src = img.convert("RGB")
    try:
        import numpy as np
        result = Image.fromarray(_color_transfer_lab(np.array(src), np.array(ref)), "RGB")
    except ImportError:
        print("  Note: numpy not installed — using RGB channel matching (install numpy for better results)")
        result = _color_transfer_rgb(src, ref)
    return result.convert(img.mode) if img.mode != "RGB" else result


def _histogram_match_lab(src_np, ref_np):
    """
    CDF-based histogram matching in LAB color space.
    Matches the full pixel distribution (not just mean/std) for more accurate tone reproduction.
    """
    import numpy as np
    src_lab = _rgb_to_lab(src_np)
    ref_lab = _rgb_to_lab(ref_np)
    result  = src_lab.copy()

    # L: [0,100]   a,b: [-128,127]
    ch_ranges = [(0.0, 100.0), (-128.0, 127.0), (-128.0, 127.0)]
    bins = 1024

    for i in range(3):
        lo, hi   = ch_ranges[i]
        src_flat = src_lab[:, :, i].ravel()
        ref_flat = ref_lab[:, :, i].ravel()

        # CDF of source and reference
        src_hist, edges = np.histogram(src_flat, bins=bins, range=(lo, hi))
        ref_hist, _     = np.histogram(ref_flat, bins=bins, range=(lo, hi))

        src_cdf = np.cumsum(src_hist).astype(np.float64); src_cdf /= src_cdf[-1]
        ref_cdf = np.cumsum(ref_hist).astype(np.float64); ref_cdf /= ref_cdf[-1]

        bin_centers = (edges[:-1] + edges[1:]) / 2.0

        # For each source bin, find the reference bin whose CDF matches
        mapped = np.interp(src_cdf, ref_cdf, bin_centers)

        # Apply mapping: locate each pixel's bin, replace with mapped value
        bin_idx = np.clip(np.searchsorted(edges[1:], src_flat), 0, bins - 1)
        result[:, :, i] = mapped[bin_idx].reshape(src_lab[:, :, i].shape)

    return _lab_to_rgb(result)


def _histogram_match_pil(src_img, ref_img):
    """
    Fallback CDF histogram matching using pure PIL (no numpy).
    Works channel-by-channel in RGB space.
    """
    channels     = src_img.split()
    ref_channels = ref_img.split()
    result_ch    = []

    for src_ch, ref_ch in zip(channels, ref_channels):
        src_hist = src_ch.histogram()   # 256 bins
        ref_hist = ref_ch.histogram()

        # Build CDFs
        src_total = sum(src_hist)
        ref_total = sum(ref_hist)

        src_cdf = []
        acc = 0
        for v in src_hist:
            acc += v
            src_cdf.append(acc / src_total)

        ref_cdf = []
        acc = 0
        for v in ref_hist:
            acc += v
            ref_cdf.append(acc / ref_total)

        # LUT: for each source value find the closest reference value by CDF
        lut     = []
        ref_val = 0
        for s_val in range(256):
            while ref_val < 255 and ref_cdf[ref_val] < src_cdf[s_val]:
                ref_val += 1
            lut.append(ref_val)

        result_ch.append(src_ch.point(lut))

    return Image.merge("RGB", result_ch)


def match_tone(img, ref_path):
    """
    Match tone and color from a reference image using full histogram (CDF) matching.
    Transfers the complete pixel distribution — more faithful than match_color's
    mean/std transfer, especially for exposure and contrast curves.
    Uses LAB color space with numpy, falls back to RGB-space PIL matching.
    """
    ref = Image.open(ref_path).convert("RGB")
    src = img.convert("RGB")
    try:
        import numpy as np
        result = Image.fromarray(_histogram_match_lab(np.array(src), np.array(ref)), "RGB")
    except ImportError:
        print("  Note: numpy not installed — using RGB histogram matching "
              "(install numpy for LAB-space results)")
        result = _histogram_match_pil(src, ref)
    return result.convert(img.mode) if img.mode != "RGB" else result


# ---------------------------------------------------------------------------
# Rounded corners
# ---------------------------------------------------------------------------

def parse_radius(radius_str):
    """
    Parse corner radius string.
    '30'   → 30 pixels (absolute)
    '10%'  → 10% of the shorter image side (resolved later at apply time)
    Returns (int, 'px') or (float, '%')
    """
    s = radius_str.strip()
    if s.endswith("%"):
        val = float(s[:-1])
        if val < 0 or val > 50:
            raise ValueError("Radius percentage must be 0–50%")
        return (val, "%")
    val = int(s)
    if val < 0:
        raise ValueError("Radius must be >= 0")
    return (val, "px")


def apply_rounded_corners(img, radius_spec):
    """
    Mask image corners to transparent using a rounded rectangle.
    radius_spec: (value, 'px') or (value, '%')
    Returns an RGBA image.
    """
    img = img.convert("RGBA")
    w, h = img.size

    val, unit = radius_spec
    if unit == "%":
        radius = int(min(w, h) * val / 100.0)
    else:
        radius = int(val)

    radius = max(0, min(radius, min(w, h) // 2))

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    try:
        # Pillow >= 8.2
        draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)
    except AttributeError:
        # Fallback for older Pillow: draw manually
        draw.rectangle([(radius, 0),     (w - radius, h)],     fill=255)
        draw.rectangle([(0,      radius), (w,         h - radius)], fill=255)
        draw.ellipse(  [(0,           0),           (2 * radius, 2 * radius)],           fill=255)
        draw.ellipse(  [(w - 2*radius, 0),          (w,          2 * radius)],           fill=255)
        draw.ellipse(  [(0,            h - 2*radius), (2*radius,  h)],                   fill=255)
        draw.ellipse(  [(w - 2*radius, h - 2*radius), (w,         h)],                   fill=255)

    img.putalpha(mask)
    return img


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------

def compute_new_size(orig_w, orig_h, size_spec, stretch=False):
    kind = size_spec[0]

    if kind == "percent":
        pct = size_spec[1] / 100.0
        return (max(1, int(orig_w * pct)), max(1, int(orig_h * pct)))

    _, target_w, target_h = size_spec

    if stretch:
        w = target_w if target_w else orig_w
        h = target_h if target_h else orig_h
        return (w, h)

    # Proportional (default)
    if target_w and target_h:
        ratio = min(target_w / orig_w, target_h / orig_h)
    elif target_w:
        ratio = target_w / orig_w
    else:
        ratio = target_h / orig_h

    return (max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio)))


# ---------------------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------------------

def fix_mode_for_format(img, fmt):
    """Convert image mode as required by the output format."""
    if fmt == "JPEG":
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            src = img.convert("RGBA") if img.mode == "P" else img
            mask = src.split()[-1] if src.mode in ("RGBA", "LA") else None
            background.paste(src, mask=mask)
            return background
        elif img.mode != "RGB":
            return img.convert("RGB")
    elif fmt == "ICO":
        if img.mode not in ("RGB", "RGBA"):
            return img.convert("RGBA")
    elif fmt not in ("PNG", "WEBP", "GIF", "BMP", "TIFF"):
        if img.mode not in ("RGB", "L"):
            return img.convert("RGB")
    return img


# ---------------------------------------------------------------------------
# Main processing pipeline
# ---------------------------------------------------------------------------

RESAMPLE_FILTERS = {
    "lanczos":  Image.LANCZOS,
    "bicubic":  Image.BICUBIC,
    "bilinear": Image.BILINEAR,
    "nearest":  Image.NEAREST,
}


def process_image(input_path, output_path, size_spec, stretch, quality, resample,
                  crop_ratio, crop_method,
                  tone=None, brightness=1.0, contrast=1.0, saturation=1.0,
                  temperature=0, match_ref=None, match_tone_ref=None,
                  corner_radius=None):
    img = ImageOps.exif_transpose(Image.open(input_path))
    orig_w, orig_h = img.size

    # Step 1: Smart crop (before resize so we work on full resolution)
    if crop_ratio is not None:
        img = smart_crop(img, crop_ratio, method=crop_method)

    # Step 2: Resize
    if size_spec:
        cur_w, cur_h = img.size
        new_w, new_h = compute_new_size(cur_w, cur_h, size_spec, stretch)
        img = img.resize((new_w, new_h), RESAMPLE_FILTERS[resample])
        print(f"  Resize: {cur_w}x{cur_h} → {new_w}x{new_h}")

    # Step 3: Color grading
    if match_tone_ref is not None:
        img = match_tone(img, match_tone_ref)
        print(f"  Tone  : histogram-matched to {Path(match_tone_ref).name}")

    if match_ref is not None:
        img = match_color(img, match_ref)
        print(f"  Color : matched to {Path(match_ref).name}")

    if tone is not None:
        img = apply_tone_preset(img, tone)
        print(f"  Tone  : {tone}")

    has_adj = brightness != 1.0 or contrast != 1.0 or saturation != 1.0 or temperature != 0
    if has_adj:
        img = apply_color_adjustments(img, brightness, contrast, saturation, temperature)
        parts = []
        if brightness  != 1.0: parts.append(f"brightness={brightness}")
        if contrast    != 1.0: parts.append(f"contrast={contrast}")
        if saturation  != 1.0: parts.append(f"saturation={saturation}")
        if temperature != 0:   parts.append(f"temperature={temperature:+d}")
        print(f"  Adjust: {', '.join(parts)}")

    # Step 4: Rounded corners
    if corner_radius is not None:
        val, unit = corner_radius
        img = apply_rounded_corners(img, corner_radius)
        label = f"{val}{'%' if unit == '%' else 'px'}"
        print(f"  Radius: {label} rounded corners applied")

    # Step 5: Save
    ext = output_path.suffix.lstrip(".").lower()
    fmt = SUPPORTED_FORMATS.get(ext)
    if not fmt:
        print(f"Error: Unsupported output format '.{ext}'")
        print(f"Supported: {', '.join(sorted(set(SUPPORTED_FORMATS.values())))}")
        sys.exit(1)

    # Rounded corners require alpha channel — auto-switch to PNG if needed
    if corner_radius is not None and fmt not in ("PNG", "WEBP"):
        new_path = output_path.with_suffix(".png")
        print(f"  Note  : {fmt} doesn't support transparency - saving as PNG instead")
        print(f"          {output_path.name} -> {new_path.name}")
        output_path = new_path
        fmt = "PNG"

    img = fix_mode_for_format(img, fmt)

    save_kwargs = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif fmt == "PNG":
        save_kwargs["optimize"] = True
    elif fmt == "WEBP":
        save_kwargs["quality"] = quality

    img.save(output_path, format=fmt, **save_kwargs)
    size_kb = output_path.stat().st_size / 1024
    print(f"  Saved : {output_path}  ({size_kb:.1f} KB)")


# ---------------------------------------------------------------------------
# Output path helper
# ---------------------------------------------------------------------------

def build_output_path(input_path, args):
    input_path = Path(input_path)

    if args.output:
        out = Path(args.output)
        if out.is_dir() or str(args.output).endswith(("/", "\\")):
            out.mkdir(parents=True, exist_ok=True)
            ext = f".{args.format.lower()}" if args.format else input_path.suffix
            return out / (input_path.stem + ext)
        return out

    stem = input_path.stem
    if args.crop:
        stem += f"_{args.crop.replace(':', '-')}"
    if args.size:
        stem += f"_{args.size.replace('%', 'pct')}"
    if getattr(args, "match_tone", None):
        stem += "_tone"
    if getattr(args, "match_color", None):
        stem += "_matched"
    if getattr(args, "tone", None):
        stem += f"_{args.tone}"
    if getattr(args, "radius", None):
        stem += f"_r{args.radius.replace('%', 'pct')}"
    ext = input_path.suffix
    if args.format:
        ext = f".{args.format.lower()}"

    return input_path.parent / f"{stem}{ext}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    tone_list = ", ".join(TONE_PRESETS)
    parser = argparse.ArgumentParser(
        description="Resize, smart crop, convert, and color grade images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Crop examples:
  --crop 16:9         smart crop to landscape 16:9
  --crop 9:16         smart crop to portrait 9:16
  --crop 1:1          smart crop to square
  --crop landscape    alias for 16:9
  --crop portrait     alias for 9:16
  --crop square       alias for 1:1
  --crop 4:3          smart crop to 4:3

  By default uses face detection (if OpenCV installed), else entropy-based.
  Use --crop-method to override: auto | faces | entropy | center

Size examples:
  --size 800x600      resize (proportional by default, fits inside 800x600)
  --size 800x         width 800, height auto
  --size x600         height 600, width auto
  --size 50%          scale to 50%

Format examples:
  --format png        convert to PNG
  --format webp       convert to WebP
  --format jpg        convert to JPEG

Color/tone examples:
  --tone warm                            apply warm preset
  --tone vintage                         apply vintage look
  --match-tone ref.jpg                   match full tone curve + color from ref (histogram)
  --match-color ref.jpg                  match color cast from ref (LAB mean/std transfer)
  --brightness 1.2 --saturation 1.3     manual adjustments
  --temperature -30                      warmer color temperature

  Tone presets: {tone_list}

  match-tone  : histogram CDF matching — transfers the full pixel distribution
                from ref including exposure, contrast curve, and color cast.
                Best for: making batch photos look identical to a reference.
  match-color : Reinhard LAB mean/std transfer — faster, more of a "style transfer".
                Best for: applying a general color mood from a reference.

  Both require numpy for LAB-space results (pip install numpy).
  Combining: --match-tone runs before --match-color, which runs before --tone.

Rounded corners examples:
  --radius 30           30px rounded corners (output auto-switches to PNG)
  --radius 5%           5% of shorter side as radius
  --radius 50%          fully circular (pill shape for landscape, circle for square)

Combined examples:
  python imgconv.py portrait.jpg --crop 16:9
  python imgconv.py portrait.jpg --crop landscape --size 1920x1080
  python imgconv.py photo.png --crop 1:1 --size 500x500 --format webp
  python imgconv.py photo.jpg --tone warm
  python imgconv.py photo.jpg --radius 30
  python imgconv.py photo.jpg --radius 5% --format png
  python imgconv.py *.jpg --radius 20 --output ./rounded/
  python imgconv.py *.jpg --match-tone golden_hour.jpg --output ./matched/
  python imgconv.py *.jpg --match-color reference.jpg --output ./graded/
  python imgconv.py *.jpg --tone vintage --saturation 0.8 --output ./out/
        """,
    )
    parser.add_argument("inputs", nargs="+", help="Input image file(s)")
    parser.add_argument("-s", "--size", metavar="SIZE",
                        help="Target size: WxH, Wx, xH, or N%%")
    parser.add_argument("-c", "--crop", metavar="RATIO",
                        help="Smart crop to aspect ratio: 16:9, 4:3, 1:1, landscape, portrait, square")
    parser.add_argument("--crop-method", default="auto",
                        choices=["auto", "faces", "entropy", "center"],
                        help="Crop strategy (default: auto = faces then entropy)")
    parser.add_argument("-f", "--format", metavar="FMT",
                        help="Output format: jpg, png, webp, bmp, gif, tiff, ico")
    parser.add_argument("-o", "--output", metavar="PATH",
                        help="Output file or directory (default: auto-named next to input)")
    parser.add_argument("-q", "--quality", type=int, default=85, metavar="N",
                        help="JPEG/WebP quality 1-95 (default: 85)")
    parser.add_argument("--stretch", action="store_true",
                        help="Non-proportional resize (stretch to exact WxH)")
    parser.add_argument("--resample", default="lanczos",
                        choices=["lanczos", "bicubic", "bilinear", "nearest"],
                        help="Resampling filter (default: lanczos)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite output if it already exists")
    # Color grading
    parser.add_argument("--tone", metavar="PRESET",
                        help=f"Color tone preset: {tone_list}")
    parser.add_argument("--radius", metavar="N",
                        help="Rounded corner radius: pixels (e.g. 30) or percent of shorter side "
                             "(e.g. 5%%). Output auto-switches to PNG/WebP if needed.")
    parser.add_argument("--match-tone", metavar="REF", dest="match_tone",
                        help="Match tone+color from reference via histogram (CDF) matching — "
                             "transfers full pixel distribution including exposure curve")
    parser.add_argument("--match-color", metavar="REF", dest="match_color",
                        help="Match color cast from reference via LAB mean/std transfer")
    parser.add_argument("--brightness", type=float, default=1.0, metavar="N",
                        help="Brightness multiplier, e.g. 1.2 (default: 1.0)")
    parser.add_argument("--contrast", type=float, default=1.0, metavar="N",
                        help="Contrast multiplier, e.g. 1.3 (default: 1.0)")
    parser.add_argument("--saturation", type=float, default=1.0, metavar="N",
                        help="Saturation multiplier, e.g. 1.5 (default: 1.0)")
    parser.add_argument("--temperature", type=int, default=0, metavar="N",
                        help="Color temperature: negative=warmer, positive=cooler (default: 0)")

    args = parser.parse_args()

    has_color = (args.tone or args.match_color or args.match_tone
                 or args.brightness != 1.0 or args.contrast != 1.0
                 or args.saturation != 1.0 or args.temperature != 0)
    if not args.size and not args.format and not args.crop and not has_color and not args.radius:
        parser.error("Specify at least one of: --size, --crop, --format, --radius, --tone, "
                     "--match-tone, --match-color, --brightness, --contrast, "
                     "--saturation, --temperature")

    corner_radius = None
    if args.radius:
        try:
            corner_radius = parse_radius(args.radius)
        except ValueError as e:
            print(f"Error parsing --radius: {e}")
            sys.exit(1)

    size_spec = None
    if args.size:
        try:
            size_spec = parse_size(args.size)
        except ValueError as e:
            print(f"Error parsing --size: {e}")
            sys.exit(1)

    crop_ratio = None
    if args.crop:
        try:
            crop_ratio = parse_crop_ratio(args.crop)
        except ValueError as e:
            print(f"Error parsing --crop: {e}")
            sys.exit(1)

    errors = 0
    for input_str in args.inputs:
        if "*" in input_str or "?" in input_str:
            p = Path(input_str)
            base_dir = p.parent if p.parent != Path(".") else Path(".")
            pattern = p.name
            paths = list(base_dir.glob(pattern))
        else:
            paths = [Path(input_str)]
        if not paths:
            print(f"Warning: No files matched '{input_str}'")
            continue

        for input_path in sorted(paths):
            if not input_path.exists():
                print(f"Error: File not found: {input_path}")
                errors += 1
                continue

            output_path = build_output_path(input_path, args)
            if output_path == input_path and not args.overwrite:
                output_path = input_path.parent / f"{input_path.stem}_out{input_path.suffix}"

            if output_path.exists() and not args.overwrite:
                print(f"Skip: {output_path} already exists (use --overwrite to replace)")
                continue

            print(f"Processing: {input_path}")
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                process_image(input_path, output_path, size_spec, args.stretch,
                              args.quality, args.resample, crop_ratio, args.crop_method,
                              tone=args.tone, brightness=args.brightness,
                              contrast=args.contrast, saturation=args.saturation,
                              temperature=args.temperature, match_ref=args.match_color,
                              match_tone_ref=args.match_tone, corner_radius=corner_radius)
            except Exception as e:
                print(f"  Error: {e}")
                errors += 1

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
