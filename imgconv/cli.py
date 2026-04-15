import argparse
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .presets import TONE_PRESETS
from .transforms import parse_radius, parse_size
from .crop import parse_crop_ratio
from .pipeline import _process_worker, process_image

try:
    from tqdm import tqdm as _tqdm
    _HAS_TQDM = True
except ImportError:
    _HAS_TQDM = False


def _tqdm_or_list(iterable, **kwargs):
    """Wrap with tqdm if available, otherwise return the iterable as-is."""
    if _HAS_TQDM and kwargs.get("total", 1) > 1:
        return _tqdm(iterable, **kwargs)
    return iterable


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
    if getattr(args, "rotate", None) is not None:
        stem += f"_rot{int(args.rotate)}"
    if getattr(args, "flip", None):
        stem += f"_flip{args.flip[0]}"
    ext = input_path.suffix
    if args.format:
        ext = f".{args.format.lower()}"

    return input_path.parent / f"{stem}{ext}"


def main():
    tone_list = ", ".join(TONE_PRESETS)
    parser = argparse.ArgumentParser(
        description="Resize, smart crop, convert, and color grade images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Crop examples:
  --crop 16:9           smart crop to landscape 16:9
  --crop 9:16           smart crop to portrait
  --crop 1:1            smart crop to square
  --crop landscape      alias for 16:9
  --crop portrait       alias for 9:16
  --crop square         alias for 1:1

  By default uses face detection (if OpenCV installed), else entropy.
  Override with --crop-method: auto | faces | entropy | center

Size examples:
  --size 800x600        proportional resize (fits inside 800x600)
  --size 800x           width 800, height auto
  --size x600           height 600, width auto
  --size 50%            scale to 50%
  --size 800x600 --pad  letterbox: resize + add padding to reach exactly 800x600
  --size 800x600 --no-upscale  skip if image is already smaller

Transform examples:
  --rotate 90           rotate 90° clockwise
  --rotate -90          rotate 90° counter-clockwise
  --rotate 45           rotate 45° (canvas expands to fit)
  --flip h              flip left-right
  --flip v              flip top-bottom
  --flip both           flip both axes

Format examples:
  --format png          convert to PNG
  --format webp         convert to WebP
  --format avif         convert to AVIF (requires Pillow with AVIF support)

Color/tone examples:
  --tone warm                       apply warm preset
  --tone vintage                    apply vintage look
  --match-tone ref.jpg              match full tone curve + color (histogram CDF)
  --match-color ref.jpg             match color cast (LAB mean/std transfer)
  --brightness 1.2 --saturation 1.3 manual adjustments
  --temperature -30                 warmer color temperature

  Tone presets: {tone_list}

Metadata examples:
  --strip-exif          remove all EXIF/metadata from output

Batch / performance examples:
  python imgconv.py *.jpg --tone warm --output ./out/
  python imgconv.py *.jpg --match-tone ref.jpg -j 4 --output ./out/   (4 parallel workers)
  python imgconv.py *.jpg --tone warm --dry-run                        (preview only)

Combined examples:
  python imgconv.py photo.jpg --crop 1:1 --size 500x500 --radius 50% --output avatar.png
  python imgconv.py photo.jpg --size 1920x1080 --pad --pad-color "#1a1a1a"
  python imgconv.py *.jpg --rotate 90 --format webp --output ./rotated/
  python imgconv.py *.jpg --match-tone golden_hour.jpg -j 8 --output ./matched/
        """,
    )

    # Inputs
    parser.add_argument("inputs", nargs="+", help="Input image file(s)")

    # Resize
    parser.add_argument("-s", "--size", metavar="SIZE",
                        help="Target size: WxH, Wx, xH, or N%%")
    parser.add_argument("--stretch", action="store_true",
                        help="Non-proportional resize (stretch to exact WxH)")
    parser.add_argument("--no-upscale", action="store_true", dest="no_upscale",
                        help="Skip resize if it would enlarge the image")
    parser.add_argument("--resample", default="lanczos",
                        choices=["lanczos", "bicubic", "bilinear", "nearest"],
                        help="Resampling filter (default: lanczos)")

    # Padding / letterbox
    parser.add_argument("--pad", action="store_true",
                        help="Add padding to fill exactly --size WxH (letterbox mode)")
    parser.add_argument("--pad-color", default="black", dest="pad_color", metavar="COLOR",
                        help="Padding fill color: name, #hex, or 'transparent' (default: black)")

    # Crop
    parser.add_argument("-c", "--crop", metavar="RATIO",
                        help="Smart crop to aspect ratio: 16:9, 4:3, 1:1, landscape, portrait, square")
    parser.add_argument("--crop-method", default="auto",
                        choices=["auto", "faces", "entropy", "center"],
                        help="Crop strategy (default: auto = faces then entropy)")

    # Transforms
    parser.add_argument("--rotate", type=float, metavar="DEG",
                        help="Rotate clockwise by DEG degrees (canvas expands to fit)")
    parser.add_argument("--flip", choices=["h", "v", "both"], metavar="DIR",
                        help="Flip: h (horizontal/mirror), v (vertical), both")

    # Format / output
    parser.add_argument("-f", "--format", metavar="FMT",
                        help="Output format: jpg, png, webp, avif, bmp, gif, tiff, ico")
    parser.add_argument("-o", "--output", metavar="PATH",
                        help="Output file or directory (default: auto-named next to input)")
    parser.add_argument("-q", "--quality", type=int, default=85, metavar="N",
                        help="JPEG/WebP/AVIF quality 1–95 (default: 85)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite output if it already exists")
    parser.add_argument("--strip-exif", action="store_true", dest="strip_exif",
                        help="Remove EXIF and ICC metadata from output")

    # Color grading
    parser.add_argument("--tone", metavar="PRESET",
                        help=f"Color tone preset: {tone_list}")
    parser.add_argument("--radius", metavar="N",
                        help="Rounded corner radius: pixels (30) or percent of shorter side (5%%). "
                             "Output auto-switches to PNG/WebP/AVIF if needed.")
    parser.add_argument("--match-tone", metavar="REF", dest="match_tone",
                        help="Match tone+color from reference via histogram (CDF) matching")
    parser.add_argument("--match-color", metavar="REF", dest="match_color",
                        help="Match color cast from reference via LAB mean/std transfer")
    parser.add_argument("--brightness", type=float, default=1.0, metavar="N",
                        help="Brightness multiplier, e.g. 1.2 (default: 1.0)")
    parser.add_argument("--contrast", type=float, default=1.0, metavar="N",
                        help="Contrast multiplier, e.g. 1.3 (default: 1.0)")
    parser.add_argument("--saturation", type=float, default=1.0, metavar="N",
                        help="Saturation multiplier, e.g. 1.5; 0 = grayscale (default: 1.0)")
    parser.add_argument("--temperature", type=int, default=0, metavar="N",
                        help="Color temperature: negative=warmer, positive=cooler (default: 0)")

    # Batch / performance
    parser.add_argument("-j", "--jobs", type=int, default=1, metavar="N",
                        help="Parallel worker processes for batch (default: 1)")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Preview what would happen without writing any files")

    args = parser.parse_args()

    # ---------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------
    has_color = (args.tone or args.match_color or args.match_tone
                 or args.brightness != 1.0 or args.contrast != 1.0
                 or args.saturation != 1.0 or args.temperature != 0)
    has_transform = args.rotate is not None or args.flip is not None
    if not (args.size or args.format or args.crop or has_color or args.radius
            or has_transform or args.strip_exif):
        parser.error(
            "Specify at least one of: --size, --crop, --format, --radius, --rotate, --flip, "
            "--tone, --match-tone, --match-color, --brightness, --contrast, "
            "--saturation, --temperature, --strip-exif"
        )

    if args.pad:
        if not args.size:
            parser.error("--pad requires --size WxH")
        try:
            _ss = parse_size(args.size)
        except ValueError:
            _ss = None
        if _ss is None or _ss[0] != "pixels" or not _ss[1] or not _ss[2]:
            parser.error("--pad requires --size WxH with both width and height specified (e.g. 800x600)")

    # Parse complex args
    corner_radius = None
    if args.radius:
        try:
            corner_radius = parse_radius(args.radius)
        except ValueError as e:
            parser.error(f"--radius: {e}")

    size_spec = None
    if args.size:
        try:
            size_spec = parse_size(args.size)
        except ValueError as e:
            parser.error(f"--size: {e}")

    crop_ratio = None
    if args.crop:
        try:
            crop_ratio = parse_crop_ratio(args.crop)
        except ValueError as e:
            parser.error(f"--crop: {e}")

    # ---------------------------------------------------------------------------
    # Collect files to process
    # ---------------------------------------------------------------------------
    file_pairs = []
    for input_str in args.inputs:
        if "*" in input_str or "?" in input_str:
            p = Path(input_str)
            base_dir = p.parent if p.parent != Path(".") else Path(".")
            paths = sorted(base_dir.glob(p.name))
        else:
            paths = [Path(input_str)]

        if not paths:
            print(f"Warning: No files matched '{input_str}'")
            continue

        for input_path in paths:
            if not input_path.exists():
                print(f"Error: File not found: {input_path}")
                continue

            output_path = build_output_path(input_path, args)
            if output_path == input_path and not args.overwrite:
                output_path = input_path.parent / f"{input_path.stem}_out{input_path.suffix}"

            if output_path.exists() and not args.overwrite:
                print(f"Skip: {output_path} already exists (use --overwrite to replace)")
                continue

            file_pairs.append((input_path, output_path))

    if not file_pairs:
        sys.exit(0)

    # ---------------------------------------------------------------------------
    # Common kwargs for process_image
    # ---------------------------------------------------------------------------
    common_kwargs = dict(
        size_spec=size_spec,
        stretch=args.stretch,
        no_upscale=args.no_upscale,
        quality=args.quality,
        resample=args.resample,
        crop_ratio=crop_ratio,
        crop_method=args.crop_method,
        rotate=args.rotate,
        flip=args.flip,
        pad=args.pad,
        pad_color=args.pad_color,
        tone=args.tone,
        brightness=args.brightness,
        contrast=args.contrast,
        saturation=args.saturation,
        temperature=args.temperature,
        match_ref=args.match_color,
        match_tone_ref=args.match_tone,
        corner_radius=corner_radius,
        strip_exif=args.strip_exif,
        dry_run=args.dry_run,
    )

    errors = 0
    n = len(file_pairs)

    # ---------------------------------------------------------------------------
    # Parallel execution
    # ---------------------------------------------------------------------------
    if args.jobs > 1 and n > 1:
        params_list = [
            {"input_path": str(inp), "output_path": str(out), **common_kwargs}
            for inp, out in file_pairs
        ]
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(_process_worker, p): p["input_path"] for p in params_list}
            completed = as_completed(futures)
            if _HAS_TQDM:
                completed = _tqdm(completed, total=n, unit="img")
            for future in completed:
                success, path, err = future.result()
                if not success:
                    print(f"  Error [{Path(path).name}]: {err}")
                    errors += 1
        sys.exit(1 if errors else 0)

    # ---------------------------------------------------------------------------
    # Sequential execution
    # ---------------------------------------------------------------------------
    iterable = _tqdm_or_list(file_pairs, total=n, unit="img")
    for input_path, output_path in iterable:
        print(f"Processing: {input_path}")
        try:
            process_image(str(input_path), str(output_path), **common_kwargs)
        except Exception as e:
            print(f"  Error: {e}")
            errors += 1

    sys.exit(1 if errors else 0)
