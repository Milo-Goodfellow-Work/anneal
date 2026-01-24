#ifndef COUNTER_H
#define COUNTER_H

#include <stdint.h>

typedef struct {
    uint32_t value;
} Counter;

static inline Counter Counter_init(void) {
    Counter c = {0};
    return c;
}

static inline Counter Counter_increment(Counter c) {
    c.value++;
    return c;
}

static inline uint32_t Counter_get(Counter c) {
    return c.value;
}

#endif
