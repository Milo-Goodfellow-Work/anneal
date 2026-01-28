#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int key;
    int value;
    int occupied;
} HashEntry;

typedef struct {
    HashEntry* entries;
    int size;
} HashTable;

unsigned int hash(int key, int size) {
    unsigned int h = (unsigned int)key;
    return h % size;
}

void insert(HashTable* table, int key, int value) {
    unsigned int h = hash(key, table->size);
    while (table->entries[h].occupied) {
        h = (h + 1) % table->size;
    }
    table->entries[h].key = key;
    table->entries[h].value = value;
    table->entries[h].occupied = 1;
}

int find(HashTable* table, int key) {
    unsigned int h = hash(key, table->size);
    int start = h;
    while (table->entries[h].occupied) {
        if (table->entries[h].key == key) {
            return table->entries[h].value;
        }
        h = (h + 1) % table->size;
        if (h == start) break;
    }
    return -1;
}

void solve_two_sum(int* nums, int n, int target) {
    int table_size = n * 2 + 1;
    HashTable table;
    table.size = table_size;
    table.entries = (HashEntry*)calloc(table_size, sizeof(HashEntry));

    for (int i = 0; i < n; i++) {
        int complement = target - nums[i];
        int res = find(&table, complement);
        if (res != -1) {
            printf("%d %d\n", res, i);
            free(table.entries);
            return;
        }
        insert(&table, nums[i], i);
    }

    printf("-1 -1\n");
    free(table.entries);
}

int main() {
    int n;
    while (scanf("%d", &n) == 1) {
        int target;
        if (scanf("%d", &target) != 1) break;
        int* nums = (int*)malloc(n * sizeof(int));
        for (int i = 0; i < n; i++) {
            if (scanf("%d", &nums[i]) != 1) break;
        }
        solve_two_sum(nums, n, target);
        free(nums);
    }
    return 0;
}
