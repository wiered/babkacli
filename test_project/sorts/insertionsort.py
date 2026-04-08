# import logging (removed as logger replaced with print)
logger = logging.getLogger(__name__)

def insertionsort(arr):
    result = arr.copy()
    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result

if __name__ == "__main__":
    sample = [64, 34, 25, 12, 22, 11, 90]
    logger.info("Original array: %s", sample)
    logger.info("Sorted array: %s", insertionsort(sample))