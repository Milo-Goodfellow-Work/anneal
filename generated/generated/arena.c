#include "arena.h"

Arena arena_init(uint64_t capacity) {
  Arena a;
  a.capacity = capacity;
  a.top = 0u;
  return a;
}

uint64_t arena_used(const Arena* a) {
  return a->top;
}

uint64_t arena_remaining(const Arena* a) {
  if (a->top >= a->capacity) return 0u;
  return a->capacity - a->top;
}

Arena arena_alloc(Arena a, uint64_t size, uint64_t align, ArenaAllocResult* out) {
  ArenaAllocResult r;
  r.ok = false;
  r.offset = 0u;
  r.size = size;
  r.align = align;

  if (!arena_is_pow2_u64(align)) {
    if (out) *out = r;
    return a;
  }

  uint64_t alignedTop = arena_align_up_u64(a.top, align);

  // overflow checks: alignedTop + size <= capacity
  if (alignedTop > a.capacity) {
    if (out) *out = r;
    return a;
  }
  if (size > a.capacity - alignedTop) {
    if (out) *out = r;
    return a;
  }

  r.ok = true;
  r.offset = alignedTop;

  a.top = alignedTop + size;
  if (out) *out = r;
  return a;
}

Arena arena_alloc_cacheline(Arena a, uint64_t size, ArenaAllocResult* out) {
  return arena_alloc(a, size, (uint64_t)ARENA_CACHELINE, out);
}

uint64_t arena_mark(const Arena* a) {
  return a->top;
}

Arena arena_reset_to_mark(Arena a, uint64_t mark) {
  if (mark <= a.top) a.top = mark;
  return a;
}

Arena arena_reset(Arena a) {
  a.top = 0u;
  return a;
}
