# img_utilities

CLI tool Python untuk memproses gambar: resize, smart crop, konversi format, color grading, tone matching, dan rounded corners.

## Instalasi

```bash
pip install Pillow
pip install numpy          # opsional, untuk tone/color matching yang lebih akurat
pip install opencv-python  # opsional, untuk face detection saat crop
```

## Penggunaan

```bash
python imgconv.py <input> [opsi...]
```

## Fitur

| Fitur | Argumen |
|---|---|
| Resize | `--size 800x600`, `--size 50%` |
| Smart crop | `--crop 16:9`, `--crop square` |
| Konversi format | `--format webp` |
| Tone preset | `--tone warm/cool/vintage/fade/vibrant/dramatic/matte` |
| Tone matching dari referensi | `--match-tone ref.jpg` |
| Color matching dari referensi | `--match-color ref.jpg` |
| Rounded corners | `--radius 30` atau `--radius 5%` |
| Penyesuaian manual | `--brightness`, `--contrast`, `--saturation`, `--temperature` |

## Contoh

```bash
# Resize dan konversi
python imgconv.py foto.jpg --size 1280x --format webp

# Smart crop ke 16:9 dengan face detection
python imgconv.py foto.jpg --crop 16:9

# Samakan tone batch foto ke satu referensi
python imgconv.py *.jpg --match-tone referensi.jpg --output ./output/

# Rounded corners
python imgconv.py foto.jpg --radius 24 --output foto_rounded.png

# Avatar lingkaran
python imgconv.py foto.jpg --crop square --size 500x500 --radius 50% --output avatar.png

# Kombinasi lengkap
python imgconv.py *.jpg --crop 1.33 --size 381x287 --match-tone ref.jpg --radius 24 --output ./out/
```

## Dokumentasi

Lihat [DOCS.md](DOCS.md) untuk dokumentasi lengkap semua fitur dan argumen.
