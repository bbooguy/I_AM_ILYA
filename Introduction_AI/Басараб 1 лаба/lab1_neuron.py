import csv
from itertools import product, combinations
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# Лабораторная работа №1, вариант 7
# F = not(x1 or x2) or x3 or x4
# ФА №1 - пороговая, ФА №2 - 0.5 * (net / (1 + |net|) + 1)

ETA = 0.3
EPS = 0.1
MAX_EPOCHS = 10000

OUT_DIR = Path(__file__).parent / "results"


def bool_func(x1, x2, x3, x4):
    return int((not (x1 or x2)) or x3 or x4)


def make_truth_table():
    vectors = []
    targets = []
    for x in product((0, 1), repeat=4):
        vectors.append((1,) + x)  # x0 = 1 - вход смещения
        targets.append(bool_func(*x))
    return vectors, targets


vectors, targets = make_truth_table()
all_ids = range(len(vectors))


def print_truth_table():
    print("Таблица истинности (x1 x2 x3 x4 | F):")
    for x, t in zip(vectors, targets):
        print(" ", *x[1:], "|", t)


def calc_net(w, x):
    return sum(wi * xi for wi, xi in zip(w, x))


def activation(net, fa):
    if fa == 1:
        return 1 if net >= 0 else 0
    return 0.5 * (net / (1 + abs(net)) + 1)


def derivative(net, fa):
    if fa == 1:
        return 1  # формула (1.5) в методичке
    s = net / (1 + abs(net))
    return 0.5 * (1 - abs(s)) ** 2


def predict(w, x, fa):
    return 1 if activation(calc_net(w, x), fa) >= 0.5 else 0


def predict_all(w, fa):
    return [predict(w, x, fa) for x in vectors]


def misclassified(w, fa):
    return sum(y != t for y, t in zip(predict_all(w, fa), targets))


def squared_error(w, fa, ids):
    return sum((targets[i] - activation(calc_net(w, vectors[i]), fa)) ** 2 for i in ids)


def epoch_row(k, w, fa):
    return k, w[:], predict_all(w, fa), misclassified(w, fa), squared_error(w, fa, all_ids)


def train(train_ids, fa):
    w = [0.0] * 5
    history = [epoch_row(0, w, fa)]

    for k in range(1, MAX_EPOCHS + 1):
        for i in train_ids:
            x = vectors[i]
            net = calc_net(w, x)
            delta = targets[i] - activation(net, fa)
            for j in range(5):
                w[j] += ETA * delta * derivative(net, fa) * x[j]

        history.append(epoch_row(k, w, fa))

        # у пороговой ФА выход 0 или 1, поэтому E < EPS там означает E = 0
        if squared_error(w, fa, train_ids) < EPS:
            break

    return w, history


def find_minimal_set(fa):
    for size in range(1, len(vectors) + 1):
        for train_ids in combinations(all_ids, size):
            w, history = train(train_ids, fa)
            if misclassified(w, fa) == 0:
                return train_ids, w, history
    return None


def hyperplane_text(w):
    text = f"{w[0]:.3f}"
    for j in range(1, 5):
        sign = "-" if w[j] < 0 else "+"
        text += f" {sign} {abs(w[j]):.3f}*x{j}"
    return text + " = 0"


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


def save_epochs(history, folder):
    rows = []
    for k, w, y, errors, e in history:
        rows.append([k] + [round(wi, 3) for wi in w] + ["".join(map(str, y))]
                    + [errors, round(e, 5)])
    header = ["k", "w0", "w1", "w2", "w3", "w4", "y", "ошибок", "E"]
    write_csv(folder / "epochs.csv", header, rows)


def save_check(w, fa, train_ids, folder):
    rows = []
    for i, (x, t) in enumerate(zip(vectors, targets)):
        net = calc_net(w, x)
        y = predict(w, x, fa)
        sample = "обучающая" if i in train_ids else "тестовая"
        rows.append(list(x[1:]) + [t, sample, round(net, 3),
                                   round(activation(net, fa), 3), y,
                                   "да" if y == t else "нет"])
    header = ["x1", "x2", "x3", "x4", "F", "выборка", "net", "out", "y", "верно"]
    write_csv(folder / "check.csv", header, rows)


