import tkinter
from PIL import ImageTk, Image


class TkOutputMixin:
    """
    Mixin class to output onto Tk canvas instead of framebuffer
    """
    scale = 3
    border = 2

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

    def update(self):
        if not hasattr(self, 'canvas'):
            self.create_canvas()
        data = self.get_image_data()
        image = Image.frombytes('1', (self.width, self.height), data, 'raw', '1;R')
        self.tkimage = ImageTk.BitmapImage(
            image.resize((self.w, self.h)), foreground='white')
        self.canvas.itemconfig(self.cimage, image=self.tkimage)
        self.tk.update()
