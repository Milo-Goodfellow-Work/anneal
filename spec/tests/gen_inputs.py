#!/usr/bin/env python3
import argparse
import random

def gen(seed: int, n: int):
    rng = random.Random(seed)
    lines = []

    # Always start with INIT to reset state.
    lines.append("INIT")

    # Hand-crafted edge cases early.
    lines += [
        "SUB 1 0 0 B",           # zero qty
        "SUB 2 0 1 S",           # price 0
        "MAT",                   # try matching
        "SUB 3 1 1 S",
        "SUB 4 1 1 B",           # exact cross
        "MAT",
        "SUB 5 4294967295 1 B",  # max u32 price
        "SUB 6 4294967295 1 S",
        "MAT",
    ]

    next_id = 10

    def rand_u32():
        # bias toward edge values
        r = rng.randrange(100)
        if r < 10:
            return 0
        if r < 20:
            return 1
        if r < 30:
            return 2
        if r < 40:
            return 4294967295
        if r < 50:
            return 4294967294
        return rng.randrange(0, 2**32)

    def rand_side():
        return 'B' if rng.randrange(2) == 0 else 'S'

    # Generate adversarial sequences.
    # We focus on submit+match since cancel/verify not implemented in Lean engine.
    while len(lines) < n:
        op = rng.randrange(100)
        if op < 65:
            oid = rng.randrange(1, 2000) if rng.randrange(10) == 0 else next_id
            if oid == next_id:
                next_id += 1
            price = rand_u32()
            qty = rand_u32()
            side = rand_side()
            lines.append(f"SUB {oid} {price} {qty} {side}")
        else:
            # match burst: include consecutive MAT to stress empty level deletion
            k = 1 if rng.randrange(4) else rng.randrange(1, 6)
            for _ in range(k):
                lines.append("MAT")

        # occasional re-init to explore fresh states & pool reuse
        if rng.randrange(200) == 0:
            lines.append("INIT")

    # Ensure non-empty lines
    return [ln for ln in lines if ln.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--n', type=int, required=True)
    args = ap.parse_args()

    lines = gen(args.seed, args.n)
    for ln in lines:
        print(ln)

if __name__ == '__main__':
    main()
