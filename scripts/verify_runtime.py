"""Exercise the bundled HEIF codec; importing pillow_heif alone defers errors."""
import io
import tkinter
import PIL
import psutil
import pillow_heif
from PIL import Image


def verify():
    pillow_heif.register_heif_opener()
    payload = io.BytesIO()
    Image.new('RGB', (16, 16), (64, 128, 192)).save(payload, format='HEIF')
    payload.seek(0)
    with Image.open(payload) as decoded:
        decoded.load()
        if decoded.size != (16, 16) or decoded.format != 'HEIF':
            raise RuntimeError('Bundled HEIF codec round trip failed')
    print('Clean runtime OK; native HEIF encode/decode passed')


if __name__ == '__main__':
    verify()
