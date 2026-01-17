#ifndef GENERATED_STACK_H
#define GENERATED_STACK_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Safety-critical, deterministic stack of int32.
// Immutable-style API: operations return a new Stack value.

#define STACK_CAPACITY 32

typedef struct {
  int32_t data[STACK_CAPACITY];
  uint32_t size; // number of valid elements
} Stack;

static inline Stack stack_empty(void) {
  Stack s;
  for (size_t i = 0; i < STACK_CAPACITY; ++i) s.data[i] = 0;
  s.size = 0;
  return s;
}

// Result of push/pop
typedef struct {
  Stack stack;
  uint8_t ok; // 1 on success, 0 on failure
} StackRes;

typedef struct {
  Stack stack;
  int32_t value; // valid iff ok==1
  uint8_t ok;
} StackPopRes;

// Query
static inline uint8_t stack_isEmpty(Stack s) { return (uint8_t)(s.size == 0); }
static inline uint8_t stack_isFull(Stack s) { return (uint8_t)(s.size >= STACK_CAPACITY); }

// Push x on top; fails if full.
static inline StackRes stack_push(Stack s, int32_t x) {
  StackRes r;
  r.stack = s;
  if (s.size >= STACK_CAPACITY) {
    r.ok = 0;
    return r;
  }
  r.stack.data[s.size] = x;
  r.stack.size = s.size + 1;
  r.ok = 1;
  return r;
}

// Pop top; fails if empty.
static inline StackPopRes stack_pop(Stack s) {
  StackPopRes r;
  r.stack = s;
  if (s.size == 0) {
    r.ok = 0;
    r.value = 0;
    return r;
  }
  r.value = s.data[s.size - 1];
  r.stack.size = s.size - 1;
  r.ok = 1;
  return r;
}

// Peek top; fails if empty.
typedef struct {
  int32_t value;
  uint8_t ok;
} StackPeekRes;

static inline StackPeekRes stack_peek(Stack s) {
  StackPeekRes r;
  if (s.size == 0) {
    r.ok = 0;
    r.value = 0;
    return r;
  }
  r.ok = 1;
  r.value = s.data[s.size - 1];
  return r;
}

#ifdef __cplusplus
}
#endif

#endif
