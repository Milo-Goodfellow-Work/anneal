#ifndef ARENA_H
#define ARENA_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint8_t* buffer;
    size_t capacity;
    size_t offset;
} Arena;

// Initialize the arena with a buffer and size
void Arena_Init(Arena* arena, uint8_t* buffer, size_t capacity);

// Allocate 'size' bytes, aligned to 64 bytes (cache line).
// Returns the offset relative to the buffer start.
// Returns SIZE_MAX if allocation fails (OOM).
size_t Arena_Alloc(Arena* arena, size_t size);

// Get the current offset (mark)
size_t Arena_GetPos(const Arena* arena);

// Set the current offset (release/pop)
void Arena_SetPos(Arena* arena, size_t pos);

// Reset the arena to empty
void Arena_Reset(Arena* arena);

#endif
