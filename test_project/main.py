# import logging (removed as logger replaced with print)
logger = logging.getLogger(__name__)

from sorts.quicksort import quicksort
from sorts.bubblesort import bubblesort
from sorts.stalinsort import stalinsort
from sorts.insertionsort import insertionsort
from utils.utils import generate_random_array, start_timer

# Создаем массив из 10000 случайных чисел от 0 до 999
arr = generate_random_array(size=10000)

# Используем start_timer для измерения времени работы quicksort
qs_time = start_timer(quicksort, arr)
logger.info(f"Время работы quicksort: {qs_time:.6f} секунд")

# Используем start_timer для измерения времени работы bubblesort
bs_time = start_timer(bubblesort, arr)
logger.info(f"Время работы bubblesort: {bs_time:.6f} секунд")

# Используем start_timer для измерения времени работы stalinsort
ss_time = start_timer(stalinsort, arr)
logger.info(f"Время работы stalinsort: {ss_time:.6f} секунд")

# Используем start_timer для измерения времени работы insertionsort
is_time = start_timer(insertionsort, arr)
logger.info(f"Время работы insertionsort: {is_time:.6f} секунд")

# Вывод разницы во времени
if qs_time < bs_time:
    logger.info(f"Quicksort быстрее bubblesort на {bs_time - qs_time:.6f} секунд")
else:
    logger.info(f"Bubblesort быстрее quicksort на {qs_time - bs_time:.6f} секунд")

if qs_time < ss_time:
    logger.info(f"Quicksort быстрее stalinsort на {ss_time - qs_time:.6f} секунд")
else:
    logger.info(f"Stalinsort быстрее quicksort на {qs_time - ss_time:.6f} секунд")

if bs_time < ss_time:
    logger.info(f"Bubblesort быстрее stalinsort на {ss_time - bs_time:.6f} секунд")
else:
    logger.info(f"Stalinsort быстрее bubblesort на {bs_time - ss_time:.6f} секунд")

if qs_time < is_time:
    logger.info(f"Quicksort быстрее insertionsort на {is_time - qs_time:.6f} секунд")
else:
    logger.info(f"Insertionsort быстрее quicksort на {qs_time - is_time:.6f} секунд")

if bs_time < is_time:
    logger.info(f"Bubblesort быстрее insertionsort на {is_time - bs_time:.6f} секунд")
else:
    logger.info(f"Insertionsort быстрее bubblesort на {bs_time - is_time:.6f} секунд")

if ss_time < is_time:
    logger.info(f"Stalinsort быстрее insertionsort на {is_time - ss_time:.6f} секунд")
else:
    logger.info(f"Insertionsort быстрее stalinsort на {ss_time - is_time:.6f} секунд")