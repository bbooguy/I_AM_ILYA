import math
import matplotlib.pyplot as plt

BASE_P = 8
BASE_ETA = 0.05
BASE_M = 4000

M_VALUES = [500, 1000, 2000, 3000, 4000]
ETA_VALUES = [0.1, 0.3, 0.5, 0.7, 1.0]
P_VALUES = [3, 4, 5, 6, 7, 8, 9]
REAL_INPUTS = True

N = 20
a = 1.7
b = 2

def func(t):
    return math.sqrt(math.tan(-t))


def data():
    dt = (b - a) / (N - 1)
    t_lst = []
    x_lst = []
    for i in range(N):
        t = a + i * dt
        x = func(t)
        t_lst.append(t)
        x_lst.append(x)
    return t_lst, x_lst, dt


def train(x_lst, p, eta, M):
    w = [0.0] * p
    for epoch in range(M):
        for i in range(p, N):
            net = 0
            for j in range(p):
                net += w[j] * x_lst[i - p + j]
            delta = x_lst[i] - net
            for j in range(p):
                w[j] += eta * delta * x_lst[i - p + j]
    return w


def forecast(x_lst, w, p, dt):
    history = list(x_lst)
    t_f = []
    x_f = []
    for k in range(N):
        net = 0
        for j in range(p):
            net += w[j] * history[-p + j]
        t = b + (k + 1) * dt
        t_f.append(t)
        x_f.append(net)
        if REAL_INPUTS:
            history.append(func(t))
        else:
            history.append(net)
    return t_f, x_f


def calc_err(t_f, x_f):
    s = 0
    for i in range(len(x_f)):
        s += (func(t_f[i]) - x_f[i]) ** 2
    return math.sqrt(s)


def run_model(p, eta, M):
    t_lst, x_lst, dt = data()
    w = train(x_lst, p, eta, M)
    t_f, x_f = forecast(x_lst, w, p, dt)
    err = calc_err(t_f, x_f)
    return t_lst, x_lst, t_f, x_f, err


def draw_forecast(ax, t_lst, x_lst, t_f, x_f, title):
    real_t = t_lst + t_f
    real_x = []
    for t in real_t:
        real_x.append(func(t))
    ax.plot(real_t, real_x, label="Real function")
    ax.plot(t_lst, x_lst, "o", markerfacecolor="none", label="Training data")
    ax.plot(t_f, x_f, "o", markerfacecolor="none", label="Forecast")
    ax.axvline(b, linestyle="--")
    ax.set_xlabel("t")
    ax.set_ylabel("x(t)")
    ax.set_title(title)
    ax.grid()
    ax.legend(fontsize=7)


def draw_error(ax, values, errors, xlabel, title):
    ax.plot(values, errors, marker="o")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Error")
    ax.set_title(title)
    ax.grid()


def experiment_M():
    errors = []
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    for k in range(len(M_VALUES)):
        M = M_VALUES[k]
        t_lst, x_lst, t_f, x_f, err = run_model(BASE_P, BASE_ETA, M)
        errors.append(err)
        print("M =", M, "err =", err)
        draw_forecast(axes[k], t_lst, x_lst, t_f, x_f, "M = " + str(M) + ", error = " + str(round(err, 4)))
    draw_error(axes[5], M_VALUES, errors, "M", "Error dependence on epochs")
    fig.tight_layout()
    return errors


def experiment_eta():
    errors = []
    for eta in ETA_VALUES:
        _, _, _, _, err = run_model(BASE_P, eta, BASE_M)
        errors.append(err)
        print("eta =", eta, "err =", err)
    fig, ax = plt.subplots(figsize=(7, 5))
    draw_error(ax, ETA_VALUES, errors, "eta", "Error dependence on learning rate")
    fig.tight_layout()
    return errors


def experiment_p():
    errors = []
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    axes = axes.flatten()
    for k in range(len(P_VALUES)):
        p = P_VALUES[k]
        t_lst, x_lst, t_f, x_f, err = run_model(p, BASE_ETA, BASE_M)
        errors.append(err)
        print("p =", p, "err =", err)
        draw_forecast(axes[k], t_lst, x_lst, t_f, x_f, "p = " + str(p) + ", error = " + str(round(err, 4)))
    draw_error(axes[7], P_VALUES, errors, "p", "Error dependence on window size")
    fig.tight_layout()
    return errors

def single(p, eta, M):
    t_lst, x_lst, t_f, x_f, err = run_model(p, eta, M)
    print("p =", p, "eta =", eta, "M =", M, "err =", err)
    fig, ax = plt.subplots(figsize=(8, 5))
    draw_forecast(ax, t_lst, x_lst, t_f, x_f, "p = " + str(p) + ", eta = " + str(eta) + ", M = " + str(M))
    fig.tight_layout()

#single(BASE_P, BASE_ETA, BASE_M)
#experiment_M()                       # влияние M
#experiment_eta()                   # влияние η
experiment_p()                     # влияние p
plt.show()