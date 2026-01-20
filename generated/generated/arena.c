#include "arena.h"

#define ALIGNMENT 64

void Arena_Init(Arena* arena, uint8_t* buffer, size_t capacity) {
    arena->buffer = buffer;
    arena->capacity = capacity;
    arena->offset = 0;
}

size_t Arena_Alloc(Arena* arena, size_t size) {
    size_t current = arena->offset;
    
    // Align current offset to next 64-byte boundary
    // Formula: (x + 63) & ~63
    size_t start = (current + (ALIGNMENT - 1)) & ~(ALIGNMENT - 1);

    // Check for overflow or out of bounds
    if (start + size > arena->capacity || start + size < start) {
        return SIZE_MAX;
    }

    arena->offset = start + size;
    return start;
}

size_t Arena_GetPos(const Arena* arena) {
    return arena->offset;
}

void Arena_SetPos(Arena* arena, size_t pos) {
    if (pos <= arena->capacity) {
        arena->offset = pos;
    }
}

void Arena_Reset(Arena* arena) {
    arena->offset = 0;
}
