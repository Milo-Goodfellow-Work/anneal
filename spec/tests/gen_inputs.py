import random

def generate_test_case():
    n = random.randint(2, 100)
    nums = [random.randint(-1000, 1000) for _ in range(n)]
    
    # Ensure there is a solution sometimes, or just pick two indices
    if random.choice([True, False]):
        i, j = random.sample(range(n), 2)
        target = nums[i] + nums[j]
    else:
        target = random.randint(-2000, 2000)
        
    print(n)
    for x in nums:
        print(x)
    print(target)

if __name__ == "__main__":
    # Generate 10 test cases
    for _ in range(10):
        generate_test_case()
