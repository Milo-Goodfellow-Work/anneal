#!/usr/bin/env python3
import argparse
import random

# Runner contract:
# - must accept: --seed <int> and --n <int>
# - prints N cases separated by a line containing only: ---
#
# Safety hardening goals:
# - adversarial sequences for structural mutations
# - whitespace corner cases
# - numeric corner cases (0, U32_MAX), id collisions
#
# IMPORTANT: Keep per-case output sizes manageable. The differential runner
# compares full stdout; generating huge match logs can dominate runtime/memory.

U32_MAX = 2**32 - 1


def ws_variants(rng: random.Random) -> tuple[str, str]:
    sep = rng.choice([" ", "  ", "\t", " \t", "\t "])
    end = rng.choice(["", " ", "  ", "\t", " \t"])
    return sep, end


def emit_cmd(rng: random.Random, toks: list[str]) -> str:
    sep, end = ws_variants(rng)
    # add CR sometimes
    cr = "\r" if rng.random() < 0.15 else ""
    return sep.join(toks) + end + cr


def gen_targeted_sequences(rng: random.Random) -> list[str]:
    lines: list[str] = []

    # INIT + modest ladders (avoid enormous match logs)
    lines.append(emit_cmd(rng, ["INIT"]))
    base_id = rng.randrange(1, 5000)

    # 12 sells ascending
    for k in range(12):
        oid = (base_id + k) & U32_MAX
        price = (100 + k) & U32_MAX
        qty = rng.choice([0, 1, 2, 10, 50, 100, U32_MAX])
        lines.append(emit_cmd(rng, ["SUBMIT", str(oid), str(price), str(qty), "S"]))

    # 12 buys descending (crossing)
    for k in range(12):
        oid = (base_id + 100 + k) & U32_MAX
        price = (120 - k) & U32_MAX
        qty = rng.choice([0, 1, 2, 10, 75, 150, U32_MAX])
        lines.append(emit_cmd(rng, ["SUBMIT", str(oid), str(price), str(qty), "B"]))

    # Drain with a few MATCH calls
    for _ in range(6):
        lines.append(emit_cmd(rng, ["MATCH"]))

    # ID collisions
    lines.append(emit_cmd(rng, ["INIT"]))
    for _ in range(10):
        oid = 42
        price = rng.choice([0, 1, 100, 101, U32_MAX])
        qty = rng.choice([0, 1, 10, 100, U32_MAX])
        side = rng.choice(["B", "S"])
        lines.append(emit_cmd(rng, ["SUBMIT", str(oid), str(price), str(qty), side]))
    for _ in range(4):
        lines.append(emit_cmd(rng, ["MATCH"]))

    # malformed commands
    lines.append(emit_cmd(rng, ["SUBMIT"]))
    lines.append(emit_cmd(rng, ["NOPE"]))

    return lines


def gen_random_ops(rng: random.Random, m: int) -> list[str]:
    lines: list[str] = []

    special_u32 = [0, 1, 2, 3, 4, 10, 99, 100, 101, 102, U32_MAX]
    special_price = [0, 1, 50, 99, 100, 101, 102, 10_000, U32_MAX]
    special_qty = [0, 1, 2, 49, 50, 51, 100, 150, U32_MAX]

    for _ in range(m):
        p = rng.random()
        if p < 0.60:
            idv = rng.choice(special_u32) if rng.random() < 0.55 else rng.getrandbits(32)
            price = rng.choice(special_price) if rng.random() < 0.60 else rng.getrandbits(32)
            qty = rng.choice(special_qty) if rng.random() < 0.75 else rng.getrandbits(32)
            side = "B" if rng.random() < 0.5 else "S"
            lines.append(emit_cmd(rng, ["SUBMIT", str(idv), str(price), str(qty), side]))
        elif p < 0.90:
            lines.append(emit_cmd(rng, ["MATCH"]))
        elif p < 0.96:
            lines.append(emit_cmd(rng, ["INIT"]))
        else:
            # malformed
            kind = rng.randint(0, 5)
            if kind == 0:
                lines.append(emit_cmd(rng, ["SUBMIT", "1", "2", "3"]))
            elif kind == 1:
                lines.append(emit_cmd(rng, ["SUBMIT", "x", "y", "z", "B"]))
            elif kind == 2:
                lines.append(emit_cmd(rng, ["MATCH", "EXTRA"]))
            elif kind == 3:
                lines.append(emit_cmd(rng, ["SUBMIT", "1", "2", "3", "B", "EXTRA"]))
            else:
                lines.append(emit_cmd(rng, ["NOPE"]))

    return lines


def generate_case(rng: random.Random) -> str:
    lines: list[str] = []
    if rng.random() < 0.8:
        lines.extend(gen_targeted_sequences(rng))

    ops = rng.randint(20, 80)
    lines.extend(gen_random_ops(rng, ops))

    text = "\n".join(lines)
    # sometimes omit trailing newline
    if rng.random() < 0.6:
        text += "\n"
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    for i in range(args.n):
        sub = random.Random(rng.getrandbits(64))
        print(generate_case(sub), end="")
        if i != args.n - 1:
            print("\n---\n", end="")


if __name__ == "__main__":
    main()
