class StringBlit:
    def __init__(self, pattern, reverse=False, rotate=None):
        self.pattern = pattern
        self.reverse = reverse
        self.rotate = rotate
        self.data, self.width, self.height = self._compile()

    def _compile(self):
        lines = [line.strip() for line in self.pattern.split('\n') if line.strip()]

        conv = {
            '.': 1 if self.reverse else 0,
            'O': 0 if self.reverse else 1,
        }

        rows = list(map(lambda lst: [conv.get(c, -1) for c in lst], lines))

        if self.rotate == 'left':
            rows = list(reversed(list(zip(*rows))))
        elif self.rotate == 'right':
            rows = list(zip(*rows[::-1]))

        return [p for row in rows for p in row], len(rows[0]), len(rows)


LABEL_MELODY = StringBlit(
    #        |         |         | #
    """
    ................................
    ................................
    .O...O......OO..........O.......
    .O...O.......O..........O.......
    .OO.OO..OOO..O..OO...OO.O.O...O.
    .O.O.O.O...O.O.O..O.O..OO.O...O.
    .O...O.OOOOO.O.O..O.O...O.O..OO.
    .O...O.O.....O.O..O.O..OO..OO.O.
    .O...O..OOO.OOO.OO...OO.O.....O.
    ..........................O...O.
    ...........................OOO..
    ................................
    """, reverse=True, rotate='right')


LABEL_DRONE = StringBlit(
    #        |         |         | #
    """
    ................................
    ................................
    ..OOOO..........................
    ...O..O.........................
    ...O..O.O.OO..OOO..O.OO...OOO...
    ...O..O.OO...O...O.OO..O.O...O..
    ...O..O.O....O...O.O...O.OOOOO..
    ...O..O.O....O...O.O...O.O......
    ..OOOO..O.....OOO..O...O..OOO...
    ................................
    ................................
    ................................
    """, reverse=True, rotate='right')


LABEL_TROMPETTE = StringBlit(
    #        |         |         | #
    """
    ................................
    ................................
    ..OOOOO.........................
    ....O...........................
    ....O...O.OO..OOO..OO.O..O.OO...
    ....O...OO...O...O.O.O.O.OO..O..
    ....O...O....O...O.O.O.O.O...O..
    ....O...O....O...O.O.O.O.OO..O..
    ....O...O.....OOO..O...O.O.OO...
    .........................O......
    .........................O......
    ................................
    """, reverse=True, rotate='right')

SBOX_1 = (
    StringBlit(
        #        |         |      #
        """
        .OOOOOOOOOOOOOOOOOOOOOO.
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        O......................O
        .OOOOOOOOOOOOOOOOOOOOOO.
        """),
    StringBlit(
        #        |         |      #
        """
        .OOOOOOOOOOOOOOOOOOOOOO.
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOOOOOOO
        .OOOOOOOOOOOOOOOOOOOOOO.
        """),
)

SBOX_2 = (
    StringBlit(
        #        |         |      #
        """
        ...OOOOOOOOOOOOOOOOOOOOOO...
        ..O......................O..
        ..O......................O..
        ..O......................O..
        ..O......................O..
        ..O......................O..
        ..O......................O..
        ..O......................O..
        ..O......................O..
        ..O......................O..
        ...OOOOOOOOOOOOOOOOOOOOOO...
        """),

    StringBlit(
        #        |         |      #
        """
        ...OOOOOOOOOOOOOOOOOOOOOO...
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ..OOOOOOOOOOOOOOOOOOOOOOOO..
        ...OOOOOOOOOOOOOOOOOOOOOO...
        """),
)

SBOX_2_ACTIVE = (
    StringBlit(
        #        |         |      #
        """
        ...OOOOOOOOOOOOOOOOOOOOOO...
        O.O......................O.O
        O.O......................O.O
        O.O......................O.O
        O.O......................O.O
        O.O......................O.O
        O.O......................O.O
        O.O......................O.O
        O.O......................O.O
        O.O......................O.O
        ...OOOOOOOOOOOOOOOOOOOOOO...
        """),

    StringBlit(
        #        |         |      #
        """
        ...OOOOOOOOOOOOOOOOOOOOOO...
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        O.OOOOOOOOOOOOOOOOOOOOOOOO.O
        ...OOOOOOOOOOOOOOOOOOOOOO...
        """),
)

SBOX_3 = (
    StringBlit(
        #        |   #
        """
        .OOOOOOOOOOOOOOOOO.
        O.................O
        O.................O
        O.................O
        O.................O
        O.................O
        O.................O
        O.................O
        O.................O
        O.................O
        .OOOOOOOOOOOOOOOOO.
        """),
    StringBlit(
        #        |   #
        """
        .OOOOOOOOOOOOOOOOO.
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        OOOOOOOOOOOOOOOOOOO
        .OOOOOOOOOOOOOOOOO.
        """),
)


SBOX_MELODY = StringBlit(
    #        |         |         | #
    """
    .........
    .........
    ..O...O..
    ..O...O..
    ..OO.OO..
    ..O.O.O..
    ..O...O..
    ..O...O..
    ..O...O..
    .........
    .........
    """, reverse=False, rotate='none')


SBOX_DRONE = StringBlit(
    #        |         |         | #
    """
    .........
    .........
    .OOO.....
    .O..O....
    .O..O....
    .O..O.OO.
    .O..O.O..
    .O..O.O..
    .OOO..O..
    .........
    .........
    """, reverse=False, rotate='none')


SBOX_TROMPETTE = StringBlit(
    #        |         |         | #
    """
    .........
    .........
    ..OOOOO..
    ....O....
    ....O....
    ....O....
    ....O....
    ....O....
    ....O....
    .........
    .........
    """, reverse=False, rotate='none')


"""
.O..O.......OO..........O.......
.OOOO........O..........O.......
.OOOO..OO....O...OO...OOO.O..O..
.O..O.O.OO...O..O..O.O..O.O..O..
.O..O.OO.....O..O..O.O..O..O.O..
.O..O..OO...OOO..OO...OOO...O...
...........................O....
................................
.OOO............................
.O..O...........................
.O..O.OOO...OO..OOO...OO........
.O..O.O..O.O..O.O..O.O.OO.......
.O..O.O....O..O.O..O.OO.........
.OOO..O.....OO..O..O..OO........
................................
................................
..OOO...........................
...O............................
...O..OOO...OO..O.O..OOO........
...O..O..O.O..O.OOOO.O..O.......
...O..O....O..O.O..O.O..O.......
...O..O.....OO..O..O.OOO........
.....................O..........
................................
"""
