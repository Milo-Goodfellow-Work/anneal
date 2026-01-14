#!/usr/bin/env python3
# Input generator for differential testing.
# The Lean harness runs the fixed `main.c` scenario and ignores stdin,
# so we output an empty program here.

def main():
    print(0)

if __name__ == "__main__":
    main()
