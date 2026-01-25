#ifndef TWO_SUM_H
#define TWO_SUM_H

#include <stdint.h>

typedef struct {
    int64_t index1;
    int64_t index2;
} TwoSumResult;

TwoSumResult solve_two_sum(const int64_t* nums, int64_t nums_size, int64_t target);

#endif
