#!/usr/bin/env python3
import argparse
import random

# Output format:
#   capacity steps\n
#   then `steps` lines, each an op:
#     A size align      (alloc)
#     C size            (alloc cacheline)
#     M                (mark)
#     R mark            (reset to mark)
#     Z                (reset)


def gen_one(rng: random.Random):
    capacity = rng.randrange(0, 4096)
    steps = rng.randrange(1, 200)

    ops = []
    for _ in range(steps):
        k = rng.randrange(0, 5)
        if k == 0:
            size = rng.randrange(0, 512)
            align = rng.randrange(0, 129)  # include non-pow2 and 0
            ops.append(f"A {size} {align}")
        elif k == 1:
            size = rng.randrange(0, 512)
            ops.append(f"C {size}")
        elif k == 2:
            ops.append("M")
        elif k == 3:
            mark = rng.randrange(0, 4097)
            ops.append(f"R {mark}")
        else:
            ops.append("Z")

    return capacity, steps, ops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=1)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    # The harness expects a single test case per run. We still accept --n for framework compliance.
    capacity, steps, ops = gen_one(rng)
    out_lines = [f"{capacity} {steps}"] + ops
    print("\n".join(out_lines), end="")


if __name__ == "__main__":
    main()
