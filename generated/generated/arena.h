#ifndef GENERATED_ARENA_H
#define GENERATED_ARENA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
  Stack-based arena allocator with cache-line respecting alignment.

  Model:
    - Arena owns a byte buffer [0, cap)
    - top is the current stack pointer (offset)
    - allocations bump top up to an aligned boundary
    - markers allow stack-like deallocation (reset to marker)

  Cache line size is configurable per arena (power of two).
*/

typedef struct {
  uint8_t *buf;      /* owned externally by caller */
  size_t cap;        /* capacity in bytes */
  size_t top;        /* next free offset */
  size_t cache_line; /* alignment unit (power of two, >= 1) */
} Arena;

typedef struct {
  size_t top;
} ArenaMarker;

/* Initialize arena with external buffer. Returns 0 on success, nonzero on error. */
int arena_init(Arena *a, uint8_t *buf, size_t cap, size_t cache_line);

/* Allocate n bytes with cache-line alignment. Returns NULL on OOM or invalid input. */
void *arena_alloc(Arena *a, size_t n);

/* Save/restore stack pointer. */
ArenaMarker arena_mark(const Arena *a);
int arena_reset(Arena *a, ArenaMarker m);

/* Reset arena to empty. */
void arena_clear(Arena *a);

/* Helpers */
size_t arena_remaining(const Arena *a);

#ifdef __cplusplus
}
#endif

#endif
