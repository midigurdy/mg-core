import time
import pytest  # noqa

from mg.ui.display import Display


def test_blit(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    pattern1 = [
        1, -1, 0,
        0, 1, 0,
        0, -1, 1,
    ]
    pattern2 = [
        -1, -1, 1,
        -1, -1, -1,
        1, -1, -1,
    ]
    with disp as d:
        d.blit(1, 2, pattern1, 3)
        d.blit(1, 2, pattern2, 3)

    assert img_eq(
        '''
        ........
        ........
        .O.O....
        ..O.....
        .O.O....
        ........
        ........
        ........
        ''', disp, out)


def test_blit_string(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    pattern1 = (
        'O .'
        '.O.'
        '. O'
    )
    pattern2 = (
        '  O'
        '   '
        'O  '
    )
    with disp as d:
        d.blit_string(1, 2, pattern1, 3)
        d.blit_string(1, 2, pattern2, 3)

    assert img_eq(
        '''
        ........
        ........
        .O.O....
        ..O.....
        .O.O....
        ........
        ........
        ........
        ''', disp, out)


def test_single_pixel(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.point(0, 0)

    assert img_eq(
        '''
        O.......
        ........
        ........
        ........
        ........
        ........
        ........
        ........
        ''', disp, out)


def test_straight_lines(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.line(0, 0, 4, 0)

    assert img_eq(
        '''
        OOOOO...
        ........
        ........
        ........
        ........
        ........
        ........
        ........
        ''', disp, out)

    disp.line(2, 1, 2, 4)
    disp.update()

    assert img_eq(
        '''
        OOOOO...
        ..O.....
        ..O.....
        ..O.....
        ..O.....
        ........
        ........
        ........
        ''', disp, out)


def test_diagonal_lines(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.line(0, 0, 6, 6)

    assert img_eq(
        '''
        O.......
        .O......
        ..O.....
        ...O....
        ....O...
        .....O..
        ......O.
        ........
        ''', disp, out)

    with disp as d:
        d.line(0, 0, 7, 3)

    assert img_eq(
        '''
        OO......
        ..OO....
        ....OO..
        ......OO
        ........
        ........
        ........
        ........
        ''', disp, out)


def test_smallest_a_umlaut(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(0, 0, 'Ä')

    assert img_eq(
        '''
        O..O....
        .OO.....
        O..O....
        OOOO....
        O..O....
        O..O....
        ........
        ........
        ''', disp, out)


def test_right_anchored(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 8, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(23, 0, 'Abw', anchor='right')

    assert img_eq(
        '''
        ...........OO..O........
        ..........O..O.O........
        ..........O..O.OOO..O..O
        ..........OOOO.O..O.O..O
        ..........O..O.O..O.OOOO
        ..........O..O.OOO..OOOO
        ........................
        ........................
        ''', disp, out)


def test_center_anchored(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 8, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(10, 0, 'Abw', anchor='center')

    assert img_eq(
        '''
        ....OO..O...............
        ...O..O.O...............
        ...O..O.OOO..O..O.......
        ...OOOO.O..O.O..O.......
        ...O..O.O..O.OOOO.......
        ...O..O.OOO..OOOO.......
        ........................
        ........................
        ''', disp, out)


def test_smallest_A(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(1, 0, 'A')

    assert img_eq(
        '''
        ..OO....
        .O..O...
        .O..O...
        .OOOO...
        .O..O...
        .O..O...
        ........
        ........
        ''', disp, out)


def test_largest_W(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(16, 24, str(out))

    with disp as d:
        d.font_size(8)
        d.puts(0, 0, 'W')

    assert img_eq(
        '''
        ................
        ................
        ................
        .OO....OO.......
        .OO....OO.......
        .OO....OO.......
        .OO....OO.......
        .OO....OO.......
        .OO.OO.OO.......
        .OO.OO.OO.......
        .OO.OO.OO.......
        .OO.OO.OO.......
        .OOO..OOO.......
        .OOO..OOO.......
        .OO....OO.......
        .OO....OO.......
        ................
        ................
        ................
        ................
        ................
        ................
        ................
        ................
        ''', disp, out)


def test_multiline_text_left_aligned(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(16, 16, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(1, 0, 'Ag\nabc')

    assert img_eq(
        '''
        ..OO............
        .O..O...........
        .O..O..OOO......
        .OOOO.O..O......
        .O..O..OO.......
        .O..O.O.........
        .......OOO......
        ................
        ......O.........
        ......O.........
        ..OOO.OOO...OO..
        .O..O.O..O.O....
        .O.OO.O..O.O....
        ..O.O.OOO...OO..
        ................
        ................
        ''', disp, out)


def test_multiline_text_with_empty_at_start(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(16, 24, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(1, 0, '\nAg\nabc')

    assert img_eq(
        '''
        ................
        ................
        ................
        ................
        ................
        ................
        ................
        ................
        ..OO............
        .O..O...........
        .O..O..OOO......
        .OOOO.O..O......
        .O..O..OO.......
        .O..O.O.........
        .......OOO......
        ................
        ......O.........
        ......O.........
        ..OOO.OOO...OO..
        .O..O.O..O.O....
        .O.OO.O..O.O....
        ..O.O.OOO...OO..
        ................
        ................
        ''', disp, out)


def test_multiline_text_with_empty_line_inbetween(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(16, 24, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(1, 0, 'Ag\n\nabc')

    assert img_eq(
        '''
        ..OO............
        .O..O...........
        .O..O..OOO......
        .OOOO.O..O......
        .O..O..OO.......
        .O..O.O.........
        .......OOO......
        ................
        ................
        ................
        ................
        ................
        ................
        ................
        ................
        ................
        ......O.........
        ......O.........
        ..OOO.OOO...OO..
        .O..O.O..O.O....
        .O.OO.O..O.O....
        ..O.O.OOO...OO..
        ................
        ................
        ''', disp, out)


def test_multiline_text_right_aligned(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(16, 16, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(1, 0, 'Ag\nabw', align='right')

    assert img_eq(
        '''
        .......OO.......
        ......O..O......
        ......O..O..OOO.
        ......OOOO.O..O.
        ......O..O..OO..
        ......O..O.O....
        ............OOO.
        ................
        ......O.........
        ......O.........
        ..OOO.OOO..O..O.
        .O..O.O..O.O..O.
        .O.OO.O..O.OOOO.
        ..O.O.OOO..OOOO.
        ................
        ................
        ''', disp, out)


def test_multiline_text_right_aligned_anchored_right(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 16, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(19, 0, 'Ag\nabw', align='right', anchor='right')

    assert img_eq(
        '''
        ............OO..........
        ...........O..O.........
        ...........O..O..OOO....
        ...........OOOO.O..O....
        ...........O..O..OO.....
        ...........O..O.O.......
        .................OOO....
        ........................
        ...........O............
        ...........O............
        .......OOO.OOO..O..O....
        ......O..O.O..O.O..O....
        ......O.OO.O..O.OOOO....
        .......O.O.OOO..OOOO....
        ........................
        ........................
        ''', disp, out)


def test_multiline_text_right_aligned_anchored_center(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 16, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(10, 0, 'Ag\nabw', align='right', anchor='center')

    assert img_eq(
        '''
        .........OO.............
        ........O..O............
        ........O..O..OOO.......
        ........OOOO.O..O.......
        ........O..O..OO........
        ........O..O.O..........
        ..............OOO.......
        ........................
        ........O...............
        ........O...............
        ....OOO.OOO..O..O.......
        ...O..O.O..O.O..O.......
        ...O.OO.O..O.OOOO.......
        ....O.O.OOO..OOOO.......
        ........................
        ........................
        ''', disp, out)


def test_multiline_text_center_aligned(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(16, 16, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(0, 0, 'Ag\nabw', align='center')

    assert img_eq(
        '''
        ...OO...........
        ..O..O..........
        ..O..O..OOO.....
        ..OOOO.O..O.....
        ..O..O..OO......
        ..O..O.O........
        ........OOO.....
        ................
        .....O..........
        .....O..........
        .OOO.OOO..O..O..
        O..O.O..O.O..O..
        O.OO.O..O.OOOO..
        .O.O.OOO..OOOO..
        ................
        ................
        ''', disp, out)


def test_multiline_text_center_aligned_anchored_right(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 16, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(19, 0, 'Ag\nabw', align='center', anchor='right')

    assert img_eq(
        '''
        .........OO.............
        ........O..O............
        ........O..O..OOO.......
        ........OOOO.O..O.......
        ........O..O..OO........
        ........O..O.O..........
        ..............OOO.......
        ........................
        ...........O............
        ...........O............
        .......OOO.OOO..O..O....
        ......O..O.O..O.O..O....
        ......O.OO.O..O.OOOO....
        .......O.O.OOO..OOOO....
        ........................
        ........................
        ''', disp, out)


def test_multiline_text_center_aligned_anchored_center(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 16, str(out))

    with disp as d:
        d.font_size(1)
        d.puts(10, 0, 'Ag\nabw', align='center', anchor='center')

    assert img_eq(
        '''
        ......OO................
        .....O..O...............
        .....O..O..OOO..........
        .....OOOO.O..O..........
        .....O..O..OO...........
        .....O..O.O.............
        ...........OOO..........
        ........................
        ........O...............
        ........O...............
        ....OOO.OOO..O..O.......
        ...O..O.O..O.O..O.......
        ...O.OO.O..O.OOOO.......
        ....O.O.OOO..OOOO.......
        ........................
        ........................
        ''', disp, out)


def test_scrolling_text_without_shift_timeout(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 8, str(out))

    with disp as d:
        d.font_size(1)
        d.scrolltext(1, 1, 18, '12345678901234567890')

    assert img_eq(
        '''
        ........................
        ...O...OO..OOOO...O.....
        ..OO..O..O....O..OO.....
        ...O.....O..OO..O.O.....
        ...O....O.....O.OOO.....
        ...O...O...O..O...O.....
        ..OOO.OOOO..OO....O.....
        ........................
        ''', disp, out)


def test_scrolltext_without_need_for_scrolling(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(24, 8, str(out))

    with disp as d:
        d.font_size(1)
        d.scrolltext(1, 1, 18, '123', shift_delay=1)

    time.sleep(0.5)

    assert img_eq(
        '''
        ........................
        ...O...OO..OOOO.........
        ..OO..O..O....O.........
        ...O.....O..OO..........
        ...O....O.....O.........
        ...O...O...O..O.........
        ..OOO.OOOO..OO..........
        ........................
        ''', disp, out)


def test_outline_rect(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.rect(1, 1, 4, 4)

    assert img_eq(
        '''
        ........
        .OOOO...
        .O..O...
        .O..O...
        .OOOO...
        ........
        ........
        ........
        ''', disp, out)


def test_filled_rect(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.rect(1, 1, 4, 4, fill=1)

    assert img_eq(
        '''
        ........
        .OOOO...
        .OOOO...
        .OOOO...
        .OOOO...
        ........
        ........
        ........
        ''', disp, out)


def test_filled_rect_with_color_black(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    with disp as d:
        d.point(2, 2, 1)
        d.rect(1, 1, 4, 4, fill=0)

    assert img_eq(
        '''
        ........
        .OOOO...
        .O..O...
        .O..O...
        .OOOO...
        ........
        ........
        ........
        ''', disp, out)


def test_combined_output(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(16, 16, str(out))

    with disp as d:
        d.font_size(8)
        d.point(5, 2)
        d.line(3, 1, 6, 6)
        d.puts(0, 0, "U")
        d.font_size(3)
        d.puts(3, 6, "i")

    assert img_eq(
        '''
        ................
        ...O............
        ....OO..........
        .OO.O..OO.......
        .OO..O.OO.......
        .OO..O.OO.......
        .OO...OOO.......
        .OO..O.OO.......
        .OO....OO.......
        .OO.OO.OO.......
        .OO..O.OO.......
        .OO..O.OO.......
        .OO..O.OO.......
        .OO.OOOOO.......
        ..OO..OO........
        ...OOOO.........
        ''', disp, out)


def test_display_without_context_manager(tmpdir):
    out = tmpdir.join('img').ensure()
    disp = Display(8, 8, str(out))

    disp.clear()
    disp.point(0, 0)
    disp.update()

    assert img_eq(
        '''
        O.......
        ........
        ........
        ........
        ........
        ........
        ........
        ........
        ''', disp, out)


def img_eq(pattern, display, output):
    expected = '\n'.join(l.strip() for l in pattern.split('\n') if l.strip())
    with output.open('rb') as f:
        data = f.read()
    result = _fmt_output(display.width, display.height, data)

    if result == expected:
        return True

    print('Expected:')
    print(expected)

    print('Got:')
    print(result)


def _fmt_output(w, h, data):
    lines = []
    for y in range(h):
        line = []
        for x in range(w // 8):
            idx = y * (w // 8) + x
            try:
                byte = data[idx]
            except IndexError:
                line.extend(['X'] * 8)
            else:
                for bit in range(8):
                    line.append('O' if (byte & (1 << bit)) else '.')
        lines.append(''.join(line))
    return '\n'.join(lines)
