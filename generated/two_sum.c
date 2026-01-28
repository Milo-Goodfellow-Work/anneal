#include <stdio.h>
#include <stdlib.h>
#include "two_sum.h"

int compare_indexed(const void *a, const void *b) {
    long long diff = ((IndexedVal *)a)->val - ((IndexedVal *)b)->val;
    if (diff < 0) return -1;
    if (diff > 0) return 1;
    return 0;
}

void solve_two_sum() {
    int n;
    while (scanf("%d", &n) == 1) {
        IndexedVal *nums = malloc(sizeof(IndexedVal) * n);
        for (int i = 0; i < n; i++) {
            if (scanf("%lld", &nums[i].val) != 1) break;
            nums[i].idx = i;
        }
        
        long long target;
        if (scanf("%lld", &target) != 1) {
            free(nums);
            break;
        }
        
        qsort(nums, n, sizeof(IndexedVal), compare_indexed);
        
        int left = 0;
        int right = n - 1;
        int found = 0;
        
        while (left < right) {
            long long sum = nums[left].val + nums[right].val;
            if (sum == target) {
                int i = nums[left].idx;
                int j = nums[right].idx;
                if (i < j) {
                    printf("%d %d\n", i, j);
                } else {
                    printf("%d %d\n", j, i);
                }
                found = 1;
                break;
            } else if (sum < target) {
                left++;
            } else {
                right--;
            }
        }
        
        if (!found) {
            printf("-1 -1\n");
        }
        
        free(nums);
    }
}
