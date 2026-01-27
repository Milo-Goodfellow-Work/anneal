#include "two_sum.h"
#include <stdlib.h>
#include <string.h>

typedef struct {
    long long key;
    int value;
    int occupied;
} HashEntry;

unsigned int hash(long long key, int size) {
    unsigned long long k = (unsigned long long)key;
    k ^= k >> 33;
    k *= 0xff51afd7ed558ccdULL;
    k ^= k >> 33;
    k *= 0xc4ceb9fe1a85ec53ULL;
    k ^= k >> 33;
    return (unsigned int)(k % size);
}

void solve_two_sum(int n, long long target, long long* nums, int* r1, int* r2) {
    int size = n * 2 + 7;
    HashEntry* table = (HashEntry*)calloc(size, sizeof(HashEntry));
    
    *r1 = -1;
    *r2 = -1;

    for (int i = 0; i < n; i++) {
        long long complement = target - nums[i];
        unsigned int h = hash(complement, size);
        
        while (table[h].occupied) {
            if (table[h].key == complement) {
                *r1 = table[h].value;
                *r2 = i;
                free(table);
                return;
            }
            h = (h + 1) % size;
        }
        
        // Insert current
        h = hash(nums[i], size);
        while (table[h].occupied) {
            h = (h + 1) % size;
        }
        table[h].key = nums[i];
        table[h].value = i;
        table[h].occupied = 1;
    }
    
    free(table);
}
