#ifndef GENERATED_ARENA_H
#define GENERATED_ARENA_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Cache line size for alignment
#define ARENA_CACHELINE 64u

static inline size_t align_up_pow2(size_t n, size_t a) {
  // a must be power of two
  return (n + (a - 1u)) & ~(a - 1u);
}

typedef struct {
  uint8_t *base;
  size_t cap;
  size_t top;
  size_t *marks;
  size_t marks_cap;
  size_t marks_len;
} arena_t;

bool arena_init(arena_t *a, void *buffer, size_t cap_bytes, size_t *marks_buf, size_t marks_cap);

static inline void arena_reset(arena_t *a) {
  a->top = 0;
  a->marks_len = 0;
}

static inline void arena_push(arena_t *a) {
  if (a->marks_len < a->marks_cap) {
    a->marks[a->marks_len++] = a->top;
  }
}

static inline void arena_pop(arena_t *a) {
  if (a->marks_len > 0) {
    a->top = a->marks[--a->marks_len];
  }
}

static inline size_t arena_remaining(const arena_t *a) {
  return (a->top <= a->cap) ? (a->cap - a->top) : 0u;
}

static inline bool arena_alloc(arena_t *a, size_t n, size_t *out_off) {
  size_t start = align_up_pow2(a->top, (size_t)ARENA_CACHELINE);
  size_t new_top = start + n;
  if (__builtin_expect(new_top <= a->cap, 1)) {
    a->top = new_top;
    if (out_off) *out_off = start;
    return true;
  }
  if (out_off) *out_off = 0u;
  return false;
}

#ifdef __cplusplus
}
#endif

#endif
