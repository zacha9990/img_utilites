# img_utilities

CLI tool Python untuk memproses gambar: resize, smart crop, konversi format, color grading, tone matching, rounded corners, rotate, flip, letterbox padding, dan batch paralel.

## Instalasi

```bash
pip install Pillow                    # wajib
pip install numpy tqdm                # direkomendasikan
pip install opencv-python             # opsional, untuk face detection
```

Atau install semua sekaligus:

```bash
pip install -r requirements.txt
```

Atau via pyproject.toml:

```bash
pip install ".[full]"                 # Pillow + numpy + tqdm + opencv
pip install ".[recommended]"          # Pillow + numpy + tqdm
```

## Penggunaan

```bash
python imgconv.py <input> [opsi...]
# atau
python -m imgconv <input> [opsi...]
```

## Fitur

| Fitur | Argumen |
|---|---|
| Resize | `--size 800x600`, `--size 50%` |
| Letterbox / padding | `--size 800x600 --pad`, `--pad-color black` |
| Tanpa upscale | `--no-upscale` |
| Smart crop | `--crop 16:9`, `--crop square` |
| Rotate | `--rotate 90` |
| Flip | `--flip h`, `--flip v`, `--flip both` |
| Konversi format | `--format webp`, `--format avif` |
| Strip EXIF | `--strip-exif` |
| Tone preset | `--tone warm/cool/vintage/fade/vibrant/dramatic/matte` |
| Tone matching dari referensi | `--match-tone ref.jpg` |
| Color matching dari referensi | `--match-color ref.jpg` |
| Rounded corners | `--radius 30` atau `--radius 5%` |
| Penyesuaian manual | `--brightness`, `--contrast`, `--saturation`, `--temperature` |
| Batch paralel | `-j 4` (4 worker processes) |
| Preview tanpa simpan | `--dry-run` |

## Contoh

```bash
# Resize dan konversi
python imgconv.py foto.jpg --size 1280x --format webp

# Letterbox: fit ke 1920x1080 dengan padding hitam
python imgconv.py foto.jpg --size 1920x1080 --pad

# Letterbox dengan padding transparan (output PNG)
python imgconv.py foto.jpg --size 1920x1080 --pad --pad-color transparent --format png

# Resize tapi jangan upscale
python imgconv.py foto.jpg --size 1920x1080 --no-upscale

# Rotate 90° searah jarum jam
python imgconv.py foto.jpg --rotate 90 --output foto_rotated.jpg

# Flip horizontal (mirror)
python imgconv.py foto.jpg --flip h

# Smart crop ke 16:9 dengan face detection
python imgconv.py foto.jpg --crop 16:9

# Samakan tone batch foto ke satu referensi (4 worker paralel)
python imgconv.py *.jpg --match-tone referensi.jpg --output ./output/ -j 4

# Rounded corners
python imgconv.py foto.jpg --radius 24 --output foto_rounded.png

# Avatar lingkaran
python imgconv.py foto.jpg --crop square --size 500x500 --radius 50% --output avatar.png

# Hapus EXIF sebelum publish
python imgconv.py foto.jpg --strip-exif --format webp

# Preview batch tanpa menulis file
python imgconv.py *.jpg --tone warm --output ./out/ --dry-run

# Kombinasi lengkap
python imgconv.py *.jpg --crop 1.33 --size 381x287 --match-tone ref.jpg --radius 24 --output ./out/
```

## Dokumentasi

Lihat [DOCS.md](DOCS.md) untuk dokumentasi lengkap semua fitur dan argumen.
