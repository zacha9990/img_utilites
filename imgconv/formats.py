from PIL import Image

from .presets import SUPPORTED_FORMATS


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
    elif fmt == "AVIF":
        if img.mode not in ("RGB", "RGBA"):
            return img.convert("RGB")
    elif fmt not in ("PNG", "WEBP", "GIF", "BMP", "TIFF"):
        if img.mode not in ("RGB", "L"):
            return img.convert("RGB")
    return img
