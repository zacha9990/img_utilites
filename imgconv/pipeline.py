import sys
from pathlib import Path

from PIL import Image, ImageOps

from .presets import SUPPORTED_FORMATS
from .formats import fix_mode_for_format
from .crop import smart_crop
from .color import apply_color_adjustments, apply_tone_preset, match_color, match_tone
from .transforms import (
    apply_flip,
    apply_padding,
    apply_rotate,
    apply_rounded_corners,
    compute_new_size,
)

RESAMPLE_FILTERS = {
    "lanczos":  Image.LANCZOS,
    "bicubic":  Image.BICUBIC,
    "bilinear": Image.BILINEAR,
    "nearest":  Image.NEAREST,
}


def process_image(
    input_path,
    output_path,
    size_spec=None,
    stretch=False,
    no_upscale=False,
    quality=85,
    resample="lanczos",
    crop_ratio=None,
    crop_method="auto",
    rotate=None,
    flip=None,
    pad=False,
    pad_color="black",
    tone=None,
    brightness=1.0,
    contrast=1.0,
    saturation=1.0,
    temperature=0,
    match_ref=None,
    match_tone_ref=None,
    corner_radius=None,
    strip_exif=False,
    dry_run=False,
):
    """
    Process a single image through the full pipeline.

    Pipeline order:
      crop → resize → pad → rotate → flip →
      match-tone → match-color → tone preset → manual adjustments →
      rounded corners → save

    Returns the final output Path (may differ from input if format was auto-switched).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    img = ImageOps.exif_transpose(Image.open(input_path))

    # Step 1: Smart crop
    if crop_ratio is not None:
        img = smart_crop(img, crop_ratio, method=crop_method)

    # Step 2: Resize
    if size_spec:
        cur_w, cur_h = img.size
        new_w, new_h = compute_new_size(cur_w, cur_h, size_spec, stretch, no_upscale)
        if (new_w, new_h) != (cur_w, cur_h):
            img = img.resize((new_w, new_h), RESAMPLE_FILTERS[resample])
            print(f"  Resize: {cur_w}x{cur_h} → {new_w}x{new_h}")
        elif no_upscale:
            print(f"  Resize: {cur_w}x{cur_h} (skipped — already at or below target, no-upscale)")

    # Step 3: Pad to exact canvas size (letterbox)
    if pad and size_spec and size_spec[0] == "pixels" and size_spec[1] and size_spec[2]:
        target_w, target_h = size_spec[1], size_spec[2]
        before_w, before_h = img.size
        if (before_w, before_h) != (target_w, target_h):
            img = apply_padding(img, target_w, target_h, pad_color)
            print(f"  Pad   : {before_w}x{before_h} → {target_w}x{target_h}  (color: {pad_color})")

    # Step 4: Rotate
    if rotate is not None:
        before_w, before_h = img.size
        img = apply_rotate(img, rotate)
        print(f"  Rotate: {rotate:g}° clockwise  {before_w}x{before_h} → {img.width}x{img.height}")

    # Step 5: Flip
    if flip is not None:
        img = apply_flip(img, flip)
        label = {"h": "horizontal", "v": "vertical", "both": "both axes"}.get(flip, flip)
        print(f"  Flip  : {label}")

    # Step 6: Tone / color matching
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

    # Step 7: Rounded corners
    if corner_radius is not None:
        val, unit = corner_radius
        img = apply_rounded_corners(img, corner_radius)
        label = f"{val}{'%' if unit == '%' else 'px'}"
        print(f"  Radius: {label} rounded corners applied")

    # Step 8: Determine output format
    ext = output_path.suffix.lstrip(".").lower()
    fmt = SUPPORTED_FORMATS.get(ext)
    if not fmt:
        print(f"Error: Unsupported output format '.{ext}'")
        print(f"Supported: {', '.join(sorted(set(SUPPORTED_FORMATS.values())))}")
        sys.exit(1)

    # Rounded corners require alpha — auto-switch to PNG if format can't carry it
    if corner_radius is not None and fmt not in ("PNG", "WEBP", "AVIF"):
        new_path = output_path.with_suffix(".png")
        print(f"  Note  : {fmt} doesn't support transparency — saving as PNG instead")
        print(f"          {output_path.name} → {new_path.name}")
        output_path = new_path
        fmt = "PNG"

    if dry_run:
        print(f"  DryRun: would save → {output_path}")
        return output_path

    # Step 9: Save
    img = fix_mode_for_format(img, fmt)

    save_kwargs = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
        if strip_exif:
            save_kwargs["exif"] = b""
    elif fmt == "PNG":
        save_kwargs["optimize"] = True
    elif fmt in ("WEBP", "AVIF"):
        save_kwargs["quality"] = quality
        if strip_exif:
            save_kwargs["exif"] = b""

    if strip_exif and hasattr(img, "info"):
        img.info.pop("exif", None)
        img.info.pop("icc_profile", None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format=fmt, **save_kwargs)
    size_kb = output_path.stat().st_size / 1024
    print(f"  Saved : {output_path}  ({size_kb:.1f} KB)")
    return output_path


# ---------------------------------------------------------------------------
# Worker for parallel processing
# ---------------------------------------------------------------------------

def _process_worker(params):
    """
    Top-level picklable worker for ProcessPoolExecutor.
    Accepts a dict with 'input_path', 'output_path', and all process_image kwargs.
    Returns (success: bool, path: str, error: str|None).
    """
    input_path = params["input_path"]
    output_path = params["output_path"]
    kwargs = {k: v for k, v in params.items() if k not in ("input_path", "output_path")}
    print(f"Processing: {input_path}")
    try:
        final = process_image(input_path, output_path, **kwargs)
        return (True, str(final), None)
    except Exception as e:
        return (False, str(input_path), str(e))
