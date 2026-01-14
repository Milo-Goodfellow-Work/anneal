#include "engine.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// --- Memory Management ---

void init_engine(Engine* engine) {
    memset(engine, 0, sizeof(Engine));
    
    // Initialize Free Lists
    engine->free_orders_count = 0;
    for (int i = 0; i < MAX_ORDERS; i++) {
        engine->free_orders[engine->free_orders_count++] = &engine->order_pool[i];
    }
    
    engine->free_levels_count = 0;
    for (int i = 0; i < MAX_LEVELS; i++) {
        engine->free_levels[engine->free_levels_count++] = &engine->level_pool[i];
    }
}

Order* alloc_order(Engine* engine) {
    if (engine->free_orders_count > 0) {
        return engine->free_orders[--engine->free_orders_count];
    }
    return NULL;
}

void free_order(Engine* engine, Order* order) {
    if (engine->free_orders_count < MAX_ORDERS) {
        // Obnoxious: No sanity check if doubly freed for now
        engine->free_orders[engine->free_orders_count++] = order;
    }
}

Level* alloc_level(Engine* engine) {
    if (engine->free_levels_count > 0) {
        Level* l = engine->free_levels[--engine->free_levels_count];
        memset(l, 0, sizeof(Level)); // Reset pointers!
        return l;
    }
    return NULL;
}

void free_level(Engine* engine, Level* level) {
    if (engine->free_levels_count < MAX_LEVELS) {
        engine->free_levels[engine->free_levels_count++] = level;
    }
}

// --- BST Helpers ---

// Validates BST Invariant: Left < Val < Right
Level* find_level(Level* root, uint32_t price) {
    if (!root) return NULL;
    if (price == root->price) return root;
    if (price < root->price) return find_level(root->left, price);
    return find_level(root->right, price);
}

Level* insert_level(Engine* engine, Level** root_ptr, uint32_t price) {
    if (!*root_ptr) {
        // Base case: Create new leaf
        Level* l = alloc_level(engine);
        if (!l) return NULL; // OOM
        l->price = price;
        *root_ptr = l;
        return l;
    }
    
    Level* root = *root_ptr;
    if (price == root->price) return root;
    
    if (price < root->price) {
        return insert_level(engine, &root->left, price);
    } else {
        return insert_level(engine, &root->right, price);
    }
}

// Find min/max for matching
Level* get_best_buy(Level* root) {
    // Best Buy is Highest Price -> Rightmost
    if (!root) return NULL;
    while (root->right) root = root->right;
    return root;
}

Level* get_best_sell(Level* root) {
    // Best Sell is Lowest Price -> Leftmost
    if (!root) return NULL;
    while (root->left) root = root->left;
    return root;
}

// Remove empty level from BST
// This is the "Obnoxious" part: BST Deletion
// Simplified: we only remove if we are matching, and typically we match from edge.
// Implementing full remove is painful. Let's do lazy removal: 
// The level stays but `orders_head` is NULL. 
// Actually, verified code should probably clean up.
// Let's implement full removal of min/max node which is easier than generic remove.

void remove_best_buy_node(Engine* engine, Level** root_ptr) {
    if (!*root_ptr) return;
    
    Level* root = *root_ptr;
    
    if (root->right) {
        // Not the max, recurse right
        remove_best_buy_node(engine, &root->right);
    } else {
        // This IS the max node
        // Since it has no right child, we replace it with left child (orphan adoption)
        *root_ptr = root->left;
        free_level(engine, root);
    }
}

void remove_best_sell_node(Engine* engine, Level** root_ptr) {
    if (!*root_ptr) return;
    
    Level* root = *root_ptr;
    
    if (root->left) {
        // Not the min, recurse left
        remove_best_sell_node(engine, &root->left);
    } else {
        // This IS the min node
        *root_ptr = root->right;
        free_level(engine, root);
    }
}


// --- Queue Helpers ---

void enqueue_order(Level* level, Order* order) {
    order->next = NULL;
    order->prev = level->orders_tail;
    
    if (level->orders_tail) {
        level->orders_tail->next = order;
    } else {
        level->orders_head = order;
    }
    level->orders_tail = order;
}

Order* dequeue_order(Level* level) {
    if (!level->orders_head) return NULL;
    
    Order* o = level->orders_head;
    level->orders_head = o->next;
    
    if (level->orders_head) {
        level->orders_head->prev = NULL;
    } else {
        level->orders_tail = NULL;
    }
    
    o->next = NULL;
    o->prev = NULL;
    return o;
}

// --- Logic ---

void submit_order(Engine* engine, uint32_t id, uint32_t price, uint32_t quantity, Side side) {
    Order* o = alloc_order(engine);
    if (!o) return; // Drop on OOM
    
    o->id = id;
    o->price = price;
    o->quantity = quantity;
    o->side = side;
    
    Level** root_ptr = (side == SIDE_BUY) ? &engine->book.buy_levels : &engine->book.sell_levels;
    Level* lvl = insert_level(engine, root_ptr, price);
    
    if (lvl) {
        enqueue_order(lvl, o);
    } else {
        free_order(engine, o); // Failed to get level
    }
}

void match_orders(Engine* engine) {
    while (true) {
        Level* best_buy = get_best_buy(engine->book.buy_levels);
        Level* best_sell = get_best_sell(engine->book.sell_levels);
        
        if (!best_buy || !best_sell) break;
        
        // Spread Check: Buy >= Sell to match
        if (best_buy->price < best_sell->price) break;
        
        // Match Head Orders
        Order* buy_order = best_buy->orders_head;
        Order* sell_order = best_sell->orders_head;
        
        // Execute Match
        uint32_t qty = (buy_order->quantity < sell_order->quantity) ? buy_order->quantity : sell_order->quantity;
        
        printf("MATCH: Buy %u @ %u matches Sell %u @ %u for %u qty\n", 
               buy_order->id, buy_order->price, sell_order->id, sell_order->price, qty);
        
        buy_order->quantity -= qty;
        sell_order->quantity -= qty;
        
        // Cleanup Filled Orders
        if (buy_order->quantity == 0) {
            Order* o = dequeue_order(best_buy);
            free_order(engine, o);
        }
        if (sell_order->quantity == 0) {
           Order* o = dequeue_order(best_sell);
           free_order(engine, o);
        }
        
        // Cleanup Empty Levels
        if (!best_buy->orders_head) {
            remove_best_buy_node(engine, &engine->book.buy_levels);
        }
        if (!best_sell->orders_head) {
            remove_best_sell_node(engine, &engine->book.sell_levels);
        }
    }
}
