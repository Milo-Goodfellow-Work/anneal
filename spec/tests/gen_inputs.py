import random
import sys

def generate_test_case():
    n = random.randint(2, 100)
    nums = []
    seen = set()
    while len(nums) < n:
        x = random.randint(-1000, 1000)
        if x not in seen:
            nums.append(x)
            seen.add(x)
            
    i, j = random.sample(range(n), 2)
    target = nums[i] + nums[j]
    
    print(n)
    print(target)
    print(" ".join(map(str, nums)))

if __name__ == "__main__":
    generate_test_case()
