# import logging (removed as logger replaced with print)
logger = logging.getLogger(__name__)

def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

if __name__ == "__main__":
    sample = [64, 34, 25, 12, 22, 11, 90]
    logger.info("Original array: %s", sample)
    logger.info("Sorted array: %s", quicksort(sample))