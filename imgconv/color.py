from PIL import Image, ImageEnhance, ImageStat

from .presets import TONE_PRESETS


# ---------------------------------------------------------------------------
# Basic adjustments
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


# ---------------------------------------------------------------------------
# LAB color space helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Color matching
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tone matching (histogram CDF)
# ---------------------------------------------------------------------------

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
