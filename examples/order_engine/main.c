#include "engine.h"
#include <stdio.h>

int main() {
    printf("Initializing Engine...\n");
    Engine engine;
    init_engine(&engine);
    
    printf("Submitting Sell Orders...\n");
    // Sell 100 @ 100, 50 @ 101
    submit_order(&engine, 1, 100, 100, SIDE_SELL);
    submit_order(&engine, 2, 101, 50, SIDE_SELL);
    
    printf("Submitting Buy Orders...\n");
    // Buy 50 @ 101 (Should match Sell #1, price improvement?)
    // In this engine, matches at resting price (Sell #1 @ 100)
    submit_order(&engine, 3, 101, 50, SIDE_BUY);
    
    printf("Matching...\n");
    match_orders(&engine);
    
    printf("Submitting Aggressive Buy...\n");
    // Buy 150 @ 102. Should clean up rest of #1 and all of #2
    submit_order(&engine, 4, 102, 150, SIDE_BUY);
    
    match_orders(&engine);
    
    printf("Done.\n");
    return 0;
}
