#include "two_sum.h"
#include <stdlib.h>

typedef struct {
    int64_t value;
    int64_t index;
} IndexedValue;

static int compare_indexed_values(const void* a, const void* b) {
    const IndexedValue* iv1 = (const IndexedValue*)a;
    const IndexedValue* iv2 = (const IndexedValue*)b;
    if (iv1->value < iv2->value) return -1;
    if (iv1->value > iv2->value) return 1;
    if (iv1->index < iv2->index) return -1;
    if (iv1->index > iv2->index) return 1;
    return 0;
}

TwoSumResult solve_two_sum(const int64_t* nums, int64_t nums_size, int64_t target) {
    TwoSumResult result = {-1, -1};
    if (nums_size < 2) return result;

    IndexedValue* indexed = (IndexedValue*)malloc(sizeof(IndexedValue) * nums_size);
    if (!indexed) return result;

    for (int64_t i = 0; i < nums_size; i++) {
        indexed[i].value = nums[i];
        indexed[i].index = i;
    }

    qsort(indexed, nums_size, sizeof(IndexedValue), compare_indexed_values);

    int64_t l = 0;
    int64_t r = nums_size - 1;

    while (l < r) {
        int64_t sum = indexed[l].value + indexed[r].value;
        if (sum == target) {
            if (indexed[l].index < indexed[r].index) {
                result.index1 = indexed[l].index;
                result.index2 = indexed[r].index;
            } else {
                result.index1 = indexed[r].index;
                result.index2 = indexed[l].index;
            }
            break;
        } else if (sum < target) {
            l++;
        } else {
            r--;
        }
    }

    free(indexed);
    return result;
}
