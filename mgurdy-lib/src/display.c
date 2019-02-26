#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/timerfd.h>
#include <unistd.h>

#include <ft2build.h>
#include FT_FREETYPE_H

#include "mg.h"


static void draw_ft_bitmap(int width, int height, char *buffer, FT_Bitmap *bitmap,
        int x, int y, int color, int start_x, int max_x);
static void puts_line(int img_width, int img_height, char *img_data, FT_Face face,
        const char *text, int textlen, int x, int y, int color, int max_width, int x_offset);
static void bline(struct mg_image *img, int x0, int y0, int x1, int y1, int c);
static void hline(struct mg_image *img, int x0, int x1, int y, int c);
static void vline(struct mg_image *img, int x, int y0, int y1, int c);
static void convert_8bpp_to_1bpp(struct mg_image *img, char *buf);
static void copy_buffer(const char *src, int src_width, int src_height, int src_x, int src_y, 
                        char *dst, int dst_width, int dst_height, int dst_x, int dst_y,
                        int width, int height);
static void stop_scrolltext(struct mg_image *img);
static void clear_scrolltext(struct mg_image *img);
static void *scroll_thread(void *args);
static void set_timer(int fd, int initial_ms, int interval_ms);


static void *scroll_thread(void *args)
{
    int ret;
    u_int64_t val;
    struct mg_image *img = args;

    ret = pthread_setcancelstate(PTHREAD_CANCEL_ENABLE, NULL);
    if (ret) {
        fprintf(stderr, "Unable to set cancel state for scroller thread\n");
        pthread_exit(NULL);
    }

    while(1) {
        ret = read(img->scroll_timerfd, &val, sizeof(u_int64_t));
        if (ret != sizeof(u_int64_t)) {
            perror("Scroll thread exiting!");
            pthread_exit(NULL);
        }

        pthread_mutex_lock(&img->mutex);
        if (img->scroll_enable && img->scroll_data) {
            int reset_timer = 0;

            img->scroll_offset += img->scroll_step;
            if (img->scroll_offset + img->scroll_width >= img->scroll_text_width) {
                img->scroll_offset = img->scroll_text_width - img->scroll_width;
                img->scroll_step *= -1;
                reset_timer = 1;
            } else if (img->scroll_offset < 0) {
                img->scroll_offset = 0;
                img->scroll_step *= -1;
                reset_timer = 1;
            }

            if (reset_timer && img->scroll_end_delay_ms) {
                set_timer(img->scroll_timerfd, img->scroll_end_delay_ms, -1);
            }

            copy_buffer(img->scroll_data, img->scroll_text_width, img->scroll_height, img->scroll_offset, 0,
                    img->data, img->width, img->height, img->scroll_x, img->scroll_y,
                    img->scroll_width, img->scroll_height);

            if (img->membuf || img->filename) {
                mg_image_write(img, img->filename);
            }

        }
        pthread_mutex_unlock(&img->mutex);
    }
}


struct mg_image *mg_image_create(int width, int height, const char *filename)
{
    int err;
    pthread_mutexattr_t attr;
    struct mg_image *img;

    img = malloc(sizeof *img);
    if (img == NULL) {
        perror("Out of memory\n");
        return NULL;
    }
    memset(img, 0, sizeof(*img));

    if (filename) {
        img->filename = strdup(filename);
    }

    img->width = width;
    img->height = height;
    img->size = width * height;
    img->data = malloc(img->size * sizeof(char));
    if (img->data == NULL) {
        perror("Out of memory\n");
        goto exit_err;
    }
    memset(img->data, 0, img->size * sizeof(char));

    err = FT_Init_FreeType(&img->ft.library);
    if (err) {
        perror("Error initializing FreeType library!\n");
        goto exit_err;
    }

    img->scroll_timerfd = timerfd_create(CLOCK_REALTIME, 0);
    if (img->scroll_timerfd < 0) {
        perror("Unable to create timer");
        goto exit_err;
    }

