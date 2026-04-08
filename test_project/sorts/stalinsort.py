# import logging (removed as logger replaced with print)
logger = logging.getLogger(__name__)

def stalinsort(arr):
    if not arr:
        return []
    result = [arr[0]]
    for x in arr[1:]:
        if x >= result[-1]:
            result.append(x)
    return result

if __name__ == "__main__":
    sample = [64, 34, 25, 12, 22, 11, 90]
    logger.info("Original array: %s", sample)
    logger.info("Sorted array: %s", stalinsort(sample))