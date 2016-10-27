#!/usr/bin/python

"""
Displays centered text in the OLED display. Use $'line1\nline2' for
multi-line text in bash.
"""

import argparse
from mg.ui.display import Display

display = Display(128, 32, '/dev/fb0', mmap=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('msg')
    parser.add_argument('--font-size', type=int, default=3)
    parser.add_argument('--fill', action="store_true", default=False)
    args = parser.parse_args()

    # turn \n to real line breaks
    args.msg = args.msg.replace(r'\n', '\n')

    if args.fill:
        font = display.get_font(args.font_size)
        line_len = display.width // font.char_width
        msg = args.msg.replace('\n', ' ')
        lines = [msg[i:i+line_len] for i in range(0, len(msg), line_len)]
        with display as d:
            d.font_size(args.font_size)
            d.puts(0, 0, '\n'.join(lines))
    else:
        num_lines = args.msg.count('\n') + 1
        with display as d:
            d.font_size(args.font_size)
            text_height = d.font.char_height * num_lines + num_lines - 1
            cy = (32 - text_height) // 2
            d.puts(64, cy, args.msg, align='center', anchor='center')


if __name__ == '__main__':
    main()
