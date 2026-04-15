SUPPORTED_FORMATS = {
    "jpg": "JPEG", "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "gif": "GIF",
    "tiff": "TIFF", "tif": "TIFF",
    "ico": "ICO",
    "avif": "AVIF",
}

TONE_PRESETS = {
    "warm":     {"temperature": -40, "saturation": 1.1},
    "cool":     {"temperature":  40, "saturation": 1.05},
    "vintage":  {"temperature": -20, "saturation": 0.7,  "contrast": 0.9,  "brightness": 0.95},
    "fade":     {"contrast": 0.8,    "brightness": 1.05, "saturation": 0.85},
    "vibrant":  {"saturation": 1.5,  "contrast": 1.1},
    "dramatic": {"contrast": 1.4,    "saturation": 0.55},
    "matte":    {"contrast": 0.75,   "saturation": 0.9,  "brightness": 1.1},
}

CROP_PRESETS = {
    "landscape": 16 / 9,
    "portrait":  9 / 16,
    "square":    1 / 1,
    "4:3":       4 / 3,
    "3:4":       3 / 4,
    "16:9":     16 / 9,
    "9:16":      9 / 16,
    "3:2":       3 / 2,
    "2:3":       2 / 3,
    "1:1":       1 / 1,
    "21:9":     21 / 9,
    "5:4":       5 / 4,
    "4:5":       4 / 5,
}
