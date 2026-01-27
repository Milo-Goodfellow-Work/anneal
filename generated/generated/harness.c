#include <stdio.h>
#include <stdlib.h>
#include "two_sum.c"

int main() {
    int n;
    if (scanf("%d", &n) != 1) return 0;
    
    long long target;
    if (scanf("%lld", &target) != 1) return 0;
    
    long long* nums = (long long*)malloc(n * sizeof(long long));
    for (int i = 0; i < n; i++) {
        if (scanf("%lld", &nums[i]) != 1) break;
    }
    
    int r1, r2;
    solve_two_sum(n, target, nums, &r1, &r2);
    
    if (r1 < r2) {
        printf("%d %d\n", r1, r2);
    } else {
        printf("%d %d\n", r2, r1);
    }
    
    free(nums);
    return 0;
}
