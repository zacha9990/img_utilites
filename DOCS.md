# imgconv.py — Dokumentasi Lengkap

[![GitHub](https://img.shields.io/badge/GitHub-img__utilites-blue)](https://github.com/zacha9990/img_utilites)

Tool CLI Python untuk resize, smart crop, konversi format, color grading, dan rounded corners gambar.

**Repository:** https://github.com/zacha9990/img_utilites

## Daftar Isi

- [Instalasi](#instalasi)
- [Penggunaan Dasar](#penggunaan-dasar)
- [Fitur: Resize](#fitur-resize)
- [Fitur: Smart Crop](#fitur-smart-crop)
- [Fitur: Konversi Format](#fitur-konversi-format)
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

---

## Instalasi

**Dependensi wajib:**

```bash
pip install Pillow
```

**Dependensi opsional** (meningkatkan kualitas/fitur tertentu):

```bash
pip install numpy                  # Tone/color matching LAB yang lebih akurat
pip install opencv-python numpy    # Face detection untuk smart crop
```

---

## Penggunaan Dasar

```bash
python imgconv.py <input> [opsi...]
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

### Format SIZE

| Format | Contoh | Perilaku |
|---|---|---|
| `WxH` | `800x600` | Proporsional, muat di dalam 800×600 |
| `Wx` | `800x` | Lebar 800 px, tinggi otomatis |
| `xH` | `x600` | Tinggi 600 px, lebar otomatis |
| `N%` | `50%` | Skala ke N% dari ukuran asli |

### Opsi Tambahan

| Argumen | Keterangan |
|---|---|
| `--stretch` | Resize paksa ke WxH tanpa mempertahankan rasio |
| `--resample FILTER` | Filter resampling: `lanczos` (default), `bicubic`, `bilinear`, `nearest` |

### Contoh

```bash
# Resize proporsional, muat dalam 1920x1080
python imgconv.py foto.jpg --size 1920x1080

# Lebar 800px, tinggi mengikuti rasio
python imgconv.py foto.jpg --size 800x

# Skala 50%
python imgconv.py foto.jpg --size 50%

# Stretch paksa ke 500x500 (bisa melar)
python imgconv.py foto.jpg --size 500x500 --stretch

# Resize dengan filter bicubic
python imgconv.py foto.jpg --size 1280x --resample bicubic
```

---

## Fitur: Smart Crop

Memotong gambar ke rasio aspek tertentu secara cerdas — bukan sekadar center crop.

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

### Preset Rasio

| Preset | Rasio |
|---|---|
| `landscape` | 16:9 |
| `portrait` | 9:16 |
| `square` | 1:1 |

### Strategi Crop (`--crop-method`)

| Strategi | Perilaku |
|---|---|
| `auto` | Coba deteksi wajah, fallback ke entropy (default) |
| `faces` | Pusatkan crop pada wajah yang terdeteksi (butuh OpenCV) |
| `entropy` | Pilih area dengan detail visual terbanyak |
| `center` | Center crop sederhana |

### Contoh

```bash
# Crop ke 16:9, strategi otomatis
python imgconv.py foto.jpg --crop 16:9

# Crop portrait dengan prioritas wajah
python imgconv.py foto.jpg --crop portrait --crop-method faces

# Crop ke rasio khusus dengan entropy
python imgconv.py foto.jpg --crop 2.35 --crop-method entropy

# Crop + resize sekaligus
python imgconv.py foto.jpg --crop 16:9 --size 1920x1080
```

---

## Fitur: Konversi Format

Mengubah format gambar ke format lain.

### Opsi

| Argumen | Keterangan |
|---|---|
| `-f`, `--format FMT` | Format output |
| `-q`, `--quality N` | Kualitas 1–95 untuk JPEG/WebP (default: 85) |

### Format yang Didukung

| Ekstensi | Format |
|---|---|
| `jpg`, `jpeg` | JPEG |
| `png` | PNG |
| `webp` | WebP |
| `bmp` | BMP |
| `gif` | GIF |
| `tiff`, `tif` | TIFF |
| `ico` | ICO |

Konversi mode warna ditangani otomatis — misalnya RGBA ke JPEG akan menghasilkan background putih.

### Contoh

```bash
# Konversi ke WebP dengan kualitas tinggi
python imgconv.py foto.jpg --format webp --quality 90

# Konversi ke PNG (lossless)
python imgconv.py foto.jpg --format png

# Konversi seluruh folder ke WebP
python imgconv.py *.jpg --format webp --output ./webp/
```

---

## Fitur: Rounded Corners

Membuat pojok-pojok gambar melengkung dengan area sudut menjadi **transparan**. Karena membutuhkan alpha channel, output otomatis disimpan sebagai **PNG** (atau WebP) meskipun input berformat JPEG.

### Opsi

| Argumen | Keterangan |
|---|---|
| `--radius N` | Radius sudut dalam piksel (`30`) atau persen sisi terpendek (`5%`) |

### Format Radius

| Format | Contoh | Perilaku |
|---|---|---|
| Piksel absolut | `30` | Radius 30px di setiap sudut |
| Persen | `5%` | 5% dari sisi terpendek gambar |
| `50%` | Bentuk oval/lingkaran penuh (pill untuk landscape) |

### Catatan Format Output

Karena sudut transparan membutuhkan alpha channel:
- Output ke **PNG** atau **WebP** — berjalan normal
- Output ke **JPEG** atau format lain yang tidak mendukung alpha — otomatis diubah ke PNG dengan pesan notifikasi

### Contoh

```bash
# Rounded corners 30px
python imgconv.py foto.jpg --radius 30

# Rounded corners 5% dari sisi terpendek
python imgconv.py foto.jpg --radius 5%

# Sudut sangat melengkung (hampir oval)
python imgconv.py foto.jpg --radius 40%

# Eksplisit simpan ke PNG
python imgconv.py foto.jpg --radius 20 --format png

# Batch: semua foto dengan sudut melengkung
python imgconv.py *.jpg --radius 30 --output ./rounded/

# Kombinasi: crop square + rounded + resize
python imgconv.py foto.jpg --crop square --size 500x500 --radius 50% --output avatar.png
```

---

## Fitur: Color Grading

Mengubah warna, tone, dan nuansa gambar. Semua opsi color grading bisa dikombinasikan satu sama lain maupun dengan resize/crop.

---

### Tone Preset

Menerapkan gaya warna siap pakai dengan satu argumen.

```bash
--tone PRESET
```

| Preset | Efek |
|---|---|
| `warm` | Hangat kemerahan/kekuningan, saturasi sedikit naik |
| `cool` | Dingin kebiruan/cyan |
| `vintage` | Kekuningan, kontras rendah, sedikit gelap — gaya film lama |
| `fade` | Bayangan terangkat, warna pudar, kontras rendah |
| `vibrant` | Warna sangat jenuh dan vivid, kontras naik |
| `dramatic` | Kontras tinggi, hampir monokrom, gelap dan kuat |
| `matte` | Blacks terangkat, flat/milky look, kontras sangat rendah |

#### Contoh

```bash
python imgconv.py foto.jpg --tone warm
python imgconv.py foto.jpg --tone vintage
python imgconv.py *.jpg --tone matte --output ./matte/

# Kombinasi preset + penyesuaian manual
python imgconv.py foto.jpg --tone vintage --saturation 0.6
```

---

### Penyesuaian Manual

Kontrol granular untuk setiap aspek warna.

| Argumen | Default | Rentang Umum | Keterangan |
|---|---|---|---|
| `--brightness N` | `1.0` | `0.5` – `2.0` | Kecerahan: `<1` gelap, `>1` terang |
| `--contrast N` | `1.0` | `0.5` – `2.0` | Kontras: `<1` flat, `>1` tajam |
| `--saturation N` | `1.0` | `0.0` – `2.0` | Saturasi: `0` = grayscale, `>1` vivid |
| `--temperature N` | `0` | `-100` – `+100` | Suhu warna: negatif = lebih hangat, positif = lebih dingin |

#### Contoh

```bash
# Terangkan dan tingkatkan saturasi
python imgconv.py foto.jpg --brightness 1.2 --saturation 1.3

# Grayscale
python imgconv.py foto.jpg --saturation 0

# Tone hangat manual
python imgconv.py foto.jpg --temperature -50

# Tone dingin dengan kontras lebih rendah
python imgconv.py foto.jpg --temperature 40 --contrast 0.9

# Gabungkan semua
python imgconv.py foto.jpg --brightness 1.1 --contrast 1.2 --saturation 1.4 --temperature -20
```

---

### Tone Matching dari Referensi

Menyamakan tone **dan** warna gambar target secara akurat mengikuti satu foto referensi, menggunakan histogram CDF matching. Ini adalah cara yang tepat untuk membuat batch foto terlihat seragam.

```bash
--match-tone REF
```

#### Cara Kerja

Algoritma memetakan distribusi pixel secara penuh — bukan hanya rata-rata dan standar deviasi:

1. Hitung **CDF (Cumulative Distribution Function)** dari setiap channel di ruang warna CIE LAB
2. Untuk setiap nilai pixel sumber, temukan nilai referensi yang memiliki **ranking CDF yang sama**
3. Terapkan pemetaan tersebut ke seluruh gambar

Hasilnya: distribusi histogram output identik dengan referensi, termasuk kurva exposure, distribusi shadow/midtone/highlight, dan nuansa warna.

- Jika **numpy tersedia**: matching dilakukan di ruang warna **CIE LAB** (1024 bins per channel) — luminance dan warna diproses terpisah, hasil lebih natural
- Jika **numpy tidak ada**: fallback ke matching **RGB per-channel** menggunakan PIL

#### Contoh

```bash
# Samakan satu foto ke referensi
python imgconv.py foto.jpg --match-tone referensi.jpg

# Batch: samakan seluruh folder ke satu foto referensi
python imgconv.py *.jpg --match-tone golden_hour.jpg --output ./matched/

# Batch dengan resize sekaligus
python imgconv.py *.jpg --match-tone referensi.jpg --size 1920x --output ./out/

# Match tone + tambah fine-tuning manual
python imgconv.py *.jpg --match-tone referensi.jpg --brightness 1.05 --output ./out/
```

---

### Color Matching dari Referensi

Mentransfer gaya warna dari foto referensi menggunakan metode Reinhard LAB mean/std transfer — lebih cepat, cocok untuk menerapkan mood warna secara umum.

```bash
--match-color REF
```

#### Cara Kerja

- Jika **numpy tersedia**: **LAB color transfer** (Reinhard et al. 2001) — menyamakan mean dan standar deviasi tiap channel di ruang CIE LAB
- Jika **numpy tidak ada**: fallback ke **RGB channel matching** — menyamakan statistik per channel R, G, B

#### Contoh

```bash
# Samakan color cast satu foto ke referensi
python imgconv.py foto.jpg --match-color referensi.jpg

# Batch: transfer mood warna dari referensi
python imgconv.py *.jpg --match-color cinematic.jpg --output ./graded/

# Match color + tone preset di atas
python imgconv.py *.jpg --match-color referensi.jpg --tone warm --output ./out/
```

---

### Perbandingan match-tone vs match-color

| | `--match-tone` | `--match-color` |
|---|---|---|
| **Algoritma** | Histogram CDF matching | Reinhard LAB mean/std transfer |
| **Yang disamakan** | Distribusi pixel penuh (CDF) | Rata-rata dan standar deviasi |
| **Akurasi tone** | Sangat tinggi — kurva shadow/midtone/highlight ikut | Sedang — hanya statistik global |
| **Kecepatan** | Lebih lambat (numpy) | Lebih cepat |
| **Cocok untuk** | Menyeragamkan batch foto secara akurat | Menerapkan mood/gaya warna umum |
| **Kebutuhan** | numpy (direkomendasikan) | numpy (direkomendasikan) |

**Kapan pakai `--match-tone`**: kamu punya 1 foto yang sudah diedit (expose, kontras, warna sudah pas) dan ingin seluruh batch foto terlihat identik dengannya.

**Kapan pakai `--match-color`**: kamu ingin menerapkan nuansa warna dari sebuah foto referensi tapi tidak perlu akurasi distribusi penuh — lebih seperti "color grade" daripada "color copy".

---

### Urutan Pemrosesan

Ketika beberapa opsi digunakan bersamaan, urutan eksekusinya adalah:

```
crop → resize → match-tone → match-color → tone preset → manual adjustments → rounded corners
```

Rounded corners selalu dijalankan **terakhir** agar masking diterapkan pada gambar yang sudah final.

Contoh kombinasi penuh:

```bash
python imgconv.py foto.jpg \
  --crop square \
  --size 500x500 \
  --match-tone referensi.jpg \
  --tone warm \
  --radius 50%
```

Urutan eksekusi: crop square → resize 500×500 → histogram match → preset warm → rounded corners 50% (lingkaran penuh)

---

## Opsi Output

| Argumen | Keterangan |
|---|---|
| `-o`, `--output PATH` | File output atau direktori tujuan |
| `--overwrite` | Timpa file jika sudah ada (default: skip) |

Jika `--output` adalah direktori, ekstensi file output mengikuti `--format` yang diberikan. Contoh: `--format webp --output ./out/` akan menghasilkan file `.webp` di folder tersebut.

Jika `--output` tidak diberikan, nama file dibuat otomatis di samping file input:

| Opsi yang digunakan | Contoh nama output |
|---|---|
| `--crop 16:9` | `foto_16-9.jpg` |
| `--size 800x` | `foto_800x.jpg` |
| `--match-tone ref.jpg` | `foto_tone.jpg` |
| `--match-color ref.jpg` | `foto_matched.jpg` |
| `--tone warm` | `foto_warm.jpg` |
| `--radius 30` | `foto_r30.png` |
| `--radius 5%` | `foto_r5pct.png` |
| `--crop 1:1 --size 500x --radius 50%` | `foto_1-1_500x_r50pct.png` |

```bash
# Output ke file tertentu
python imgconv.py foto.jpg --match-tone ref.jpg --output foto_graded.jpg

# Output ke direktori
python imgconv.py *.jpg --match-tone ref.jpg --output ./output/

# Timpa file yang ada
python imgconv.py foto.jpg --tone warm --output foto.jpg --overwrite
```

---

## Batch Processing

Semua fitur mendukung pemrosesan banyak file sekaligus.

```bash
# Wildcard
python imgconv.py *.jpg --match-tone referensi.jpg --output ./matched/

# Beberapa file eksplisit
python imgconv.py a.jpg b.jpg c.jpg --size 1280x --output ./resized/

# Subdirektori
python imgconv.py photos/*.jpg --match-tone ref.jpg --output ./graded/

# Kombinasi lengkap: samakan tone + resize + konversi format
python imgconv.py *.jpg --match-tone ref.jpg --size 1920x --format webp --output ./out/
```

---

## Referensi Argumen

| Argumen | Pendek | Tipe | Default | Keterangan |
|---|---|---|---|---|
| `inputs` | — | positional | — | Satu atau lebih file input |
| `--size` | `-s` | string | — | Target ukuran: `WxH`, `Wx`, `xH`, `N%` |
| `--crop` | `-c` | string | — | Target rasio crop |
| `--crop-method` | — | pilihan | `auto` | Strategi crop |
| `--format` | `-f` | string | — | Format output |
| `--quality` | `-q` | int 1–95 | `85` | Kualitas JPEG/WebP |
| `--stretch` | — | flag | `false` | Resize non-proporsional |
| `--resample` | — | pilihan | `lanczos` | Filter resampling |
| `--output` | `-o` | path | auto | File atau direktori output |
| `--overwrite` | — | flag | `false` | Izinkan timpa file |
| `--tone` | — | string | — | Preset tone warna |
| `--radius` | — | string | — | Radius sudut: piksel (`30`) atau persen (`5%`) |
| `--match-tone` | — | path | — | Foto referensi untuk histogram tone matching |
| `--match-color` | — | path | — | Foto referensi untuk LAB color transfer |
| `--brightness` | — | float | `1.0` | Kecerahan |
| `--contrast` | — | float | `1.0` | Kontras |
| `--saturation` | — | float | `1.0` | Saturasi |
| `--temperature` | — | int | `0` | Suhu warna |
