#include "arena.h"

static int is_pow2(size_t x) {
  return x != 0 && (x & (x - 1)) == 0;
}

static size_t align_up(size_t x, size_t a) {
  /* a must be power of two */
  return (x + (a - 1)) & ~(a - 1);
}

int arena_init(Arena *ar, uint8_t *buf, size_t cap, size_t cache_line) {
  if (!ar || !buf) return 1;
  if (cap == 0) return 2;
  if (cache_line == 0) return 3;
  if (!is_pow2(cache_line)) return 4;
  ar->buf = buf;
  ar->cap = cap;
  ar->top = 0;
  ar->cache_line = cache_line;
  return 0;
}

void *arena_alloc(Arena *ar, size_t n) {
  if (!ar) return NULL;
  if (n == 0) return NULL;
  if (ar->cache_line == 0 || !is_pow2(ar->cache_line)) return NULL;

  size_t start = align_up(ar->top, ar->cache_line);
  if (start > ar->cap) return NULL;
  if (n > ar->cap - start) return NULL;

  ar->top = start + n;
  return (void *)(ar->buf + start);
}

ArenaMarker arena_mark(const Arena *ar) {
  ArenaMarker m;
  m.top = ar ? ar->top : 0;
  return m;
}

int arena_reset(Arena *ar, ArenaMarker m) {
  if (!ar) return 1;
  if (m.top > ar->cap) return 2;
  ar->top = m.top;
  return 0;
}

void arena_clear(Arena *ar) {
  if (!ar) return;
  ar->top = 0;
}

size_t arena_remaining(const Arena *ar) {
  if (!ar) return 0;
  if (ar->top >= ar->cap) return 0;
  return ar->cap - ar->top;
}
