import os

from PIL import Image, ImageDraw, ImageFont

from .base import BaseDisplay


class PillowDisplay(BaseDisplay):
    """
    Uses python-pillow for all rendering and drawing routines and outputs
    data to a fbdev file (in 1bpp format)
    """

    def __init__(self, width, height, filename):
        super().__init__(width, height)
        self.image = Image.new('1', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        self.output = open(filename, 'wb')
        self._load_pil_fonts()
        self.font_size(1)

    def font_size(self, size):
        super().font_size(size)
        self.font = self.fonts[size]

    def puts(self, x, y, text, color=1, spacing=1, align='left', anchor='left'):
        if anchor != 'left':
            width = self.draw.textsize(text, self.font)[0]
            x -= (width - 2) if anchor == 'right' else width // 2
        self.draw.text((x, y), text, fill=color, font=self.font,
                       spacing=spacing, align=align)

    def point(self, x, y, color=1):
        self.draw.point((x, y), fill=color)

    def line(self, x1, y1, x2, y2, color=1, width=0):
        self.draw.line(((x1, y1), (x2, y2)), fill=color, width=width)

    def rect(self, x1, y1, x2, y2, color=1, fill=None):
        self.draw.rectangle(((x1, y1), (x2, y2)), outline=color, fill=fill)

    def clear(self):
        self.draw.rectangle(((0, 0), (self.width, self.height)), fill=0)

    def update(self):
        self.output.seek(0)
        self.output.write(self.get_image_data())
        self.output.flush()

    def _load_pil_fonts(self):
        self.fonts = []
        for font in self.FONTS:
            imgfont = ImageFont.load(os.path.join(self.font_dir, '%s.pil' % font.name))
            self.fonts.append(imgfont)

    def get_image_data(self):
        return self.image.tobytes('raw', '1;R')

    def __del__(self):
        try:
            self.output.close()
        except:
            pass