    pthread_mutexattr_init(&attr);
    pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    err = pthread_mutex_init(&img->mutex, &attr);
    pthread_mutexattr_destroy(&attr);
    if (err) {
        perror("Error initializing image mutex!\n");
        goto exit_err;
    }

    err = pthread_create(&img->scroll_pth, NULL, scroll_thread, img);
    if (err) {
        perror("Unable to start scroller thread");
        goto exit_err;
    }

    return img;

exit_err:
    pthread_mutex_destroy(&img->mutex);
    free(img->filename);
    free(img->data);
    free(img);
    return NULL;
}


void mg_image_scrolltext(struct mg_image *img, int face_id, const char *text,
        int x, int y, int width, int color,
        int initial_delay_ms, int shift_delay_ms, int end_delay_ms)
{
    int char_width = 0;
    int text_width = 0;
    int text_height = 0;
    int buf_size;

    pthread_mutex_lock(&img->mutex);

    /* If a call to scrolltext comes in and scrolling is already enabled, then caller has requested
     * multiple scrolling texts on the same screen. As this is currently not supported, clear the
     * previous scrolling config and only keep the last one */
    if (img->scroll_enable) {
        clear_scrolltext(img);
    }

    FT_Face face = img->ft.faces[face_id];

    /* the fonts supported by this function all have a single size */
    if (face->available_sizes) {
        char_width = face->available_sizes[0].width;
        text_height = face->available_sizes[0].height;
    }

    text_width = strlen(text) * char_width;
    if (text_width <= width) {
        mg_image_puts(img, face_id, text, x, y, color, 0, 0, 0, 0, 0);
        goto exit;
    }

    /* Check if we have an identical scrolling config from a previous render. If so, then
     * simply reuse the previous config and continue where we left off earlier, otherwise
     * set up a new scroller config */
    if (img->scroll_text == NULL
            || strcmp(img->scroll_text, text) != 0
            || img->scroll_width != width
            || img->scroll_height != text_height
            || img->scroll_text_width != text_width)
    {
        clear_scrolltext(img);

        buf_size = text_width * text_height;
        img->scroll_data = malloc(buf_size * sizeof(char));
        if (img->scroll_data == NULL) {
            clear_scrolltext(img);
            goto exit;
        }
        img->scroll_text = strdup(text);
        if (img->scroll_text == NULL) {
            clear_scrolltext(img);
            goto exit;
        }
        memset(img->scroll_data, 0, buf_size * sizeof(char));

        /* render the text into a dedicated buffer once, then use that buffer
        * during scrolling */
        puts_line(text_width, text_height, img->scroll_data, face,
                text, strlen(text), 0, 0, color, 0, 0);

        img->scroll_width = width;
        img->scroll_height = text_height;
        img->scroll_text_width = text_width;
        img->scroll_offset = 0;
        img->scroll_step = 1;
        img->scroll_end_delay_ms = end_delay_ms;

        if (!initial_delay_ms) {
            initial_delay_ms = shift_delay_ms;
        }
    }
    else {
        initial_delay_ms = shift_delay_ms;
    }

    img->scroll_x = x;
    img->scroll_y = y;

    /* Write the initially visible text into the image */
    copy_buffer(img->scroll_data, img->scroll_text_width, img->scroll_height, img->scroll_offset, 0,
            img->data, img->width, img->height, img->scroll_x, img->scroll_y,
            img->scroll_width, img->scroll_height);

    img->scroll_enable = 1;

    /* Start the scroll timer */
    if (shift_delay_ms) {
        set_timer(img->scroll_timerfd, initial_delay_ms, shift_delay_ms);
    }

exit:
    pthread_mutex_unlock(&img->mutex);
}

static void set_timer(int fd, int initial_ms, int interval_ms)
{
    struct itimerspec itimer;
    if (timerfd_gettime(fd, &itimer)) {
        fprintf(stderr, "unable to get time from timerfd!\n");
        return;
    }
    if (initial_ms >= 0) {
        itimer.it_value.tv_sec = initial_ms / 1000;
        itimer.it_value.tv_nsec = (initial_ms % 1000) * 1000 * 1000;
    }
    if (interval_ms >= 0) {
        itimer.it_interval.tv_sec = interval_ms / 1000;
        itimer.it_interval.tv_nsec = (interval_ms % 1000) * 1000 * 1000;
    }
    if (timerfd_settime(fd, 0, &itimer, NULL)) {
        fprintf(stderr, "Unable to set timerfd\n");
    }
}

