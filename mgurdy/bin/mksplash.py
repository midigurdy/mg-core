import os
import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser(description='Create MidiGurdy boot splash image')
parser.add_argument('output')
parser.add_argument('--png', dest='png', action='store_true')
args = parser.parse_args()

"""
FONTS
-----
4x6   -> 32x4 chars (+ 0x5 px)
5x7   -> 25x4 chars (+ 4x1 px)
5x8   -> 25x3 chars (+ 4x5 px)
6x10  -> 21x3 chars (+ 3x0 px)
7x13  -> 18x2 chars (+ 3x3 px)
7x13B -> 18x2 chars (+ 3x3 px) BOLD
9x15  -> 14x2 chars (+ 1x2 px)
9x15B -> 14x2 chars (+ 1x2 px) BOLD
"""

width = 128
height = 32
font_dir = '../lib/mg/ui/fonts/'
font_name = '9x15'

font = ImageFont.load(os.path.join(font_dir, '%s.pil' % font_name))
img = Image.new('1', (width, height))
draw = ImageDraw.Draw(img)

def puts(x, y, text, color=1, spacing=1, align='left',
         anchor='left'):
    if anchor != 'left':
        w = draw.textsize(text, font)[0]
        x -= w if anchor == 'right' else w // 2
        draw.text((x, y), text, fill=color, font=font,
                       spacing=spacing, align=align)

puts(64, 0, 'MidiGurdy\nstarting...', align='center', anchor='center')

if args.png:
    with open(args.output, 'wb') as f:
        img.save(f, format='png')
else:
    """
    The screen is divided in pages, each having a height of 8
    pixels, and the width of the screen. When sending a byte of
    data to the controller, it gives the 8 bits for the current
    column. I.e, the first byte are the 8 bits of the first
    column, then the 8 bits for the second column, etc.
    
    
    Representation of the screen, assuming it is 5 bits
    wide. Each letter-number combination is a bit that controls
    one pixel.
    
    A0 A1 A2 A3 A4
    B0 B1 B2 B3 B4
    C0 C1 C2 C3 C4
    D0 D1 D2 D3 D4
    E0 E1 E2 E3 E4
    F0 F1 F2 F3 F4
    G0 G1 G2 G3 G4
    H0 H1 H2 H3 H4
    
    If you want to update this screen, you need to send 5 bytes:
     (1) A0 B0 C0 D0 E0 F0 G0 H0
     (2) A1 B1 C1 D1 E1 F1 G1 H1
     (3) A2 B2 C2 D2 E2 F2 G2 H2
     (4) A3 B3 C3 D3 E3 F3 G3 H3
     (5) A4 B4 C4 D4 E4 F4 G4 H4
    """
    raw = list(img.getdata())  # flat array of 1 bit image data 
    data = [0] * (height * width / 8)

    for i in range(height / 8):
        for j in range(width):
            ary_idx = i * width + j
            for k in range(8):
                page_length = width * 8 * i
                index = page_length + (width * k + j)
                bit = raw[index]
                data[ary_idx] |= bit << k
    with open(args.output, 'wb') as f:
        f.write(bytearray(data))
