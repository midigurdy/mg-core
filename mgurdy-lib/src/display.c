#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <ft2build.h>
#include FT_FREETYPE_H

#include "mg.h"


static void draw_ft_bitmap(struct mg_image *img, FT_Bitmap *bitmap,
        int x, int y, int color, int start_x, int max_x);
static void puts_line(struct mg_image *img, int face_id,
        const char *text, int textlen, int x, int y, int color, int max_width, int x_offset);
static void bline(struct mg_image *img, int x0, int y0, int x1, int y1, int c);
static void hline(struct mg_image *img, int x0, int x1, int y, int c);
static void vline(struct mg_image *img, int x, int y0, int y1, int c);
static void convert_8bpp_to_1bpp(struct mg_image *img, char *buf);


struct mg_image *mg_image_create(int width, int height)
{
    int err;
    struct mg_image *img = malloc(sizeof *img);

    img->width = width;
    img->height = height;
    img->size = width * height;
    img->data = malloc(img->size * sizeof(char));
    img->membuf = NULL;
    img->ft.face_count = 0;
    mg_image_clear(img);

    err = FT_Init_FreeType(&img->ft.library);
    if (err) {
        printf("Error initializing FreeType library!\n");
    }

    return img;
}


void mg_image_destroy(struct mg_image *img)
{
    int i;

    for (i=0; i<img->ft.face_count; i++) {
        FT_Done_Face(img->ft.faces[i]);
    }

    if (img->membuf) {
        munmap(img->membuf, img->size / 8);
    }

    free(img->data);
    free(img);
}


int mg_image_load_font(struct mg_image *img, const char *filename)
{
    int err;
    int id = img->ft.face_count;

    if (img->ft.face_count == MG_IMAGE_MAX_FONTS) {
        printf("Maximum fonts reached for image!\n");
        return -1;
    }

    err = FT_New_Face(img->ft.library, filename, 0, &img->ft.faces[id]);
    if (err) {
        printf("Error loading font %s: %d\n", filename, err);
        return -1;
    }

    img->ft.face_count++;
    return id;
}


static void draw_ft_bitmap(struct mg_image *img, FT_Bitmap *bitmap,
        int x, int y, int color, int start_x, int max_x)
{
    int row;
    int col;
    int ix, iy;
    char b;
    int bit;
    int i;

    for (row=0; row < bitmap->rows; row++) {
        bit = 0;
        ix = x;
        iy = y + row;
        for(col=0; col < bitmap->pitch; col++) {
            b = bitmap->buffer[row * bitmap->pitch + col];
            for(i=7; i>=0; i--, ix++, bit++) {
                if (bit == bitmap->width)
                    break;
                if (ix < 0 || ix < start_x || (max_x > 0 && ix > max_x) || iy < 0 || ix >= img->width ||
                        iy >= img->height)
                    continue;
                if (color) {
                    img->data[iy * img->width + ix] |=
                        (b & (1 << i)) ? 1 : 0;
                }
                else {
                    if (b & (1 << i)) {
                        img->data[iy * img->width + ix] &= 0;
                    }

                }
            }
        }
    }
}


static void puts_line(struct mg_image *img, int face_id,
        const char *text, int textlen, int x, int y, int color, int max_width, int x_offset)
{
    int i;
    int start_x;
    int max_x = 0;

    FT_GlyphSlot slot = img->ft.faces[face_id]->glyph;
    FT_Face face = img->ft.faces[face_id];

    start_x = x;
    if (max_width > 0)
        max_x = start_x + max_width;
    x += x_offset;
    for (i=0; i<textlen; i++) {
        if (FT_Load_Char(face, (unsigned char) text[i],
                    FT_LOAD_RENDER | FT_LOAD_MONOCHROME))
            return;
        draw_ft_bitmap(img, &slot->bitmap, x - slot->bitmap_left, y, color, start_x, max_x);
        x += slot->advance.x >> 6;
    }
}


void mg_image_puts(struct mg_image *img, int face_id, const char *text,
        int x, int y, int color, int line_spacing, int align, int anchor,
        int max_width, int x_offset)
{
    int i;
    int line_x = x;
    int textlen;
    int char_w = 0;
    int char_h = 0;
    int num_lines;
    int longest_line = 0;
    char *line = NULL;
    char *input;
    char *tmp;
    char *tok;

    FT_Face face = img->ft.faces[face_id];

    /* the fonts supported by this function all have a single size */
    if (face->available_sizes) {
        char_w = face->available_sizes[0].width;
        char_h = face->available_sizes[0].height;
    }

    /* split text into lines and optionally determine the longest line
     * for right or center alinged or anchored text */
    tmp = line = input = strdup(text);
    num_lines = 0;
    while((tok = strsep(&tmp, "\n")) != NULL) {
        num_lines++;
        if (align || anchor) {
            textlen = strlen(tok);
            if (textlen > longest_line)
                longest_line = textlen;
        }
    }

    /* now render each line separately */
    for(i=0; i<num_lines; i++) {
        textlen = strlen(line);
        if (textlen) {
            if (anchor == 1)  // center anchored
                line_x = x - (longest_line * char_w) / 2;
            else if (anchor == 2)  // right anchored
                line_x = x - ((longest_line * char_w) - 2);
            else
                line_x = x;

            if (align == 1) { // center aligned
                line_x += ((longest_line - textlen) * char_w) / 2;
            }
            else if (align == 2) { // right aligned
                line_x += ((longest_line - textlen) * char_w);
            }

            puts_line(img, face_id, line, textlen, line_x, y, color, max_width, x_offset);
        }

        y += char_h;
        y += line_spacing;

        // advance char pointer to beginning of next line
        line += textlen + 1;
    }

    free(input);
}


