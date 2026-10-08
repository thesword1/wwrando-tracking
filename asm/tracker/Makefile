# Host build of the tracker runtime for unit tests (test/test_tracker_c.py builds it the same way).
# The game build goes through asm/patches/tracker.asm and asm/assemble.py instead.

CC ?= gcc
BUILD_DIR ?= build
CFLAGS_HOST = -DTRACKER_HOST -std=gnu17 -O1 -Wall -Werror -fPIC -fvisibility=hidden -fno-strict-aliasing

SOURCES = tracker.c tracker_host.c
HEADERS = $(wildcard *.h) $(filter-out $(SOURCES),$(wildcard *.c))

.PHONY: host clean

host: $(BUILD_DIR)/libtracker_host.so

$(BUILD_DIR)/libtracker_host.so: $(SOURCES) $(HEADERS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS_HOST) -shared -o $@ $(SOURCES)

clean:
	rm -rf $(BUILD_DIR)
