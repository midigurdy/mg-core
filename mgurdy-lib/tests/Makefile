vpath %.c ../src

FREETYPE_CONFIG=/usr/bin/freetype-config
FREETYPE_CFLAGS=$(shell $(FREETYPE_CONFIG) --cflags)
CFLAGS=-O3 -Wall -std=gnu99 -fPIC $(FREETYPE_CFLAGS)

INCLUDE_DIRS = -I../src
INCLUDE_DIRS += -I$(CMOCKA_DIR)/include
INCLUDE_DIRS += -I$(FLUID_DIR)/include

CFLAGS	+= $(INCLUDE_DIRS)

LDFLAGS = -lc -lrt -lasound -lm -lpthread -lfluidsynth -lwebsockets -lfreetype
LDFLAGS += -L$(FLUID_DIR)/build/src -Wl,-rpath=$(FLUID_DIR)/build/src
LDFLAGS	+= -L$(CMOCKA_DIR)/build/src -Wl,-rpath=$(CMOCKA_DIR)/build/src 
#LDFLAGS += -Wl,--wrap=i2c_read_blocking -Wl,--wrap=i2c_transmit_blocking 
LDFLAGS += -lcmocka

TARGET = runtests

SRC = mg.c state.c worker.c sensors.c server.c midi.c utils.c synth.c
TEST_SRC = tests.c test_utils.c test_synth.c

SRC_OBJ = $(patsubst %.c,obj/%.o,$(SRC)) 
TEST_OBJ = $(patsubst %.c,obj/%.o,$(TEST_SRC)) 
OBJ_DIR = obj

CMOCKA_TAR = cmocka-1.1.0.tar.xz
CMOCKA_DIR = cmocka

FLUID_DIR = /home/marcus/mg/fluidsynth

all: $(CMOCKA_DIR) $(TARGET)
	./$(TARGET)

$(SRC_OBJ): | $(OBJ_DIR)

$(OBJ_DIR):
	@mkdir -p $@

$(OBJ_DIR)/%.o : %.c
	@echo $< 
	$(CC) $(CFLAGS) -c $< -o $@

$(TARGET):  $(SRC_OBJ) $(TEST_OBJ)
	$(CC) -o $@ $^ $(LDFLAGS)

$(CMOCKA_DIR): 
	mkdir -p $@
	tar -xf cmocka-1.1.0.tar.xz -C $@ --strip-components 1
	mkdir -p $@/build
	@(cd $@/build && cmake ../ && make -s)

clean:
	rm -rf $(TARGET) $(OBJ_DIR)
