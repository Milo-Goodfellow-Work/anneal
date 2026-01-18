#ifndef GENERATED_ARENA_H
#define GENERATED_ARENA_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifndef ARENA_CACHELINE
#define ARENA_CACHELINE 64u
#endif

typedef struct {
  uint64_t capacity;
  uint64_t top;
} Arena;

typedef struct {
  bool ok;
  uint64_t offset;
  uint64_t size;
  uint64_t align;
} ArenaAllocResult;

static inline bool arena_is_pow2_u64(uint64_t x) {
  return x != 0u && ((x & (x - 1u)) == 0u);
}

static inline uint64_t arena_align_up_u64(uint64_t x, uint64_t a) {
  // a must be >0
  return ((x + (a - 1u)) / a) * a;
}

Arena arena_init(uint64_t capacity);
uint64_t arena_used(const Arena* a);
uint64_t arena_remaining(const Arena* a);
Arena arena_alloc(Arena a, uint64_t size, uint64_t align, ArenaAllocResult* out);
Arena arena_alloc_cacheline(Arena a, uint64_t size, ArenaAllocResult* out);
uint64_t arena_mark(const Arena* a);
Arena arena_reset_to_mark(Arena a, uint64_t mark);
Arena arena_reset(Arena a);

#endif
