#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <inttypes.h>

#include "../../generated/generated/arena.h"

static void print_alloc(const Arena *a, const ArenaAllocResult *r) {
  // Print arena state and alloc result in a single line for easy diff.
  // Format: top capacity ok offset size align
  printf("%" PRIu64 " %" PRIu64 " %d %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",
         a->top, a->capacity, r->ok ? 1 : 0, r->offset, r->size, r->align);
}

int main(void) {
  uint64_t capacity = 0;
  int steps = 0;
  if (scanf("%" SCNu64 " %d", &capacity, &steps) != 2) return 0;

  Arena a = arena_init(capacity);

  for (int i = 0; i < steps; i++) {
    char op = 0;
    if (scanf(" %c", &op) != 1) break;

    if (op == 'A') {
      uint64_t size = 0, align = 0;
      scanf("%" SCNu64 " %" SCNu64, &size, &align);
      ArenaAllocResult r;
      a = arena_alloc(a, size, align, &r);
      print_alloc(&a, &r);
    } else if (op == 'C') {
      uint64_t size = 0;
      scanf("%" SCNu64, &size);
      ArenaAllocResult r;
      a = arena_alloc_cacheline(a, size, &r);
      print_alloc(&a, &r);
    } else if (op == 'M') {
      uint64_t m = arena_mark(&a);
      printf("MARK %" PRIu64 "\n", m);
    } else if (op == 'R') {
      uint64_t m = 0;
      scanf("%" SCNu64, &m);
      a = arena_reset_to_mark(a, m);
      printf("RESET %" PRIu64 " %" PRIu64 "\n", a.top, a.capacity);
    } else if (op == 'Z') {
      a = arena_reset(a);
      printf("ZERO %" PRIu64 " %" PRIu64 "\n", a.top, a.capacity);
    } else {
      // unknown op; consume line
      int c;
      while ((c = getchar()) != '\n' && c != EOF) {}
    }
  }

  return 0;
}
