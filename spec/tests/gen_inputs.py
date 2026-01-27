import random
import os

def generate_case(n, max_val, has_solution=True):
    nums = [random.randint(-max_val, max_val) for _ in range(n)]
    if has_solution:
        i, j = random.sample(range(n), 2)
        target = nums[i] + nums[j]
    else:
        target = random.randint(-2*max_val, 2*max_val)
    return n, nums, target

def main():
    os.makedirs("tests", exist_ok=True)
    for i in range(10):
        n = random.randint(2, 100)
        has_solution = i < 8
        n, nums, target = generate_case(n, 1000000, has_solution)
        with open(f"tests/input_{i}.txt", "w") as f:
            f.write(f"{n}\n")
            for x in nums:
                f.write(f"{x}\n")
            f.write(f"{target}\n")

if __name__ == "__main__":
    main()
