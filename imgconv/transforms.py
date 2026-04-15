from PIL import Image, ImageColor, ImageDraw, ImageOps


# ---------------------------------------------------------------------------
# Size / resize
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


def compute_new_size(orig_w, orig_h, size_spec, stretch=False, no_upscale=False):
    kind = size_spec[0]

    if kind == "percent":
        pct = size_spec[1] / 100.0
        new_w = max(1, int(orig_w * pct))
        new_h = max(1, int(orig_h * pct))
        if no_upscale and (new_w > orig_w or new_h > orig_h):
            return (orig_w, orig_h)
        return (new_w, new_h)

    _, target_w, target_h = size_spec

    if stretch:
        w = target_w if target_w else orig_w
        h = target_h if target_h else orig_h
        if no_upscale:
            w = min(w, orig_w)
            h = min(h, orig_h)
        return (w, h)

    # Proportional (default)
    if target_w and target_h:
        ratio = min(target_w / orig_w, target_h / orig_h)
    elif target_w:
        ratio = target_w / orig_w
    else:
        ratio = target_h / orig_h

    if no_upscale and ratio > 1.0:
        return (orig_w, orig_h)

    return (max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio)))


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
        # Fallback for older Pillow
        draw.rectangle([(radius, 0),     (w - radius, h)],           fill=255)
        draw.rectangle([(0,      radius), (w,         h - radius)],  fill=255)
        draw.ellipse(  [(0,           0),           (2*radius, 2*radius)],           fill=255)
        draw.ellipse(  [(w - 2*radius, 0),          (w,        2*radius)],           fill=255)
        draw.ellipse(  [(0,            h - 2*radius), (2*radius, h)],                fill=255)
        draw.ellipse(  [(w - 2*radius, h - 2*radius), (w,        h)],                fill=255)

    img.putalpha(mask)
    return img


# ---------------------------------------------------------------------------
# Rotate / flip
# ---------------------------------------------------------------------------

def apply_rotate(img, degrees, expand=True):
    """Rotate image clockwise by `degrees`. Uses bicubic resampling."""
    return img.rotate(-degrees, expand=expand, resample=Image.BICUBIC)


def apply_flip(img, direction):
    """
    Flip image.
    direction: 'h' or 'horizontal' → left-right mirror
               'v' or 'vertical'   → top-bottom flip
               'both'              → both axes
    """
    d = direction.lower()
    if d in ("h", "horizontal"):
        return ImageOps.mirror(img)
    elif d in ("v", "vertical"):
        return ImageOps.flip(img)
    elif d == "both":
        return ImageOps.mirror(ImageOps.flip(img))
    else:
        raise ValueError(f"Unknown flip direction '{direction}'. Use: h, v, both")


# ---------------------------------------------------------------------------
# Padding / letterbox
# ---------------------------------------------------------------------------

def apply_padding(img, target_w, target_h, pad_color="black"):
    """
    Center `img` on a `target_w x target_h` canvas filled with `pad_color`.
    Use pad_color='transparent' for an alpha-transparent background (output becomes RGBA).
    """
    cur_w, cur_h = img.size
    if cur_w == target_w and cur_h == target_h:
        return img

    if pad_color.lower() == "transparent":
        canvas_mode = "RGBA"
        fill = (0, 0, 0, 0)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
    else:
        try:
            rgb = ImageColor.getrgb(pad_color)
        except (ValueError, AttributeError):
            raise ValueError(
                f"Invalid pad color: '{pad_color}'. "
                "Use a color name (black, white), #hex value, or 'transparent'."
            )
        canvas_mode = img.mode
        if img.mode == "RGBA":
            fill = rgb[:3] + (255,)
        elif img.mode == "RGB":
            fill = rgb[:3]
        elif img.mode == "L":
            fill = int(0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2])
        else:
            img = img.convert("RGB")
            canvas_mode = "RGB"
            fill = rgb[:3]

    canvas = Image.new(canvas_mode, (target_w, target_h), fill)
    offset_x = (target_w - cur_w) // 2
    offset_y = (target_h - cur_h) // 2
    canvas.paste(img, (offset_x, offset_y))
    return canvas
