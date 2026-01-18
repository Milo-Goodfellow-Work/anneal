#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../generated/generated/arena.h"

#define MAX_MARKS 2048

int main(void) {
  size_t cap = 0, cache_line = 0, steps = 0;
  if (scanf("%zu %zu %zu", &cap, &cache_line, &steps) != 3) return 1;

  uint8_t *buf = (uint8_t *)malloc(cap);
  if (!buf) return 2;

  Arena a;
  int init_rc = arena_init(&a, buf, cap, cache_line);
  if (init_rc != 0) {
    printf("INIT ERR %d\n", init_rc);
    free(buf);
    return 0;
  }

  ArenaMarker marks[MAX_MARKS];
  size_t mark_count = 0;

  for (size_t i = 0; i < steps; i++) {
    char op = 0;
    if (scanf(" %c", &op) != 1) break;

    if (op == 'A') {
      size_t n = 0;
      if (scanf("%zu", &n) != 1) n = 0;
      void *p = arena_alloc(&a, n);
      if (!p) {
        printf("A FAIL top=%zu rem=%zu\n", a.top, arena_remaining(&a));
      } else {
        size_t off = (size_t)((uint8_t *)p - a.buf);
        printf("A OK off=%zu top=%zu rem=%zu\n", off, a.top, arena_remaining(&a));
      }
    } else if (op == 'M') {
      if (mark_count < MAX_MARKS) {
        marks[mark_count++] = arena_mark(&a);
        printf("M idx=%zu top=%zu\n", mark_count - 1, a.top);
      } else {
        printf("M FAIL_FULL\n");
      }
    } else if (op == 'R') {
      size_t idx = 0;
      if (scanf("%zu", &idx) != 1) idx = 0;
      if (idx >= mark_count) {
        printf("R FAIL_BADIDX idx=%zu\n", idx);
      } else {
        int rc = arena_reset(&a, marks[idx]);
        if (rc != 0) printf("R FAIL rc=%d\n", rc);
        else printf("R OK idx=%zu top=%zu rem=%zu\n", idx, a.top, arena_remaining(&a));
      }
    } else if (op == 'C') {
      arena_clear(&a);
      printf("C OK top=%zu rem=%zu\n", a.top, arena_remaining(&a));
    } else {
      printf("UNK %c\n", op);
    }
  }

  free(buf);
  return 0;
}
