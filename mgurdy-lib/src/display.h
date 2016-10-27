#ifndef _MG_DISPLAY_H_
#define _MG_DISPLAY_H_

#include <ft2build.h>
#include FT_FREETYPE_H

#define MG_IMAGE_MAX_FONTS (10)

struct mg_image_ft {
    FT_Library  library;
    FT_Face faces[MG_IMAGE_MAX_FONTS];
    int face_count;
    int face;
};


#endif
