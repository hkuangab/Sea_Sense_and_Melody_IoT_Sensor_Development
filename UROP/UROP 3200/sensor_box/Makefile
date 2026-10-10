# Makefile for the Sensor Box application
#
# Targets:
#   make            Build the application (default)
#   make -j4        Parallel build
#   make clean      Remove object files and the binary
#   make doxygen    Generate API documentation into docs/doxygen_out/
#                   Requires the Doxyfile in this directory.
#   make check      Run cppcheck static analysis, if available
#
# Author:   KUANG, Haozhe
#          The Hong Kong University of Science and Technology
# Email:    hkuangab@connect.ust.hk
# Date:     2026/10/06

PROG      := sensor_box

# Compilers and flags. The pthread flag is required by the display and
# touch modules; libm and libgpiod are needed for math and GPIO.
CC        := cc
CFLAGS    := -O2 -Wall -Wextra -Wno-unused-parameter -std=gnu17
LIBS      := -lm -lpthread -lgpiod

# Per-file flags. touch_sensor.c is built without optimisation so that
# its state variables are easier to inspect during debugging; if that
# matters, remove the override below.
CFLAGS_TOUCH := -O0 -Wall -Wextra -std=gnu17

OBJS := main.o mcp3008.o light_sensor.o sound_sensor.o touch_sensor.o \
        seg7_display.o lcd1602.o csv_writer.o jsonl_writer.o term_print.o \
        math_util.o

.PHONY: all clean doxygen check

all: $(PROG)

$(PROG): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LIBS)

main.o: main.c sensor_box.h
	$(CC) $(CFLAGS) -c $< -o $@

mcp3008.o: mcp3008.c mcp3008.h
	$(CC) $(CFLAGS) -c $< -o $@

light_sensor.o: light_sensor.c light_sensor.h sensor_box.h mcp3008.h math_util.h
	$(CC) $(CFLAGS) -c $< -o $@

sound_sensor.o: sound_sensor.c sound_sensor.h sensor_box.h mcp3008.h \
                seg7_display.h math_util.h
	$(CC) $(CFLAGS) -c $< -o $@

touch_sensor.o: touch_sensor.c touch_sensor.h sensor_box.h seg7_display.h \
                math_util.h
	$(CC) $(CFLAGS_TOUCH) -c $< -o $@

seg7_display.o: seg7_display.c seg7_display.h sensor_box.h
	$(CC) $(CFLAGS) -c $< -o $@

lcd1602.o: lcd1602.c lcd1602.h sensor_box.h
	$(CC) $(CFLAGS) -c $< -o $@

csv_writer.o: csv_writer.c csv_writer.h sensor_box.h
	$(CC) $(CFLAGS) -c $< -o $@

jsonl_writer.o: jsonl_writer.c jsonl_writer.h sensor_box.h
	$(CC) $(CFLAGS) -c $< -o $@

term_print.o: term_print.c term_print.h sensor_box.h
	$(CC) $(CFLAGS) -c $< -o $@

math_util.o: math_util.c math_util.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(PROG)

doxygen:
	doxygen Doxyfile

check:
	@if command -v cppcheck >/dev/null 2>&1; then \
		cppcheck --enable=all --suppress=missingIncludeSystem \
		         --inconclusive *.c *.h; \
	else \
		echo "cppcheck not installed; skipping static analysis"; \
	fi
