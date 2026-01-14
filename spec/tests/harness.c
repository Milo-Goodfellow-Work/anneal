#include <stdio.h>
#include <stdint.h>

#include "../../examples/order_engine/engine.h"

int main(void) {
    (void)getchar; // silence unused warnings in some compilers

    Engine engine;
    init_engine(&engine);

    // Same scenario as examples/order_engine/main.c
    submit_order(&engine, 1, 100, 100, SIDE_SELL);
    submit_order(&engine, 2, 101, 50, SIDE_SELL);
    submit_order(&engine, 3, 101, 50, SIDE_BUY);
    match_orders(&engine);
    submit_order(&engine, 4, 102, 150, SIDE_BUY);
    match_orders(&engine);

    return 0;
}
