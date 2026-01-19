#include "arena.h"

bool arena_init(arena_t *a, void *buffer, size_t cap_bytes, size_t *marks_buf, size_t marks_cap) {
  if (!a || !buffer || !marks_buf) return false;
  a->base = (uint8_t *)buffer;
  a->cap = cap_bytes;
  a->top = 0u;
  a->marks = marks_buf;
  a->marks_cap = marks_cap;
  a->marks_len = 0u;
  return true;
}
