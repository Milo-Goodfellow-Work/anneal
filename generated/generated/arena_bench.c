/*
 * Arena allocator benchmark - new optimized version
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
#define MARKS_CAP 1024

static inline double time_diff_sec(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) +
           (end.tv_nsec - start.tv_nsec) / 1e9;
}

int main(void) {
    struct timespec t_start, t_end, t_ops_start, t_ops_end;
    
    clock_gettime(CLOCK_MONOTONIC, &t_start);
    
    printf("=== Arena Allocator Benchmark (Optimized) ===\n");
    printf("Arena size: %.2f GB\n", ARENA_SIZE / (1024.0 * 1024 * 1024));
    printf("Iterations: %.2f billion\n", NUM_ITERATIONS / 1e9);
    printf("Alloc size: %d bytes (cache-line aligned)\n\n", ALLOC_SIZE);
    
    /* Single malloc for backing memory */
    printf("Allocating backing memory...\n");
    void* backing = malloc(ARENA_SIZE);
    if (!backing) {
        fprintf(stderr, "Failed to allocate backing memory\n");
        return 1;
    }
    
    size_t marks[MARKS_CAP];
    arena_t arena;
    
    if (!arena_init(&arena, backing, ARENA_SIZE, marks, MARKS_CAP)) {
        fprintf(stderr, "Failed to init arena\n");
        return 1;
    }
    
    /* How many allocations fit in the arena? */
    size_t allocs_per_batch = ARENA_SIZE / ALLOC_SIZE;
    size_t total_allocs = 0;
    size_t total_resets = 0;
    size_t out_off;
    
    printf("Starting ops timer...\n\n");
    
    /* ========== TIMED OPERATIONS ========== */
    clock_gettime(CLOCK_MONOTONIC, &t_ops_start);
    
    while (total_allocs < NUM_ITERATIONS) {
        /* Allocate until full */
        size_t batch = 0;
        while (batch < allocs_per_batch && total_allocs < NUM_ITERATIONS) {
            if (!arena_alloc(&arena, ALLOC_SIZE, &out_off)) break;
            batch++;
            total_allocs++;
        }
        /* Reset */
        arena_reset(&arena);
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
