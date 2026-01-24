import random
import sys

def generate_inputs(num_lines=1000):
    ops = ["inc", "get"]
    with open("spec/tests/input.txt", "w") as f:
        for _ in range(num_lines):
            # Heavily favor increment to build up value
            if random.random() < 0.8:
                f.write("inc\n")
            else:
                f.write("get\n")

if __name__ == "__main__":
    generate_inputs()
