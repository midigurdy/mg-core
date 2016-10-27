import os

from mg.mglib.api import MGImage

from .base import BaseDisplay


class MGDisplay(BaseDisplay):
    """
    Uses the mglib drawing routines and outputs data to an fbdev file
    (in 1bpp format)
    """
    def __init__(self, width, height, filename, mmap=False):
        super().__init__(width, height)
        self.filename = filename
        self.img = MGImage(self.width, self.height,
                           mmap_filename=self.filename if mmap else None)
        self._load_bdf_fonts()

    def clear(self):
        self.img.clear()

    def point(self, x, y, color=1):
        self.img.point(x, y, color)

    def line(self, x0, y0, x1, y1, color=1):
        self.img.line(x0, y0, x1, y1, color)

    def rect(self, x1, y1, x2, y2, color=1, fill=-1):
        self.img.rect(x1, y1, x2, y2, color, fill)

    def update(self):
        self.img.write(self.filename)

    def font_size(self, size):
        super().font_size(size)
        self.font_id = size

    def puts(self, x, y, text, color=1, spacing=1, align='left', anchor='left',
             max_width=0, x_offset=0):
        self.img.puts(x, y, text, self.fonts[self.font_id], color, spacing,
                      align, anchor, max_width, x_offset)

    def get_image_data(self):
        self.img.get_image_data()

    def _load_bdf_fonts(self):
        self.fonts = []
        for font in self.FONTS:
            filename = os.path.join(self.font_dir, '%s.bdf' % font.name)
            fontid = self.img.load_font(filename)
            self.fonts.append(fontid)
