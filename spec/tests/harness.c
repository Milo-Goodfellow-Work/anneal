#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>

#include "../../examples/order_engine/engine.h"

static uint32_t parse_u32_tok(const char *s) {
    if (s == NULL || *s == '\0') return 0;
    // accept only digits; otherwise 0
    for (const char *p = s; *p; p++) {
        if (*p < '0' || *p > '9') return 0;
    }
    unsigned long long v = strtoull(s, NULL, 10);
    return (uint32_t)v;
}

static Side parse_side_tok(const char *s) {
    if (s && strcmp(s, "B") == 0) return SIDE_BUY;
    return SIDE_SELL;
}

int main(void) {
    Engine engine;
    int inited = 0;

    char line[512];
    while (fgets(line, sizeof(line), stdin)) {
        // tokenize
        char *toks[16];
        int nt = 0;
        char *save = NULL;
        for (char *tok = strtok_r(line, " \t\r\n", &save);
             tok != NULL && nt < 16;
             tok = strtok_r(NULL, " \t\r\n", &save)) {
            toks[nt++] = tok;
        }
        if (nt == 0) continue;

        if (strcmp(toks[0], "INIT") == 0 && nt == 1) {
            init_engine(&engine);
            inited = 1;
            printf("OK\n");
            continue;
        }

        if (!inited) {
            init_engine(&engine);
            inited = 1;
        }

        if (strcmp(toks[0], "MATCH") == 0 && nt == 1) {
            match_orders(&engine);
            printf("OK\n");
        } else if (strcmp(toks[0], "SUBMIT") == 0 && nt >= 5) {
            uint32_t id = parse_u32_tok(toks[1]);
            uint32_t price = parse_u32_tok(toks[2]);
            uint32_t qty = parse_u32_tok(toks[3]);
            Side side = parse_side_tok(toks[4]);
            submit_order(&engine, id, price, qty, side);
            printf("OK\n");
        } else {
            printf("ERR\n");
        }
    }

    return 0;
}
