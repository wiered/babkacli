# import logging (removed as logger replaced with print)
logger = logging.getLogger(__name__)

def bubblesort(arr):
    n = len(arr)
    result = arr.copy()
    for i in range(n):
        for j in range(0, n - i - 1):
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
    return result

if __name__ == "__main__":
    sample = [64, 34, 25, 12, 22, 11, 90]
    logger.info("Original array: %s", sample)
    logger.info("Sorted array: %s", bubblesort(sample))