#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include "../../generated/generated/stack.h"

static void print_bool(uint8_t b) { printf("%u\n", (unsigned)b); }

int main(void) {
  Stack s = stack_empty();

  int n;
  if (scanf("%d", &n) != 1) return 0;

  for (int i = 0; i < n; ++i) {
    char op[32];
    if (scanf("%31s", op) != 1) return 0;

    if (strcmp(op, "push") == 0) {
      int64_t x64;
      if (scanf("%" SCNd64, &x64) != 1) return 0;
      int32_t x = (int32_t)x64;
      StackRes r = stack_push(s, x);
      s = r.stack;
      printf("push %u\n", (unsigned)r.ok);
    } else if (strcmp(op, "pop") == 0) {
      StackPopRes r = stack_pop(s);
      s = r.stack;
      if (r.ok) {
        printf("pop 1 %" PRId32 "\n", r.value);
      } else {
        printf("pop 0\n");
      }
    } else if (strcmp(op, "peek") == 0) {
      StackPeekRes r = stack_peek(s);
      if (r.ok) {
        printf("peek 1 %" PRId32 "\n", r.value);
      } else {
        printf("peek 0\n");
      }
    } else if (strcmp(op, "isEmpty") == 0) {
      printf("isEmpty ");
      print_bool(stack_isEmpty(s));
    } else if (strcmp(op, "isFull") == 0) {
      printf("isFull ");
      print_bool(stack_isFull(s));
    } else {
      // unknown op
      return 0;
    }
  }

  return 0;
}
