#ifndef ENGINE_H
#define ENGINE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

// --- Constants ---
#define MAX_ORDERS 1024
#define MAX_LEVELS 256

// --- Types ---

typedef enum {
    SIDE_BUY,
    SIDE_SELL
} Side;

// Order Node for Doubly Linked List
typedef struct Order {
    uint32_t id;
    uint32_t price;
    uint32_t quantity;
    Side side;
    
    // DLL Pointers
    struct Order* next;
    struct Order* prev;
} Order;

// Price Level Node for BST
typedef struct Level {
    uint32_t price;
    
    // Queue Pointers (Head/Tail of DLL)
    Order* orders_head;
    Order* orders_tail;
    
    // BST Pointers
    struct Level* left;
    struct Level* right;
} Level;

// Order Book Root
typedef struct OrderBook {
    Level* buy_levels;  // BST Root for Bids
    Level* sell_levels; // BST Root for Asks
} OrderBook;

// Memory Pool
typedef struct Engine {
    // Pools
    Order order_pool[MAX_ORDERS];
    Level level_pool[MAX_LEVELS];
    
    // Free Lists (Stack-based)
    Order* free_orders[MAX_ORDERS];
    int free_orders_count;
    
    Level* free_levels[MAX_LEVELS];
    int free_levels_count;
    
    // The Book
    OrderBook book;
} Engine;

// --- API ---

// Memory Management
void init_engine(Engine* engine);
Order* alloc_order(Engine* engine);
void free_order(Engine* engine, Order* order);
Level* alloc_level(Engine* engine);
void free_level(Engine* engine, Level* level);

// Logic
void submit_order(Engine* engine, uint32_t id, uint32_t price, uint32_t quantity, Side side);
void cancel_order(Engine* engine, uint32_t id); // Simplified: Assume ID lookup is handled externally or linear scan
void match_orders(Engine* engine);

// Validation / Debug
bool verify_book_integrity(Engine* engine);

#endif
