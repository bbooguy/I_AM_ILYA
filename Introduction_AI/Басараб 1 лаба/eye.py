from itertools import product, combinations
from pathlib import Path
import csv
import matplotlib.pyplot as plt


# -------------------------------------------------
# Основные параметры
# -------------------------------------------------

LEARNING_RATE = 0.3
MAX_EPOCHS = 5000

# Папка, в которой находится этот .py файл
BASE_DIR = Path(__file__).resolve().parent


# -------------------------------------------------
# Булева функция варианта 7
#
# F = NOT(x1 OR x2) OR x3 OR x4
# -------------------------------------------------

def boolean_func(x1, x2, x3, x4):
    return int((not (x1 or x2)) or x3 or x4)


# -------------------------------------------------
# Построение таблицы истинности
# -------------------------------------------------

def make_truth_table():
    table = []

    for x1, x2, x3, x4 in product([0, 1], repeat=4):

        target = boolean_func(
            x1,
            x2,
            x3,
            x4
        )

        # x0 = 1 — постоянный вход смещения
        inputs = [1, x1, x2, x3, x4]

        table.append((inputs, target))

    return table


# -------------------------------------------------
# Вычисление net
#
# net = w0*x0 + w1*x1 + ... + w4*x4
# -------------------------------------------------

def calculate_net(weights, inputs):

    net = 0

    for weight, x in zip(weights, inputs):
        net += weight * x

    return net


# -------------------------------------------------
# Функции активации
# -------------------------------------------------

def activation(net, function_number):

    # ФА №1 — пороговая
    if function_number == 1:

        if net >= 0:
            return 1
        else:
            return 0

    # ФА №2 — рациональная сигмоидная
    elif function_number == 2:

        return 0.5 * (
            net / (1 + abs(net)) + 1
        )

    else:
        raise ValueError(
            "Номер функции активации должен быть 1 или 2"
        )


# -------------------------------------------------
# Производная функции активации
# -------------------------------------------------

def activation_derivative(net, function_number):

    # Для ФА №1 по условию лабораторной
    # используется значение производной 1
    if function_number == 1:
        return 1

    # Производная ФА №2
    elif function_number == 2:

        return 1 / (
            2 * (1 + abs(net)) ** 2
        )

    else:
        raise ValueError(
            "Номер функции активации должен быть 1 или 2"
        )


# -------------------------------------------------
# Перевод выхода нейрона в бинарный класс
# -------------------------------------------------

def to_class(output, function_number):

    # ФА №1 уже возвращает 0 или 1
    if function_number == 1:
        return int(output)

    # Для ФА №2 используется порог 0.5
    if output >= 0.5:
        return 1
    else:
        return 0


# -------------------------------------------------
# Проверка выбранной обучающей выборки
# -------------------------------------------------

def training_set_is_correct(
    table,
    indexes,
    weights,
    function_number
):

    for index in indexes:

        inputs, target = table[index]

        net = calculate_net(
            weights,
            inputs
        )

        output = activation(
            net,
            function_number
        )

        prediction = to_class(
            output,
            function_number
        )

        if prediction != target:
            return False

    return True


# -------------------------------------------------
# Обучение нейронной сети
# -------------------------------------------------

def train_network(
    table,
    train_indexes,
    function_number
):

    # Все веса изначально равны нулю
    weights = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0
    ]

    # Здесь будет храниться история эпох
    history = []

    for epoch in range(1, MAX_EPOCHS + 1):

        epoch_error = 0

        for index in train_indexes:

            inputs, target = table[index]

            # Вычисляем net
            net = calculate_net(
                weights,
                inputs
            )

            # Получаем выход нейрона
            output = activation(
                net,
                function_number
            )

            # Ошибка
            error = target - output

            # Добавляем квадрат ошибки
            epoch_error += error ** 2

            # Производная функции активации
            derivative = activation_derivative(
                net,
                function_number
            )

            # Корректируем каждый вес
            for j in range(len(weights)):

                weights[j] += (
                    LEARNING_RATE
                    * error
                    * derivative
                    * inputs[j]
                )

        # После окончания эпохи сохраняем
        # номер эпохи, веса и E(k)
        history.append({
            "epoch": epoch,
            "w0": weights[0],
            "w1": weights[1],
            "w2": weights[2],
            "w3": weights[3],
            "w4": weights[4],
            "error": epoch_error
        })

        # Если вся обучающая выборка
        # классифицируется правильно,
        # обучение прекращаем
        if training_set_is_correct(
            table,
            train_indexes,
            weights,
            function_number
        ):
            break

    return weights, history


