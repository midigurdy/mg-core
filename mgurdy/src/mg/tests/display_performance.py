import time

from mg.ui.display import Display


def time_text(d, iterations, anchor='left'):
    texts = (
        'This is a test',
        'This is\n a test',
        'This is a test. This is a test',
    )

    for text in texts:
        print('Rendering %sx text (%s): %s' % (iterations, anchor, text))
        t0 = time.time()
        for _ in range(iterations):
            d.clear()
            d.font_size(3)
            d.puts(0, 0, text, anchor=anchor)
            d.update()
        t1 = time.time()
        print('Took: {:.4}\n'.format(t1 - t0))


def time_line(d, iterations):
    lines = (
        (0, 0, 10, 0),
        (0, 0, 127, 31),
        (0, 0, 127, 0),
        (0, 31, 127, 0),
        (127, 0, 0, 31),
    )

    for line in lines:
        print('Rendering %sx line: %s' % (iterations, line))
        t0 = time.time()
        for _ in range(iterations):
            d.clear()
            d.line(*line)
            d.update()
        t1 = time.time()
        print('Took: {:.4}\n'.format(t1 - t0))


def test_display_performance(tmpdir):
    out = tmpdir.join('output').ensure()
    d1 = Display(132, 32, str(out))

    time_text(d1, 50000)
    time_text(d1, 50000, anchor='right')
    time_line(d1, 10000)
