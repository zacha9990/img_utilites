import math

from PIL import Image

from .presets import CROP_PRESETS


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
    return float(key)


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
