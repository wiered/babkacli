from sorts.quicksort import quicksort
from sorts.bubblesort import bubblesort
from sorts.stalinsort import stalinsort
from utils.utils import generate_random_array, start_timer

# Создаем массив из 10000 случайных чисел от 0 до 999
arr = generate_random_array(size=10000)

# Используем start_timer для измерения времени работы quicksort
qs_time = start_timer(quicksort, arr)
print(f"Время работы quicksort: {qs_time:.6f} секунд")

# Используем start_timer для измерения времени работы bubblesort
bs_time = start_timer(bubblesort, arr)
print(f"Время работы bubblesort: {bs_time:.6f} секунд")

# Используем start_timer для измерения времени работы stalinsort
ss_time = start_timer(stalinsort, arr)
print(f"Время работы stalinsort: {ss_time:.6f} секунд")

# Вывод разницы во времени
if qs_time < bs_time:
    print(f"Quicksort быстрее bubblesort на {bs_time - qs_time:.6f} секунд")
else:
    print(f"Bubblesort быстрее quicksort на {qs_time - bs_time:.6f} секунд")

if qs_time < ss_time:
    print(f"Quicksort быстрее stalinsort на {ss_time - qs_time:.6f} секунд")
else:
    print(f"Stalinsort быстрее quicksort на {qs_time - ss_time:.6f} секунд")

if bs_time < ss_time:
    print(f"Bubblesort быстрее stalinsort на {ss_time - bs_time:.6f} секунд")
else:
    print(f"Stalinsort быстрее bubblesort на {bs_time - ss_time:.6f} секунд")
