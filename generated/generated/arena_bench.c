/*
 * Arena allocator benchmark - Gemini-generated version
 * 
 * Compile: gcc -O3 -march=native -o arena_bench arena_bench.c arena.c
 * Run: ./arena_bench
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include "arena.h"

#define ARENA_SIZE (1ULL << 30)  /* 1 GB */
#define NUM_ITERATIONS 1000000000ULL  /* 1 billion */
#define ALLOC_SIZE 64  /* bytes per allocation */

static inline double time_diff_sec(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) +
           (end.tv_nsec - start.tv_nsec) / 1e9;
}

int main(void) {
    struct timespec t_start, t_end, t_ops_start, t_ops_end;
    
    clock_gettime(CLOCK_MONOTONIC, &t_start);
    
    printf("=== Arena Allocator Benchmark (Gemini) ===\n");
    printf("Arena size: %.2f GB\n", ARENA_SIZE / (1024.0 * 1024 * 1024));
    printf("Iterations: %.2f billion\n", NUM_ITERATIONS / 1e9);
    printf("Alloc size: %d bytes (cache-line aligned)\n\n", ALLOC_SIZE);
    
    /* Single malloc for backing memory */
    printf("Allocating backing memory...\n");
    uint8_t* backing = (uint8_t*)malloc(ARENA_SIZE);
    if (!backing) {
        fprintf(stderr, "Failed to allocate backing memory\n");
        return 1;
    }
    
    Arena arena;
    Arena_Init(&arena, backing, ARENA_SIZE);
    
    /* How many allocations fit in the arena? */
    size_t allocs_per_batch = ARENA_SIZE / ALLOC_SIZE;
    size_t total_allocs = 0;
    size_t total_resets = 0;
    
    printf("Starting ops timer...\n\n");
    
    /* ========== TIMED OPERATIONS ========== */
    clock_gettime(CLOCK_MONOTONIC, &t_ops_start);
    
    while (total_allocs < NUM_ITERATIONS) {
        /* Allocate until full */
        size_t batch = 0;
        while (batch < allocs_per_batch && total_allocs < NUM_ITERATIONS) {
            size_t off = Arena_Alloc(&arena, ALLOC_SIZE);
            if (off == SIZE_MAX) break;
            batch++;
            total_allocs++;
        }
        /* Reset */
        Arena_Reset(&arena);
        total_resets++;
    }
    
    clock_gettime(CLOCK_MONOTONIC, &t_ops_end);
    /* ========== END TIMED ========== */
    
    /* Single free */
    free(backing);
    
    clock_gettime(CLOCK_MONOTONIC, &t_end);
    
    double ops_sec = time_diff_sec(t_ops_start, t_ops_end);
    double total_sec = time_diff_sec(t_start, t_end);
    double ops_per_sec = total_allocs / ops_sec;
    
    printf("=== Results ===\n");
    printf("Total allocations: %zu\n", total_allocs);
    printf("Total resets: %zu\n", total_resets);
    printf("\n");
    printf("Ops time:     %.3f sec\n", ops_sec);
    printf("Program time: %.3f sec\n", total_sec);
    printf("\n");
    printf("Speed: %.2f B allocs/sec (%.2f ns/alloc)\n", 
           ops_per_sec / 1e9, 1e9 / ops_per_sec);
    
    return 0;
}
