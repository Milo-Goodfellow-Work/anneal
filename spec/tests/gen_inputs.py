import argparse
import random

# Text format:
#   cap cacheLine steps\n
# Each step is one line:
#   A n        (alloc n bytes)
#   M          (mark)
#   R idx      (reset to marker index)
#   C          (clear)


def gen_one(rng: random.Random) -> str:
    cap = rng.randint(1, 4096)
    cache_line = 1 << rng.randint(0, 6)  # 1..64
    steps = rng.randint(1, 200)

    out = [f"{cap} {cache_line} {steps}\n"]
    marks = 0
    for _ in range(steps):
        op = rng.choices(["A", "M", "R", "C"], weights=[70, 10, 10, 10])[0]
        if op == "A":
            n = rng.randint(0, 512)
            out.append(f"A {n}\n")
        elif op == "M":
            out.append("M\n")
            marks += 1
        elif op == "R":
            if marks == 0:
                out.append("C\n")
            else:
                idx = rng.randint(0, marks - 1)
                out.append(f"R {idx}\n")
        else:
            out.append("C\n")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    # Differential framework expects exactly one test case per invocation.
    # We ignore --n except to advance RNG deterministically.
    for _ in range(max(0, args.n - 1)):
        _ = gen_one(rng)
    print(gen_one(rng), end="")


if __name__ == "__main__":
    main()
