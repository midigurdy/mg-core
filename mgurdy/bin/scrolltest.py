import time
from mg.ui.display import Display

display = Display(128, 32, '/tmp/mgimage', mmap=False)

with display as d:
    d.font_size(3)
    d.puts(0, 0, "test")
    d.scrolltext(10, 10, 32, "0123456789abdcefghij", shift_delay=10)

time.sleep(3)

with display as d:
    d.scrolltext(5, 5, 30, "abcdefghijklmnop", 1, initial_delay=1000, shift_delay=10, end_delay=500)

time.sleep(10)
