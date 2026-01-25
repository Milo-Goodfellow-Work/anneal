import random
import sys

def generate():
    n = random.randint(2, 100)
    target = random.randint(-1000, 1000)
    nums = [random.randint(-1000, 1000) for _ in range(n)]
    
    # Occasionally ensure there is a solution
    if random.random() < 0.5:
        idx1 = random.randint(0, n-1)
        idx2 = random.randint(0, n-1)
        while idx1 == idx2:
            idx2 = random.randint(0, n-1)
        target = nums[idx1] + nums[idx2]

    print(f"{n} {target}")
    print(" ".join(map(str, nums)))

if __name__ == "__main__":
    generate()