void mg_image_clear(struct mg_image *img)
{
    memset(img->data, 0, img->size * sizeof(char));
}


char *mg_image_data(struct mg_image *img)
{
    return img->data;
}

static void bline(struct mg_image *img, int x0, int y0, int x1, int y1, int c)
{
    int dx =  abs(x1-x0), sx = x0<x1 ? 1 : -1;
    int dy = -abs(y1-y0), sy = y0<y1 ? 1 : -1;
    int err = dx+dy, e2; /* error value e_xy */

    while(1){
        mg_image_point(img, x0, y0, c);
        if (x0==x1 && y0==y1) break;
        e2 = 2*err;
        if (e2 > dy) { err += dy; x0 += sx; } /* e_xy+e_x > 0 */
        if (e2 < dx) { err += dx; y0 += sy; } /* e_xy+e_y < 0 */
    }
}

static void hline(struct mg_image *img, int x0, int x1, int y, int c)
{
    int x = (x0 > x1) ? x1 : x0;
    int xmax = (x0 > x1) ? x0 : x1;

    for (; x<=xmax; x++)
        mg_image_point(img, x, y, c);
}

static void vline(struct mg_image *img, int x, int y0, int y1, int c)
{
    int y = (y0 > y1) ? y1 : y0;
    int ymax = (y0 > y1) ? y0 : y1;

    for (; y<=ymax; y++) {
        mg_image_point(img, x, y, c);
    }
}


void mg_image_line(struct mg_image *img, int x0, int y0, int x1, int y1, int c)
{
    if (x0 == x1)
        vline(img, x0, y0, y1, c);
    else if (y0 == y1)
        hline(img, x0, x1, y0, c);
    else
        bline(img, x0, y0, x1, y1, c);
}


void mg_image_rect(struct mg_image *img, int x0, int y0, int x1, int y1,
        int c, int fill)
{
    int x, y, xmax, ymax, ix, iy;
    if (fill > -1) {
        x = (x0 > x1) ? x1 : x0;
        xmax = (x0 > x1) ? x0 : x1;
        if (xmax >= img->width)
            xmax = img->width;
        y = (y0 > y1) ? y1 : y0;
        ymax = (y0 > y1) ? y0 : y1;
        if (ymax >= img->height)
            ymax = img->height;
        for(iy=y; iy<=ymax; iy++)
            for(ix=x; ix<=xmax; ix++)
                img->data[iy * img->width + ix] = fill;
    }
    if (fill != c) {
        hline(img, x0, x1, y0, c);
        vline(img, x1, y0, y1, c);
        hline(img, x1, x0, y1, c);
        vline(img, x0, y1, y0, c);
    }
}




void mg_image_point(struct mg_image *img, int x, int y, int c)
{
    int idx = y * img->width + x;
    if (idx < img->size)
        img->data[idx] = c;
}

/**
 * Turns the 8 bit per pixel image into a 1-bit per pixel buffer.
 * Assumes image width and height are multiples of 8 pixels.
 * Pixel order in resulting buffer:
 *	Byte 1            Byte 2
 *	8.7.6.5.4.3.2.1   16.15.14.13.12.11.10
 */
static void convert_8bpp_to_1bpp(struct mg_image *img, char *buf)
{
    int i;
    int bit = 0;
    char byte = 0;
    int k = 0;

    for (i=0; i<img->size; i++) {
        byte |= (img->data[i] << bit);
        bit++;
        if (bit > 7) {
            buf[k++] = byte;
            byte = 0;
            bit = 0;
        }
    }
}


int mg_image_mmap_file(struct mg_image *img, const char *filename)
{
    int fd;
    char *mm;

    fd = open(filename, O_RDWR);
    if (fd < 0) {
        perror("Unable to open output file");
        return -1;
    }

    mm = (char *) mmap(0, img->size / 8, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mm == MAP_FAILED) {
        perror("Failed to map framebuffer device to memory");
        return -1;
    }

    img->membuf = mm;

    return 0;
}


int mg_image_write(struct mg_image *img, const char *filename)
{
    int fd = -1;
    int ret = 0;
    char *buf;

    // If this image has a memory mapped output file, just convert
    // into the buffer and exit.
    if (img->membuf != NULL) {
        convert_8bpp_to_1bpp(img, img->membuf);
        return 0;
    }

    // Otherwise convert to new buffer and write to output file
    buf = malloc((img->size / 8) * sizeof(char));
    if (buf == NULL) {
        perror("Out of memory");
        return -1;
    }

    convert_8bpp_to_1bpp(img, buf);

    fd = open(filename, O_WRONLY);
    if (fd < 0) {
        perror("Unable to open output file");
        ret = -1;
        goto exit;
    }

    ret = write(fd, buf, img->size / 8);
    if (ret < 0) {
        perror("Unable to write file");
    }

    close(fd);
exit:
    free(buf);
    return ret;
}
