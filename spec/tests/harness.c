#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "two_sum.h"

int main() {
    int64_t n, target;
    if (scanf("%ld %ld", &n, &target) != 2) return 0;

    int64_t* nums = (int64_t*)malloc(sizeof(int64_t) * n);
    for (int64_t i = 0; i < n; i++) {
        if (scanf("%ld", &nums[i]) != 1) break;
    }

    TwoSumResult result = solve_two_sum(nums, n, target);
    printf("%ld %ld\n", result.index1, result.index2);

    free(nums);
    return 0;
}
