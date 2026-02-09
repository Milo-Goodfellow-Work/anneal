#!/usr/bin/env python3
import argparse, random

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--n', type=int, required=True)
    args = ap.parse_args()
    random.seed(args.seed)
    for _ in range(args.n):
        print('NOOP')

if __name__ == '__main__':
    main()
