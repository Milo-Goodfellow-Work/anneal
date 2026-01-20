import random
import sys
import argparse

def gen_inputs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=100)
    args = parser.parse_args()

    random.seed(args.seed)
    
    capacity = 1024 * 1024 # 1MB
    print(f"init {capacity}")
    
    ops = ["alloc", "getpos", "setpos", "reset"]
    
    for _ in range(args.n):
        op = random.choice(ops)
        
        if op == "alloc":
            size = random.randint(1, 128)
            print(f"alloc {size}")
        elif op == "getpos":
            print("getpos")
        elif op == "setpos":
            # Just set to 0 or random pos within capacity
            val = 0
            if random.random() < 0.5:
                val = random.randint(0, capacity)
            print(f"setpos {val}")
        elif op == "reset":
            print("reset")

if __name__ == "__main__":
    gen_inputs()
