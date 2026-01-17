import argparse
import random


def gen_case(rng: random.Random, n: int) -> str:
    # Format:
    # n\n
    # then n lines each:
    #   push X
    #   pop
    #   peek
    #   isEmpty
    #   isFull
    ops = []
    for _ in range(n):
        k = rng.randint(0, 4)
        if k == 0:
            x = rng.randint(-2**31, 2**31 - 1)
            ops.append(f"push {x}")
        elif k == 1:
            ops.append("pop")
        elif k == 2:
            ops.append("peek")
        elif k == 3:
            ops.append("isEmpty")
        else:
            ops.append("isFull")
    return "{}\n{}\n".format(n, "\n".join(ops))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    print(gen_case(rng, args.n), end="")


if __name__ == "__main__":
    main()
