import numpy as np
import matplotlib.pyplot as plt

TOL = 1e-9


# ---------- Задача ----------
def f(x1, x2):
    return (x1**2 + 3) ** 2 - (x2**2 + 2) ** 2 - 10


def grad_f(x):
    x1, x2 = x
    return np.array([4 * x1**3 + 12 * x1, -4 * x2**3 - 8 * x2])


def g(x):
    x1, x2 = x
    return np.array([x1**2 + x2**2 - 1, -x1, -x2])


def grad_g(x):
    x1, x2 = x
    return np.array([[2 * x1, 2 * x2],   # grad g1
                     [-1.0, 0.0],        # grad g2
                     [0.0, -1.0]])       # grad g3


def hessian_L(x, lam):
    """Матрица Гессе функции Лагранжа L = f + sum(lam_j * g_j) при lam0 = 1."""
    x1, x2 = x
    return np.array([[12 * x1**2 + 12 + 2 * lam[0], 0.0],
                     [0.0, -12 * x2**2 - 8 + 2 * lam[0]]])


points = {
    "A": np.array([0.0, 0.0]),
    "B": np.array([0.0, 1.0]),
    "C": np.array([1.0, 0.0]),
}


def multipliers(x):
    gx = g(x)
    active = np.abs(gx) < TOL
    lam = np.zeros(3)
    if active.any():
        J = grad_g(x)[active]                  
        sol, *_ = np.linalg.lstsq(J.T, -grad_f(x), rcond=None)
        lam[active] = sol
    return lam, active


def second_order(x, lam, active):
    H = hessian_L(x, lam)
    J = grad_g(x)
    angles = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    values = []
    for t in angles:
        dx = np.array([np.cos(t), np.sin(t)])
        ok = True
        for j in range(3):
            if not active[j]:
                continue
            dgj = J[j] @ dx
            if abs(lam[j]) > TOL:                 
                ok &= abs(dgj) < TOL
            else:                                 
                ok &= dgj <= TOL
        if ok:
            values.append(dx @ H @ dx)
    return np.array(values)


print("Условно-стационарные точки:")
for name, x in points.items():
    lam, active = multipliers(x)
    resid = np.linalg.norm(grad_f(x) + grad_g(x).T @ lam)
    feasible = np.all(g(x) <= TOL)
    compl = np.max(np.abs(lam * g(x)))
    print(f"{name} = ({x[0]:.0f}; {x[1]:.0f}):  f = {f(*x):.4f},  "
          f"lambda = ({lam[0]:.4f}; {lam[1]:.4f}; {lam[2]:.4f}),  "
          f"допустима: {feasible},  |grad L| = {resid:.1e},  "
          f"max|lam*g| = {compl:.1e}")

print("\nУсловия второго порядка (d^2 L на допустимых dx):")
for name, x in points.items():
    lam, active = multipliers(x)
    d2 = second_order(x, lam, active)
    lo, hi = d2.min(), d2.max()
    if lo > TOL:
        verdict = "условный локальный минимум"
    elif hi < -TOL:
        verdict = "условный локальный максимум"
    else:
        verdict = "достаточные условия не выполняются; экстремума нет"
    print(f"{name}: d2L принимает значения от {lo:.2f} до {hi:.2f}  ->  {verdict}")

# ---------- Проверка перебором по сетке ----------
n = 2001
x1, x2 = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
inside = x1**2 + x2**2 <= 1 + 1e-12
F = np.where(inside, f(x1, x2), np.nan)
i_min = np.nanargmin(F)
i_max = np.nanargmax(F)
print("\nПроверка перебором по сетке:")
print(f"min f = {F.flat[i_min]:.4f} в точке ({x1.flat[i_min]:.3f}; {x2.flat[i_min]:.3f})")
print(f"max f = {F.flat[i_max]:.4f} в точке ({x1.flat[i_max]:.3f}; {x2.flat[i_max]:.3f})")

# ---------- Рисунок ----------
fig, ax = plt.subplots(figsize=(7, 6))
cs = ax.contourf(x1, x2, F, levels=30)
ax.contour(x1, x2, F, levels=12, colors="k", linewidths=0.4)
fig.colorbar(cs, label=r"$f(x_1, x_2)$")

t = np.linspace(0, np.pi / 2, 400)
ax.plot(np.cos(t), np.sin(t), "b", lw=1.8, label=r"$g_1(x)=0$")
ax.plot([0, 0], [0, 1], "r", lw=1.8, label=r"$g_2(x)=0$")
ax.plot([0, 1], [0, 0], "g", lw=1.8, label=r"$g_3(x)=0$")

for name, x in points.items():
    ax.scatter(*x, c="k", s=45, zorder=5)
    ax.annotate(f"{name} ({x[0]:.0f}; {x[1]:.0f})\nf = {f(*x):.0f}", x,
                xytext=(10, 8), textcoords="offset points", fontsize=10,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8))

ax.set_xlabel(r"$x_1$")
ax.set_ylabel(r"$x_2$")
ax.set_title("Допустимая область и условно-стационарные точки")
ax.set_xlim(-0.1, 1.25)
ax.set_ylim(-0.1, 1.15)
ax.set_aspect("equal")
ax.grid(True, alpha=0.4)
ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig("result_2_2.png", dpi=200)
print("\nРисунок сохранён: result_2_2.png")