#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "arena.h"

int main() {
    char line[256];
    Arena arena = {0};
    uint8_t* buffer = NULL;

    while (fgets(line, sizeof(line), stdin)) {
        // Remove trailing newline
        line[strcspn(line, "\n")] = 0;
        
        if (line[0] == 0) continue;

        char cmd[32];
        size_t arg = 0;
        // Check input format
        int items = sscanf(line, "%s %zu", cmd, &arg);

        if (strcmp(cmd, "init") == 0) {
            if (buffer) free(buffer);
            buffer = malloc(arg);
            Arena_Init(&arena, buffer, arg);
            printf("init ok\n");
        } else if (strcmp(cmd, "alloc") == 0) {
            size_t res = Arena_Alloc(&arena, arg);
            if (res == SIZE_MAX) {
                printf("alloc fail\n");
            } else {
                printf("alloc %zu\n", res);
            }
        } else if (strcmp(cmd, "getpos") == 0) {
            size_t pos = Arena_GetPos(&arena);
            printf("pos %zu\n", pos);
        } else if (strcmp(cmd, "setpos") == 0) {
            Arena_SetPos(&arena, arg);
            printf("setpos ok\n");
        } else if (strcmp(cmd, "reset") == 0) {
            Arena_Reset(&arena);
            printf("reset ok\n");
        }
    }

    if (buffer) free(buffer);
    return 0;
}