/* Stops the scrolling but leaves the scroller configuration in place. Used to resume
 * scrolling in cases when simply the x/y position of the scrollbox has changed from the
 * previous image write */
static void stop_scrolltext(struct mg_image *img)
{
    struct itimerspec itimer;

    img->scroll_enable = 0;

    /* clear timer */
    itimer.it_value.tv_sec = 0;
    itimer.it_value.tv_nsec = 0;
    itimer.it_interval.tv_sec = 0;
    itimer.it_interval.tv_nsec = 0;
    timerfd_settime(img->scroll_timerfd, 0, &itimer, NULL);
}

/* Stop and clear all scroll configuration */
static void clear_scrolltext(struct mg_image *img)
{
    stop_scrolltext(img);

    free(img->scroll_data);
    img->scroll_data = NULL;

    free(img->scroll_text);
    img->scroll_text = NULL;
}

static void copy_buffer(const char *src, int src_width, int src_height, int src_x, int src_y, 
                        char *dst, int dst_width, int dst_height, int dst_x, int dst_y,
                        int width, int height)
{
    int row, col;
    int src_idx, dst_idx;

    for (row = 0; row < height; row++) {
        for (col = 0; col < width; col++) {
            if ((row + dst_y < dst_height && col + dst_x < dst_width) &&
                (row + src_y < src_height && col + src_x < src_width)) {
                dst_idx = (row + dst_y) * dst_width + col + dst_x;
                src_idx = (row + src_y) * src_width + col + src_x;
                dst[dst_idx] = src[src_idx];
            }
        }
    }
}


void mg_image_destroy(struct mg_image *img)
{
    int i;

    pthread_mutex_lock(&img->mutex);

    pthread_cancel(img->scroll_pth);
    pthread_join(img->scroll_pth, NULL);

    for (i=0; i<img->ft.face_count; i++) {
        FT_Done_Face(img->ft.faces[i]);
    }

    if (img->membuf) {
        munmap(img->membuf, img->size / 8);
    }

    free(img->filename);
    free(img->scroll_data);
    free(img->data);
    pthread_mutex_unlock(&img->mutex);

    if (pthread_mutex_destroy(&img->mutex)) {
        fprintf(stderr, "Unable to destroy mutex!\n");
    }

    free(img);
}


int mg_image_load_font(struct mg_image *img, const char *filename)
{
    int err;
    int id = img->ft.face_count;

    pthread_mutex_lock(&img->mutex);

    if (img->ft.face_count == MG_IMAGE_MAX_FONTS) {
        fprintf(stderr, "Maximum fonts reached for image!\n");
        id = -1;
        goto exit;
    }

    err = FT_New_Face(img->ft.library, filename, 0, &img->ft.faces[id]);
    if (err) {
        fprintf(stderr, "Error loading font %s: %d\n", filename, err);
        id = -1;
        goto exit;
    }

    img->ft.face_count++;

exit:
    pthread_mutex_unlock(&img->mutex);

    return id;
}


static void draw_ft_bitmap(int width, int height, char *buffer, FT_Bitmap *bitmap,
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
                if (ix < 0 || ix < start_x || (max_x > 0 && ix > max_x) || iy < 0 || ix >= width ||
                        iy >= height)
                    continue;
                if (color) {
                    buffer[iy * width + ix] |=
                        (b & (1 << i)) ? 1 : 0;
                }
                else {
                    if (b & (1 << i)) {
                        buffer[iy * width + ix] &= 0;
                    }

                }
            }
        }
    }
}


