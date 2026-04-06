import random
import time

def generate_random_array(size=1000, lower_bound=0, upper_bound=999):
    """Генерирует массив случайных чисел заданного размера и диапазона."""
    return [random.randint(lower_bound, upper_bound) for _ in range(size)]


def start_timer(sort_function, arr):
    """Принимает функцию сортировки и массив, возвращает время выполнения сортировки."""
    start = time.time()
    sort_function(arr)
    end = time.time()
    return end - start
