#!/usr/bin/env python3
import argparse
import random

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--seed', type=int, required=True)
  ap.add_argument('--n', type=int, required=True)
  args = ap.parse_args()

  rng = random.Random(args.seed)

  cap = rng.choice([0, 64, 128, 256, 1024, 4096])
  steps = max(1, args.n)
  print(f"{cap} {steps}")

  for _ in range(steps):
    op = rng.choices(['a','p','o','r'], weights=[70, 10, 10, 10])[0]
    if op == 'a':
      n = rng.choice([0, 1, 7, 63, 64, 65, rng.randint(0, 256)])
      print(f"a {n}")
    else:
      print(op)

if __name__ == '__main__':
  main()
