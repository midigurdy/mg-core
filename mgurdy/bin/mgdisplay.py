import os
import selectors
import tkinter
from PIL import ImageTk, Image

FILENAME = '/tmp/mgimage'


class TkDisplay:
    scale = 3
    border = 2
    width = 128
    height = 32
    size = int((width * height) / 8)

    def __init__(self):
        self.create_canvas()

    def create_canvas(self):
        self.w = self.width * self.scale
        self.h = self.height * self.scale
        self.b = self.border * self.scale
        self.tk = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.tk,
                                     width=self.w + 2 * self.b,
                                     height=self.h + 2 * self.b,
                                     bg='black')
        self.canvas.pack()
        tmp_img = Image.new('1', (self.width, self.height))
        self.tkimage = ImageTk.BitmapImage(tmp_img, foreground='white')
        self.cimage = self.canvas.create_image(self.b, self.b,
                                               image=self.tkimage,
                                               anchor=tkinter.NW)
        self.tk.update()

    def update(self, data):
        image = Image.frombytes('1', (self.width, self.height), data, 'raw', '1;R')
        self.tkimage = ImageTk.BitmapImage(
            image.resize((self.w, self.h)), foreground='white')
        self.canvas.itemconfig(self.cimage, image=self.tkimage)
        self.tk.update()


def main():
    display = TkDisplay()
    sel = selectors.DefaultSelector()
    if not os.path.exists(FILENAME):
        os.mkfifo(FILENAME)
    fp = os.open(FILENAME, os.O_RDWR | os.O_NONBLOCK)
    sel.register(fp, selectors.EVENT_READ)

    while True:
        for key, mask in sel.select():
            data = os.read(key.fileobj, display.size)
            display.update(data)


main()
