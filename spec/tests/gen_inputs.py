import random

def generate_test():
    n = random.randint(2, 50)
    target = random.randint(-100, 100)
    arr = [random.randint(-100, 100) for _ in range(n)]
    
    # Occasionally force a solution
    if random.random() < 0.5:
        i = random.randint(0, n - 2)
        j = random.randint(i + 1, n - 1)
        arr[i] = random.randint(-50, 50)
        arr[j] = target - arr[i]

    print(f"{target} {n}")
    print(" ".join(map(str, arr)))

if __name__ == "__main__":
    generate_test()
