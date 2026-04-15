# imgconv.py — Dokumentasi Lengkap

[![GitHub](https://img.shields.io/badge/GitHub-img__utilites-blue)](https://github.com/zacha9990/img_utilites)

Tool CLI Python untuk resize, smart crop, konversi format, color grading, rounded corners, rotate, flip, letterbox padding, dan batch paralel.

**Repository:** https://github.com/zacha9990/img_utilites

## Daftar Isi

- [Instalasi](#instalasi)
- [Penggunaan Dasar](#penggunaan-dasar)
- [Fitur: Resize](#fitur-resize)
- [Fitur: Letterbox / Padding](#fitur-letterbox--padding)
- [Fitur: Smart Crop](#fitur-smart-crop)
- [Fitur: Rotate & Flip](#fitur-rotate--flip)
- [Fitur: Konversi Format](#fitur-konversi-format)
- [Fitur: Strip EXIF](#fitur-strip-exif)
- [Fitur: Rounded Corners](#fitur-rounded-corners)
- [Fitur: Color Grading](#fitur-color-grading)
  - [Tone Preset](#tone-preset)
  - [Penyesuaian Manual](#penyesuaian-manual)
  - [Tone Matching dari Referensi](#tone-matching-dari-referensi)
  - [Color Matching dari Referensi](#color-matching-dari-referensi)
  - [Perbandingan match-tone vs match-color](#perbandingan-match-tone-vs-match-color)
  - [Urutan Pemrosesan](#urutan-pemrosesan)
- [Opsi Output](#opsi-output)
- [Batch Processing](#batch-processing)
- [Referensi Argumen](#referensi-argumen)
- [Struktur Proyek](#struktur-proyek)

---

## Instalasi

**Dependensi wajib:**

```bash
pip install Pillow>=9.0.0
```

**Dependensi direkomendasikan** (aktifkan fitur penuh):

```bash
pip install numpy tqdm
```

- `numpy` → LAB-space color/tone matching yang lebih akurat
- `tqdm` → progress bar saat batch processing

**Dependensi opsional:**

```bash
pip install opencv-python    # Face detection untuk smart crop
```

**Install semuanya:**

```bash
pip install -r requirements.txt
# atau
pip install ".[full]"
```

---

## Penggunaan Dasar

```bash
python imgconv.py <input> [opsi...]
# atau lewat package
python -m imgconv <input> [opsi...]
```

Minimal satu opsi harus diberikan. Beberapa opsi bisa dikombinasikan sekaligus.

```bash
# Satu file
python imgconv.py foto.jpg --tone warm

# Beberapa file sekaligus
python imgconv.py foto1.jpg foto2.jpg foto3.jpg --tone vintage

# Wildcard / glob
python imgconv.py *.jpg --match-tone referensi.jpg --output ./output/
```

---

## Fitur: Resize

Mengubah ukuran gambar. Secara default **proporsional** (tidak melar).

### Opsi

| Argumen | Keterangan |
|---|---|
| `-s`, `--size SIZE` | Target ukuran |
| `--stretch` | Resize paksa ke WxH tanpa mempertahankan rasio |
| `--resample FILTER` | Filter resampling: `lanczos` (default), `bicubic`, `bilinear`, `nearest` |
| `--no-upscale` | Skip resize jika hasilnya lebih besar dari ukuran asli |

### Format SIZE

| Format | Contoh | Perilaku |
|---|---|---|
| `WxH` | `800x600` | Proporsional, muat di dalam 800×600 |
| `Wx` | `800x` | Lebar 800 px, tinggi otomatis |
| `xH` | `x600` | Tinggi 600 px, lebar otomatis |
| `N%` | `50%` | Skala ke N% dari ukuran asli |

### Contoh

```bash
python imgconv.py foto.jpg --size 1920x1080
python imgconv.py foto.jpg --size 800x
python imgconv.py foto.jpg --size 50%
python imgconv.py foto.jpg --size 500x500 --stretch
python imgconv.py foto.jpg --size 1920x1080 --no-upscale   # tidak diperbesar
```

---

## Fitur: Letterbox / Padding

Fit gambar ke ukuran tertentu **tanpa crop** — area kosong diisi padding (warna atau transparan). Berguna untuk thumbnail e-commerce, posting media sosial, dll.

### Opsi

| Argumen | Keterangan |
|---|---|
| `--pad` | Aktifkan letterbox mode (butuh `--size WxH`) |
| `--pad-color COLOR` | Warna padding: nama warna, `#hex`, atau `transparent` (default: `black`) |

### Perilaku

1. Gambar di-resize secara proporsional agar muat di dalam `WxH`
2. Canvas `WxH` dibuat dengan `pad-color`
3. Gambar di-paste di tengah canvas

### Catatan

- `--pad` hanya berlaku jika `--size WxH` (kedua dimensi harus ditentukan)
- `--pad-color transparent` menghasilkan RGBA; output auto-switch ke PNG/WebP jika format tidak mendukung alpha
- `--no-upscale` + `--pad` = konten gambar tidak diperbesar, tapi canvas tetap dicapai ukuran penuh

### Contoh

```bash
# Letterbox 1920x1080 dengan background hitam
python imgconv.py foto.jpg --size 1920x1080 --pad

# Background putih
python imgconv.py foto.jpg --size 800x800 --pad --pad-color white

# Background warna custom
python imgconv.py foto.jpg --size 800x600 --pad --pad-color "#1a1a2e"

# Background transparan (output PNG)
python imgconv.py foto.jpg --size 500x500 --pad --pad-color transparent --format png

# Batch thumbnail produk
python imgconv.py *.jpg --size 800x800 --pad --pad-color white --output ./thumbnails/
```

---

## Fitur: Smart Crop

Memotong gambar ke rasio aspek tertentu secara cerdas.

### Opsi

| Argumen | Keterangan |
|---|---|
| `-c`, `--crop RATIO` | Target rasio aspek |
| `--crop-method METHOD` | Strategi crop: `auto` (default), `faces`, `entropy`, `center` |

### Format RATIO

| Format | Contoh |
|---|---|
| Preset nama | `landscape`, `portrait`, `square` |
| Rasio kolom:baris | `16:9`, `4:3`, `1:1`, `9:16`, `3:2`, `21:9`, `5:4` |
| Bilangan desimal | `1.78`, `0.5625` |

### Strategi Crop (`--crop-method`)

| Strategi | Perilaku |
|---|---|
| `auto` | Coba deteksi wajah, fallback ke entropy (default) |
| `faces` | Pusatkan crop pada wajah yang terdeteksi (butuh OpenCV) |
| `entropy` | Pilih area dengan detail visual terbanyak |
| `center` | Center crop sederhana |

### Contoh

```bash
python imgconv.py foto.jpg --crop 16:9
python imgconv.py foto.jpg --crop portrait --crop-method faces
python imgconv.py foto.jpg --crop 16:9 --size 1920x1080
```

---

## Fitur: Rotate & Flip

### Rotate

Memutar gambar. Canvas otomatis diperbesar agar gambar muat.

| Argumen | Keterangan |
|---|---|
| `--rotate DEG` | Putar searah jarum jam `DEG` derajat (bisa desimal) |

```bash
python imgconv.py foto.jpg --rotate 90          # 90° searah jarum jam
python imgconv.py foto.jpg --rotate -90         # 90° berlawanan jarum jam
python imgconv.py foto.jpg --rotate 180         # balik 180°
python imgconv.py foto.jpg --rotate 45          # 45° (canvas diperlebar)
python imgconv.py *.jpg --rotate 90 --output ./rotated/
```

### Flip

Membalik gambar secara horizontal, vertikal, atau keduanya.

| Argumen | Nilai | Keterangan |
|---|---|---|
| `--flip DIR` | `h` / `horizontal` | Mirror kiri-kanan |
| | `v` / `vertical` | Balik atas-bawah |
| | `both` | Keduanya |

```bash
python imgconv.py foto.jpg --flip h              # mirror
python imgconv.py foto.jpg --flip v              # flip vertikal
python imgconv.py foto.jpg --flip both
python imgconv.py *.jpg --flip h --output ./mirrored/
```

---

## Fitur: Konversi Format

### Opsi

| Argumen | Keterangan |
|---|---|
| `-f`, `--format FMT` | Format output |
| `-q`, `--quality N` | Kualitas 1–95 untuk JPEG/WebP/AVIF (default: 85) |

### Format yang Didukung

| Ekstensi | Format |
|---|---|
| `jpg`, `jpeg` | JPEG |
| `png` | PNG |
| `webp` | WebP |
| `avif` | AVIF (butuh Pillow ≥ 9.1 dengan dukungan libavif) |
| `bmp` | BMP |
| `gif` | GIF |
| `tiff`, `tif` | TIFF |
| `ico` | ICO |

### Contoh

```bash
python imgconv.py foto.jpg --format webp --quality 90
python imgconv.py foto.jpg --format avif
python imgconv.py *.jpg --format webp --output ./webp/
```

---

## Fitur: Strip EXIF

Menghapus metadata EXIF dan ICC profile dari output — berguna untuk privasi (GPS, info perangkat) sebelum publish ke web.

| Argumen | Keterangan |
|---|---|
| `--strip-exif` | Hapus EXIF dan ICC metadata |

```bash
python imgconv.py foto.jpg --strip-exif --format webp
python imgconv.py *.jpg --strip-exif --output ./clean/
```

---

## Fitur: Rounded Corners

Membuat pojok gambar melengkung (area sudut transparan). Output otomatis ke PNG/WebP/AVIF.

### Opsi

| Argumen | Keterangan |
|---|---|
| `--radius N` | Radius dalam piksel (`30`) atau persen sisi terpendek (`5%`) |

### Contoh

```bash
python imgconv.py foto.jpg --radius 30
python imgconv.py foto.jpg --radius 5%
python imgconv.py foto.jpg --crop square --size 500x500 --radius 50% --output avatar.png
python imgconv.py *.jpg --radius 30 --output ./rounded/
```

---

## Fitur: Color Grading

---

### Tone Preset

```bash
--tone PRESET
```

| Preset | Efek |
|---|---|
| `warm` | Hangat kemerahan/kekuningan |
| `cool` | Dingin kebiruan/cyan |
| `vintage` | Kekuningan, kontras rendah, gaya film lama |
| `fade` | Bayangan terangkat, warna pudar |
| `vibrant` | Warna sangat jenuh dan vivid |
| `dramatic` | Kontras tinggi, hampir monokrom |
| `matte` | Blacks terangkat, flat/milky look |

```bash
python imgconv.py foto.jpg --tone warm
python imgconv.py *.jpg --tone matte --output ./matte/
```

---

### Penyesuaian Manual

| Argumen | Default | Rentang | Keterangan |
|---|---|---|---|
| `--brightness N` | `1.0` | `0.5`–`2.0` | Kecerahan |
| `--contrast N` | `1.0` | `0.5`–`2.0` | Kontras |
| `--saturation N` | `1.0` | `0.0`–`2.0` | Saturasi; `0` = grayscale |
| `--temperature N` | `0` | `-100`–`+100` | Suhu warna: negatif = lebih hangat |

```bash
python imgconv.py foto.jpg --brightness 1.2 --saturation 1.3
python imgconv.py foto.jpg --saturation 0       # grayscale
python imgconv.py foto.jpg --temperature -50    # hangat
```

---

### Tone Matching dari Referensi

```bash
--match-tone REF
```

CDF-based histogram matching di ruang warna CIE LAB. Menyamakan distribusi pixel penuh termasuk kurva exposure, shadow/midtone/highlight, dan warna.

```bash
python imgconv.py foto.jpg --match-tone referensi.jpg
python imgconv.py *.jpg --match-tone golden_hour.jpg --output ./matched/
```

---

### Color Matching dari Referensi

```bash
--match-color REF
```

Reinhard LAB mean/std transfer — lebih cepat, cocok untuk menerapkan mood warna umum.

```bash
python imgconv.py foto.jpg --match-color referensi.jpg
python imgconv.py *.jpg --match-color cinematic.jpg --output ./graded/
```

---

### Perbandingan match-tone vs match-color

| | `--match-tone` | `--match-color` |
|---|---|---|
| **Algoritma** | Histogram CDF matching | Reinhard LAB mean/std transfer |
| **Akurasi** | Sangat tinggi | Sedang |
| **Kecepatan** | Lebih lambat | Lebih cepat |
| **Cocok untuk** | Menyeragamkan batch secara akurat | Menerapkan mood warna umum |

---

### Urutan Pemrosesan

```
crop → resize → pad → rotate → flip →
match-tone → match-color → tone preset → manual adjustments →
rounded corners → save
```

---

## Opsi Output

| Argumen | Keterangan |
|---|---|
| `-o`, `--output PATH` | File output atau direktori tujuan |
| `--overwrite` | Timpa file jika sudah ada (default: skip) |
| `--dry-run` | Preview operasi tanpa menulis file apapun |

```bash
python imgconv.py foto.jpg --tone warm --output foto_warm.jpg
python imgconv.py *.jpg --tone warm --output ./output/
python imgconv.py *.jpg --tone warm --dry-run    # cek dulu sebelum proses
```

---

## Batch Processing

Semua fitur mendukung pemrosesan banyak file sekaligus. Gunakan `-j N` untuk pemrosesan paralel.

```bash
# Batch sekuensial
python imgconv.py *.jpg --match-tone referensi.jpg --output ./matched/

# Batch paralel (4 worker processes)
python imgconv.py *.jpg --match-tone ref.jpg -j 4 --output ./matched/

# Deteksi jumlah CPU otomatis (coba python -c "import os; print(os.cpu_count())")
python imgconv.py *.jpg --tone vintage -j 8 --output ./out/

# Beberapa file eksplisit
python imgconv.py a.jpg b.jpg c.jpg --size 1280x --output ./resized/

# Kombinasi lengkap + paralel
python imgconv.py *.jpg --match-tone ref.jpg --size 1920x --format webp -j 4 --output ./out/
```

**Catatan:** Progress bar otomatis tampil saat batch jika `tqdm` terinstal (`pip install tqdm`).

---

## Referensi Argumen

| Argumen | Pendek | Tipe | Default | Keterangan |
|---|---|---|---|---|
| `inputs` | — | positional | — | Satu atau lebih file input |
| `--size` | `-s` | string | — | Target ukuran: `WxH`, `Wx`, `xH`, `N%` |
| `--stretch` | — | flag | `false` | Resize non-proporsional |
| `--no-upscale` | — | flag | `false` | Skip resize jika akan memperbesar |
| `--resample` | — | pilihan | `lanczos` | Filter resampling |
| `--pad` | — | flag | `false` | Letterbox mode (butuh `--size WxH`) |
| `--pad-color` | — | string | `black` | Warna padding |
| `--crop` | `-c` | string | — | Target rasio crop |
| `--crop-method` | — | pilihan | `auto` | Strategi crop |
| `--rotate` | — | float | — | Rotasi searah jarum jam dalam derajat |
| `--flip` | — | `h`/`v`/`both` | — | Flip gambar |
| `--format` | `-f` | string | — | Format output |
| `--quality` | `-q` | int 1–95 | `85` | Kualitas JPEG/WebP/AVIF |
| `--output` | `-o` | path | auto | File atau direktori output |
| `--overwrite` | — | flag | `false` | Izinkan timpa file |
| `--strip-exif` | — | flag | `false` | Hapus metadata EXIF/ICC |
| `--tone` | — | string | — | Preset tone warna |
| `--radius` | — | string | — | Radius sudut: piksel atau persen |
| `--match-tone` | — | path | — | Referensi histogram tone matching |
| `--match-color` | — | path | — | Referensi LAB color transfer |
| `--brightness` | — | float | `1.0` | Kecerahan |
| `--contrast` | — | float | `1.0` | Kontras |
| `--saturation` | — | float | `1.0` | Saturasi |
| `--temperature` | — | int | `0` | Suhu warna |
| `--jobs` | `-j` | int | `1` | Jumlah worker paralel |
| `--dry-run` | — | flag | `false` | Preview tanpa menulis file |

---

## Struktur Proyek

```
imgconv/           # Package utama
├── __init__.py
├── __main__.py    # Entry point: python -m imgconv
├── cli.py         # Argument parsing dan main()
├── pipeline.py    # Pipeline process_image() dan worker paralel
├── crop.py        # Smart crop (entropy, face detection)
├── color.py       # Color grading, tone/color matching, LAB conversions
├── transforms.py  # Resize, rotate, flip, padding, rounded corners
├── formats.py     # Format conversion helpers
└── presets.py     # Konstanta: SUPPORTED_FORMATS, TONE_PRESETS, CROP_PRESETS

imgconv.py         # Shim backward-compatible (python imgconv.py ...)
requirements.txt   # Dependencies
pyproject.toml     # Build config + optional deps
```
