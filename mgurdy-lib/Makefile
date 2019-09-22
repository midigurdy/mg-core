FREETYPE_CFLAGS=-I/usr/include/freetype2
CFLAGS=-O3 -Wall -std=gnu99 -fPIC $(FREETYPE_CFLAGS) -ffast-math
LDFLAGS=-lc -lrt -lasound -lm -lpthread -lfluidsynth -lwebsockets -fPIC -shared -Wl,-soname,libmgurdy.so -lfreetype

BUILD_DIR = build
SRC_DIR = src
SOURCES = $(shell find $(SRC_DIR)/ -name "*.c")
TARGET  = $(BUILD_DIR)/libmgurdy.so
OBJECTS = $(SOURCES:$(SRC_DIR)/%.c=$(BUILD_DIR)/%.o)

default: $(TARGET)

all: default mgcrashdump

clean:
	rm -rf $(BUILD_DIR)

.SECONDEXPANSION:

$(OBJECTS) : $$(patsubst $(BUILD_DIR)/%.o,$(SRC_DIR)/%.c,$$@)
	mkdir -p $(@D)
	$(CC) -c -o $@ $(CFLAGS) $<

$(TARGET): $(OBJECTS)
	$(CC) $(OBJECTS) -o $@ $(LDFLAGS)

mgcrashdump:
	mkdir -p $(BUILD_DIR)
	$(CC) src/crashdump.c -o $(BUILD_DIR)/mgcrashdump

.PHONY: default clean