static void puts_line(int img_width, int img_height, char *img_data, FT_Face face,
        const char *text, int textlen, int x, int y, int color, int max_width, int x_offset)
{
    int i;
    int start_x;
    int max_x = 0;

    FT_GlyphSlot slot = face->glyph;

    start_x = x;
    if (max_width > 0)
        max_x = start_x + max_width;
    x += x_offset;
    for (i=0; i<textlen; i++) {
        if (FT_Load_Char(face, (unsigned char) text[i],
                    FT_LOAD_RENDER | FT_LOAD_MONOCHROME))
            return;
        draw_ft_bitmap(img_width, img_height, img_data, &slot->bitmap,
                x - slot->bitmap_left, y, color, start_x, max_x);
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

    pthread_mutex_lock(&img->mutex);

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

            puts_line(img->width, img->height, img->data, face,
                    line, textlen, line_x, y, color, max_width, x_offset);
        }

        y += char_h;
        y += line_spacing;

        // advance char pointer to beginning of next line
        line += textlen + 1;
    }

    free(input);

    pthread_mutex_unlock(&img->mutex);
}


void mg_image_clear(struct mg_image *img, int x0, int y0, int x1, int y1)
{
    pthread_mutex_lock(&img->mutex);

    stop_scrolltext(img);

    if (x0 >=0 && y0 >=0 && x1 >= 0 && y1 >= 0) {
        mg_image_rect(img, x0, y0, x1, y1, 0, 0);
    }
    else {
        memset(img->data, 0, img->size * sizeof(char));
    }

    pthread_mutex_unlock(&img->mutex);
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
    pthread_mutex_lock(&img->mutex);

    if (x0 == x1)
        vline(img, x0, y0, y1, c);
    else if (y0 == y1)
        hline(img, x0, x1, y0, c);
    else
        bline(img, x0, y0, x1, y1, c);

    pthread_mutex_unlock(&img->mutex);
}


void mg_image_rect(struct mg_image *img, int x0, int y0, int x1, int y1,
        int c, int fill)
{
    int x, y, xmax, ymax, ix, iy;

    pthread_mutex_lock(&img->mutex);

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

    pthread_mutex_unlock(&img->mutex);
}




void mg_image_point(struct mg_image *img, int x, int y, int c)
{
    int idx = y * img->width + x;

    pthread_mutex_lock(&img->mutex);

    if (idx < img->size)
        img->data[idx] = c;

    pthread_mutex_unlock(&img->mutex);
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
    int ret = -1;
    char *mm;

    pthread_mutex_lock(&img->mutex);

    fd = open(filename, O_RDWR);
    if (fd < 0) {
        perror("Unable to open output file");
        goto exit;
    }

    mm = (char *) mmap(0, img->size / 8, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mm == MAP_FAILED) {
        perror("Failed to map framebuffer device to memory");
        goto exit;
    }

    img->membuf = mm;

    ret = 0;

exit:
    pthread_mutex_unlock(&img->mutex);

    return ret;
}


int mg_image_write(struct mg_image *img, const char *filename)
{
    int fd = -1;
    int ret = -1;
    char *buf = NULL;

    pthread_mutex_lock(&img->mutex);

    /* Previous image clear has stopped scrolling and no new scroll width has been created.
     * So get rid of the old config now */
    if (img->scroll_data != NULL && !img->scroll_enable) {
        clear_scrolltext(img);
    }

    // If this image has a memory mapped output file, just convert
    // into the buffer and exit.
    if (img->membuf != NULL) {
        convert_8bpp_to_1bpp(img, img->membuf);
        ret = 0;
        goto exit;
    }

    // Otherwise convert to new buffer and write to output file
    buf = malloc((img->size / 8) * sizeof(char));
    if (buf == NULL) {
        perror("Out of memory");
        goto exit;
    }

    convert_8bpp_to_1bpp(img, buf);

    fd = open(filename, O_WRONLY);
    if (fd < 0) {
        perror("Unable to open output file");
        goto exit;
    }

    ret = write(fd, buf, img->size / 8);
    if (ret < 0) {
        perror("Unable to write file");
    }

exit:
    if (fd != -1) {
        close(fd);
    }
    free(buf);
    pthread_mutex_unlock(&img->mutex);

    return ret;
}
