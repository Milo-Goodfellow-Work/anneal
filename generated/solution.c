#include <stdio.h>
#include <stdlib.h>
#include "solution.h"

int compareElements(const void* a, const void* b) {
    Element* e1 = (Element*)a;
    Element* e2 = (Element*)b;
    if (e1->val != e2->val) {
        if (e1->val < e2->val) return -1;
        return 1;
    }
    return e1->idx - e2->idx;
}

void solve_two_sum() {
    int n;
    if (scanf("%d", &n) != 1) return;
    Element* elements = (Element*)malloc(n * sizeof(Element));
    for (int i = 0; i < n; i++) {
        if (scanf("%lld", &elements[i].val) != 1) break;
        elements[i].idx = i;
    }
    long long target;
    if (scanf("%lld", &target) != 1) {
        free(elements);
        return;
    }

    qsort(elements, n, sizeof(Element), compareElements);

    int left = 0;
    int right = n - 1;
    while (left < right) {
        long long sum = elements[left].val + elements[right].val;
        if (sum == target) {
            int i1 = elements[left].idx;
            int i2 = elements[right].idx;
            if (i1 < i2) {
                printf("%d %d\n", i1, i2);
            } else {
                printf("%d %d\n", i2, i1);
            }
            free(elements);
            return;
        } else if (sum < target) {
            left++;
        } else {
            right--;
        }
    }

    printf("notfound\n");
    free(elements);
}
