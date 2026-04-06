import random
from sorts.bubblesort import bubblesort
from sorts.insertionsort import insertionsort
from sorts.quicksort import quicksort
from sorts.stalinsort import stalinsort

# List of sorting functions
sorting_algorithms = [bubblesort, insertionsort, quicksort, stalinsort]

# Function to check if a list is sorted
def is_sorted(arr):
    return all(arr[i] <= arr[i + 1] for i in range(len(arr) - 1))

# Generate random lists and test sorting algorithms
for sort_func in sorting_algorithms:
    print(f"Testing {sort_func.__name__}...")
    for i in range(10):
        test_list = [random.randint(0, 1000) for _ in range(100)]
        sorted_list = sort_func(test_list)
        if is_sorted(sorted_list):
            print(f"Test {i + 1}: PASS")
        else:
            print(f"Test {i + 1}: FAIL")
    print()