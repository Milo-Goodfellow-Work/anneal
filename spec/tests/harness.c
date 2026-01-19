#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../generated/generated/arena.h"

int main(void) {
  size_t cap = 0, steps = 0;
  if (scanf("%zu %zu", &cap, &steps) != 2) return 1;

  void *buf = NULL;
  if (cap > 0) {
    buf = aligned_alloc(ARENA_CACHELINE, (cap + ARENA_CACHELINE - 1u) & ~(ARENA_CACHELINE - 1u));
    if (!buf) return 2;
  } else {
    buf = aligned_alloc(ARENA_CACHELINE, ARENA_CACHELINE);
    if (!buf) return 2;
  }

  size_t marks_storage[4096];
  arena_t a;
  if (!arena_init(&a, buf, cap, marks_storage, 4096)) return 3;

  for (size_t i = 0; i < steps; i++) {
    char op[2] = {0};
    if (scanf(" %1s", op) != 1) return 4;
    if (op[0] == 'a') {
      size_t n;
      if (scanf("%zu", &n) != 1) return 5;
      size_t off = 0;
      bool ok = arena_alloc(&a, n, &off);
      printf("A %d %zu %zu\n", ok ? 1 : 0, off, a.top);
    } else if (op[0] == 'p') {
      arena_push(&a);
      printf("P %zu %zu\n", a.top, a.marks_len);
    } else if (op[0] == 'o') {
      arena_pop(&a);
      printf("O %zu %zu\n", a.top, a.marks_len);
    } else if (op[0] == 'r') {
      arena_reset(&a);
      printf("R %zu %zu\n", a.top, a.marks_len);
    } else {
      return 6;
    }
  }

  free(buf);
  return 0;
}
