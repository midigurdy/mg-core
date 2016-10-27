from collections import namedtuple
import os


Font = namedtuple('Font', 'name char_width char_height line_spacing max_lines')


class BaseDisplay:
    """
    Provides methods to draw on the supplied output, like point, line, text
    rendering etc.

    Can also be used as a context manager which will clear the
    display on enter and update the ouput on exit.

    All drawing operations are done on a backbuffer, to send the image onto
    the external device use the 'update' method.

    FONTS

    Idx  Name     Number of chars on 128x32 display
    --------------------------------------------
    0:   4x6      32x4 chars (+ 0x5 px)
    1:   5x7      25x4 chars (+ 3x1 px)
    2:   5x8      25x3 chars (+ 3x6 px)
    3:   6x10     21x3 chars (+ 2x0 px)
    4:   7x13     18x2 chars (+ 2x5 px)
    5:   7x13B    18x2 chars (+ 2x5 px) BOLD
    6:   9x15     14x2 chars (+ 2x1 px)
    7:   9x15B    14x2 chars (+ 2x1 px) BOLD
    8:   10x20    12x1 chars (+ 8x12 px)

    The fonts are available in .pil and .pdf format.
    """

    FONTS = (
        Font('4x6', 4, 6, 1, 4),
        Font('5x7', 5, 7, 1, 4),
        Font('5x8', 5, 8, 1, 3),
        Font('6x10', 6, 10, 1, 3),
        Font('7x13', 7, 13, 1, 2),
        Font('7x13B', 7, 13, 1, 2),
        Font('9x15', 9, 15, 1, 2),
        Font('9x15B', 9, 15, 1, 2),
        Font('10x20', 10, 20, 1, 1),
    )

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self._font_size = 0

    @property
    def font_dir(self):
        return os.path.join(os.path.dirname(__file__), 'fonts')

    def font_size(self, size):
        self._font_size = int(size)

    @property
    def font(self):
        return self.FONTS[self._font_size]

    def get_font(self, size):
        return self.FONTS[size]

    def puts(self, x, y, text, color=1, spacing=1, align='left', anchor='left', max_width=0, x_offset=0):
        """
        Write the supplied string onto the display. align and anchor can
        be 'left' (or None), 'right' or 'center'.
        """

    def point(self, x, y, color=1):
        """
        Draw a single pixel
        """

    def line(self, x1, y1, x2, y2, color=1, width=0):
        """
        Draw a line
        """

    def rect(self, x1, y1, x2, y2, color=1, fill=None):
        """
        Draw a rectangle
        """

    def clear(self):
        """
        Clear the display
        """

    def update(self):
        """
        Update the actual output
        """

    def get_image_data(self):
        """
        Return the image in PIL raw '1;R' mode, i.e. 1 bit per pixel, first
        pixel in LSB of each byte.
        """

    # Context-manager support: clear on enter, update on exit
    def __enter__(self):
        self.clear()
        return self

    def __exit__(self, *args):
        self.update()