def save_error_plot(history, title, folder):
    plt.figure()
    style = "o-" if len(history) < 50 else "-"
    plt.plot([row[0] for row in history], [row[4] for row in history], style,
             markerfacecolor="white")
    plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))
    plt.xlabel("Номер эпохи k")
    plt.ylabel("E(k)")
    plt.title(title)
    plt.grid(True)
    plt.savefig(folder / "error.png", dpi=200, bbox_inches="tight")
    plt.close()


def save_plane_plot(w, title, folder):
    # при фиксированных x3, x4 гиперплоскость даёт на плоскости (x1, x2)
    # прямую w1*x1 + w2*x2 + (w0 + w3*x3 + w4*x4) = 0, как в лекции про AND/OR
    fig, axes = plt.subplots(2, 2, figsize=(8, 8), constrained_layout=True)
    xs = [-0.5, 1.5]
    for ax, (x3, x4) in zip(axes.flat, product((0, 1), repeat=2)):
        for x1, x2 in product((0, 1), repeat=2):
            t = bool_func(x1, x2, x3, x4)
            ax.plot(x1, x2, "o", markersize=12, markeredgecolor="black",
                    markerfacecolor="black" if t == 1 else "white")
        c = w[0] + w[3] * x3 + w[4] * x4
        if w[2] != 0:
            ax.plot(xs, [-(c + w[1] * x) / w[2] for x in xs], "r--")
        elif w[1] != 0:
            ax.axvline(-c / w[1], color="r", linestyle="--")
        ax.text(-0.45, 1.4, f"{w[1]:.2f}*x1 {w[2]:+.2f}*x2 {c:+.2f} = 0",
                color="r", fontsize=9, va="top")
        ax.set_xlim(-0.5, 1.5)
        ax.set_ylim(-0.5, 1.5)
        ax.set_xlabel("x1")
        ax.set_ylabel("x2")
        ax.set_title(f"x3 = {x3}, x4 = {x4}")
        ax.grid(True)
    fig.suptitle(title + "\n(чёрные точки F = 1, белые F = 0)")
    fig.savefig(folder / "plane.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def print_result(title, train_ids, w, history, fa):
    print(title)
    if len(train_ids) < len(vectors):
        print("  обучающие векторы:", [vectors[i][1:] for i in train_ids])
        test_ids = [i for i in all_ids if i not in train_ids]
        correct = sum(predict(w, vectors[i], fa) == targets[i] for i in test_ids)
        print(f"  тестовые векторы: верно {correct} из {len(test_ids)}")
    else:
        print("  обучающие векторы: все 16")
    k, _, _, errors, e = history[-1]
    print("  эпох:", k)
    print("  веса:", [round(wi, 3) for wi in w])
    print("  ошибок классификации (из 16):", errors)
    print(f"  E по всем 16 векторам: {e:.5f}")
    print("  гиперплоскость:", hyperplane_text(w))
    on_plane = [x[1:] for x in vectors if abs(calc_net(w, x)) < 1e-9]
    if on_plane:
        print("  лежат на гиперплоскости (net = 0):", on_plane)


def run(mode, fa):
    folder = OUT_DIR / f"{mode}_fa{fa}"
    folder.mkdir(parents=True, exist_ok=True)

    if mode == "full":
        train_ids = all_ids
        w, history = train(train_ids, fa)
        title = f"Полное обучение, ФА №{fa}"
    else:
        result = find_minimal_set(fa)
        if result is None:
            print("Минимальный набор не найден")
            return
        train_ids, w, history = result
        title = f"Минимальный набор, ФА №{fa}"

    print_result(title, train_ids, w, history, fa)
    save_epochs(history, folder)
    save_check(w, fa, train_ids, folder)
    save_error_plot(history, title, folder)
    save_plane_plot(w, title, folder)


def main():
    print_truth_table()
    for fa in (1, 2):
        print(f"\n=== ФА №{fa} ===")
        run("full", fa)  # задание 1: обучение на всех комбинациях
        run("min", fa)   # задание 2: часть комбинаций, остальные тестовые
    print("\nФайлы сохранены в", OUT_DIR)


if __name__ == "__main__":
    main()
