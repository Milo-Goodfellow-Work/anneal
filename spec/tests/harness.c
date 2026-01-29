#include <stdio.h>
#include <string.h>

int main(void) {
    char buf[512];
    while (fgets(buf, sizeof(buf), stdin)) {
        size_t n = strlen(buf);
        while (n && (buf[n-1] == '\n' || buf[n-1] == '\r')) { buf[n-1] = 0; n--; }
        if (n == 0) continue;
        if (strcmp(buf, "NOOP") == 0) puts("OK");
        else puts("ERR");
    }
    return 0;
}
