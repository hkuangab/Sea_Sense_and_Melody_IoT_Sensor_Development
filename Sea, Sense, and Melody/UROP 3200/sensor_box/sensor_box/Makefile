# Makefile for Sensor Box (main_camera.c as entry point, libcamera support)
#
# Targets:
#   make            Force-rebuild all source files and link (default)
#   make -j4        Parallel force-build
#   make clean      Remove object files and the binary
#   make rebuild    Clean and rebuild from scratch
#
# Author:   KUANG, Haozhe
#           The Hong Kong University of Science and Technology
# Email:    hkuangab@connect.ust.hk
# Date:     2026/10/18

# --- Executable name ---
PROG      := sensor_box

# --- Compilers and flags ---
CC        := cc
CXX       := c++
CFLAGS    := -std=c11 -D_POSIX_C_SOURCE=200112L -D_GNU_SOURCE -O2 -Wall -Wextra -Wpedantic -pthread
CXXFLAGS  := -std=c++20 -O2 -Wall -Wextra -pthread
LDFLAGS   := -pthread -lm -lgpiod

# libcamera flags (via pkg-config)
CXXFLAGS += $(shell pkg-config --cflags libcamera)
LDFLAGS  += $(shell pkg-config --libs libcamera)

# SDL2 flags (simple linking; use pkg-config if needed)
LDFLAGS  += -lSDL2

# ==== ADDED: SDL2_ttf for text rendering and librt for POSIX message queues ====
LDFLAGS  += -lSDL2_ttf -lrt

# --- Source files: separate C and C++ ---
SRCS_C    := $(filter-out camera_sensor.cpp,$(wildcard *.c))
SRCS_CPP  := camera_sensor.cpp
OBJS      := $(patsubst %.c,%.o,$(SRCS_C)) $(patsubst %.cpp,%.o,$(SRCS_CPP))

# --- Phony targets ---
.PHONY: all clean rebuild FORCE

# --- Default target ---
all: $(PROG)

# --- Link step ---
$(PROG): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJS) $(LDFLAGS)

# --- Pattern rules (force recompile via FORCE) ---
%.o: %.c FORCE
	$(CC) $(CFLAGS) -c $< -o $@

%.o: %.cpp FORCE
	$(CXX) $(CXXFLAGS) -c $< -o $@

# --- FORCE is always out-of-date ---
FORCE:

# --- Clean ---
clean:
	rm -f $(OBJS) $(PROG)

# --- Rebuild ---
rebuild: clean all