# -------------------------------------------------
# Сохранение истории обучения в CSV
# -------------------------------------------------

def save_training_history(
    history,
    function_number,
    prefix=""
):

    filename = (
        f"{prefix}teach_process_func_"
        f"{function_number}.csv"
    )

    filepath = BASE_DIR / filename

    with open(
        filepath,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(
            file,
            delimiter=";"
        )

        # Заголовок таблицы
        writer.writerow([
            "epoch",
            "w0",
            "w1",
            "w2",
            "w3",
            "w4",
            "E(k)"
        ])

        # Данные всех эпох
        for row in history:

            writer.writerow([
                row["epoch"],
                row["w0"],
                row["w1"],
                row["w2"],
                row["w3"],
                row["w4"],
                row["error"]
            ])

    print(
        "История обучения сохранена:",
        filepath
    )


# -------------------------------------------------
# Получение результатов проверки
# -------------------------------------------------

def get_test_results(
    table,
    weights,
    function_number
):

    results = []

    all_correct = True

    for inputs, target in table:

        net = calculate_net(
            weights,
            inputs
        )

        output = activation(
            net,
            function_number
        )

        prediction = to_class(
            output,
            function_number
        )

        if prediction != target:
            all_correct = False

        results.append({
            "x1": inputs[1],
            "x2": inputs[2],
            "x3": inputs[3],
            "x4": inputs[4],
            "target": target,
            "net": net,
            "output": output,
            "class": prediction
        })

    return all_correct, results


# -------------------------------------------------
# Сохранение результатов проверки в CSV
# -------------------------------------------------

def save_test_results(
    results,
    function_number,
    prefix=""
):

    filename = (
        f"{prefix}test_result_func_"
        f"{function_number}.csv"
    )

    filepath = BASE_DIR / filename

    with open(
        filepath,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(
            file,
            delimiter=";"
        )

        writer.writerow([
            "x1",
            "x2",
            "x3",
            "x4",
            "target",
            "net",
            "output",
            "class"
        ])

        for row in results:

            writer.writerow([
                row["x1"],
                row["x2"],
                row["x3"],
                row["x4"],
                row["target"],
                row["net"],
                row["output"],
                row["class"]
            ])

    print(
        "Результаты проверки сохранены:",
        filepath
    )


# -------------------------------------------------
# Вывод проверки в терминал
# -------------------------------------------------

def print_test_results(results):

    print()

    print(
        "x1 x2 x3 x4 | target | "
        "net | output | class"
    )

    for row in results:

        print(
            row["x1"],
            row["x2"],
            row["x3"],
            row["x4"],
            "|",
            row["target"],
            "|",
            round(row["net"], 6),
            "|",
            round(row["output"], 6),
            "|",
            row["class"]
        )


# -------------------------------------------------
# Построение и сохранение графика E(k)
# -------------------------------------------------

def save_error_graph(
    history,
    function_number
):

    epochs = [
        row["epoch"]
        for row in history
    ]

    errors = [
        row["error"]
        for row in history
    ]

    plt.figure()

    plt.plot(
        epochs,
        errors
    )

    plt.xlabel("Номер эпохи k")
    plt.ylabel("E(k)")

    plt.title(
        f"Функция активации №{function_number}"
    )

    plt.grid()

    filename = (
        f"error_func_{function_number}.png"
    )

    filepath = BASE_DIR / filename

    plt.savefig(
        filepath,
        dpi=200,
        bbox_inches="tight"
    )

    print(
        "График сохранён:",
        filepath
    )

    plt.show()


# -------------------------------------------------
# Обучение на полной таблице истинности
# -------------------------------------------------

def full_training(
    table,
    function_number
):

    train_indexes = list(
        range(len(table))
    )

    weights, history = train_network(
        table,
        train_indexes,
        function_number
    )

    print()
    print(
        "Функция активации №",
        function_number
    )

    print(
        "Количество эпох:",
        len(history)
    )

    print(
        "Итоговые веса:"
    )

    print(
        [
            round(weight, 6)
            for weight in weights
        ]
    )

    print(
        "Последняя ошибка E(k):",
        history[-1]["error"]
    )

    # Сохраняем историю обучения
    save_training_history(
        history,
        function_number
    )

    # Проверяем сеть на всех 16 комбинациях
    correct, results = get_test_results(
        table,
        weights,
        function_number
    )

    print_test_results(results)

    print()
    print(
        "Все 16 комбинаций "
        "классифицированы правильно:",
        correct
    )

    # Сохраняем результаты проверки
    save_test_results(
        results,
        function_number
    )

    # Сохраняем график ошибки
    save_error_graph(
        history,
        function_number
    )


# -------------------------------------------------
# Сохранение минимального обучающего набора
# -------------------------------------------------

def save_minimal_set(
    table,
    indexes,
    function_number
):

    filename = (
        f"minimal_set_func_"
        f"{function_number}.csv"
    )

    filepath = BASE_DIR / filename

    with open(
        filepath,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(
            file,
            delimiter=";"
        )

        writer.writerow([
            "index",
            "x1",
            "x2",
            "x3",
            "x4",
            "target"
        ])

        for index in indexes:

            inputs, target = table[index]

            writer.writerow([
                index,
                inputs[1],
                inputs[2],
                inputs[3],
                inputs[4],
                target
            ])

    print(
        "Минимальная выборка сохранена:",
        filepath
    )


# -------------------------------------------------
# Поиск минимальной обучающей выборки
# -------------------------------------------------

def find_minimal_training_set(
    table,
    function_number
):

    total_vectors = len(table)

    for subset_size in range(
        1,
        total_vectors + 1
    ):

        print()
        print(
            "Проверяются выборки длины:",
            subset_size
        )

        subsets = combinations(
            range(total_vectors),
            subset_size
        )

        checked = 0

        for train_indexes in subsets:

            checked += 1

            weights, history = train_network(
                table,
                train_indexes,
                function_number
            )

            # Проверяем полученную сеть
            # на ВСЕХ 16 комбинациях
            correct, results = get_test_results(
                table,
                weights,
                function_number
            )

            if correct:

                print()
                print(
                    "Минимальная выборка найдена"
                )

                print(
                    "Количество векторов:",
                    subset_size
                )

                print(
                    "Проверено сочетаний:",
                    checked
                )

                print(
                    "Индексы:",
                    train_indexes
                )

                print(
                    "Количество эпох:",
                    len(history)
                )

                print(
                    "Итоговые веса:",
                    [
                        round(weight, 6)
                        for weight in weights
                    ]
                )

                print()
                print(
                    "Обучающие векторы:"
                )

                for index in train_indexes:

                    inputs, target = table[index]

                    print(
                        index,
                        inputs[1:],
                        "->",
                        target
                    )

                # Сохраняем найденную выборку
                save_minimal_set(
                    table,
                    train_indexes,
                    function_number
                )

                # Сохраняем историю обучения
                # только найденной минимальной выборки
                save_training_history(
                    history,
                    function_number,
                    prefix="minimal_"
                )

                # Сохраняем проверку
                # найденной сети на 16 комбинациях
                save_test_results(
                    results,
                    function_number,
                    prefix="minimal_"
                )

                print_test_results(
                    results
                )

                return (
                    train_indexes,
                    weights,
                    history
                )

    print(
        "Подходящая обучающая "
        "выборка не найдена"
    )

    return None


# -------------------------------------------------
# Вывод таблицы истинности
# -------------------------------------------------

def print_truth_table(table):

    print()
    print("Таблица истинности:")
    print("x1 x2 x3 x4 | F")

    for inputs, target in table:

        print(
            inputs[1],
            inputs[2],
            inputs[3],
            inputs[4],
            "|",
            target
        )


# -------------------------------------------------
# Главное меню
# -------------------------------------------------

def main():

    table = make_truth_table()

    print_truth_table(table)

    while True:

        print()
        print("Выберите режим:")
        print(
            "1 — обучение на полной таблице"
        )
        print(
            "2 — поиск минимальной выборки"
        )
        print(
            "0 — выход"
        )

        mode = input(
            "Режим: "
        )

        if mode == "0":
            break

        if mode not in ["1", "2"]:

            print(
                "Неверный режим"
            )

            continue

        print()
        print(
            "Выберите функцию активации:"
        )

        print(
            "1 — пороговая"
        )

        print(
            "2 — рациональная сигмоидная"
        )

        function_input = input(
            "Функция: "
        )

        if function_input not in ["1", "2"]:

            print(
                "Необходимо выбрать 1 или 2"
            )

            continue

        function_number = int(
            function_input
        )

        if mode == "1":

            full_training(
                table,
                function_number
            )

        elif mode == "2":

            find_minimal_training_set(
                table,
                function_number
            )


# -------------------------------------------------
# Запуск программы
# -------------------------------------------------

if __name__ == "__main__":
    main()