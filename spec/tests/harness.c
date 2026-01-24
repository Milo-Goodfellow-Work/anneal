#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "../../generated/test_project/counter.h"

int main() {
    Counter c = Counter_init();
    char line[1024];

    while (fgets(line, sizeof(line), stdin)) {
        // Remove newline
        line[strcspn(line, "\n")] = 0;

        if (strcmp(line, "inc") == 0) {
            c = Counter_increment(c);
        } else if (strcmp(line, "get") == 0) {
            printf("%u\n", Counter_get(c));
        }
    }
    return 0;
}
