#ifndef SOLUTION_H
#define SOLUTION_H

typedef struct {
    long long val;
    int idx;
} Element;

int compareElements(const void* a, const void* b);
void solve_two_sum();

#endif
