"""
Render figures/fig_workflow.png: the LangGraph supervisor workflow (9 nodes).

Mirrors backend/app/agent/graph.py. Run from anywhere:
    python ieee_paper/figures/make_fig_workflow.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon  # noqa: E402

W, H = 1358, 2290  # drawing units; y grows downward
OUT = Path(__file__).with_name("fig_workflow.png")

INK = "#334155"
TITLE = "#0f172a"
SUB = "#475569"
STYLES = {
    "io": ("#e0f2fe", "#0284c7"),
    "infra": ("#f8fafc", "#64748b"),
    "router": ("#f1f5f9", "#334155"),
    "node": ("#eff6ff", "#2563eb"),
    "verify": ("#fff7ed", "#ea580c"),
    "composer": ("#f3e8ff", "#7c3aed"),
    "ticket": ("#ecfdf5", "#059669"),
    "end": ("#f1f5f9", "#475569"),
    "decision": ("#fef3c7", "#d97706"),
}

fig = plt.figure(figsize=(W / 100, H / 100), dpi=163)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(H, 0)
ax.axis("off")


def box(cx, cy, w, h, title, sub, style, pill=False):
    face, edge = STYLES[style]
    radius = h / 2 if pill else 14
    ax.add_patch(FancyBboxPatch((cx - w / 2 + radius, cy - h / 2 + radius), w - 2 * radius, h - 2 * radius,
                                boxstyle=f"round,pad={radius}", fc=face, ec=edge, lw=3, zorder=2))
    ax.text(cx, cy - 17, title, ha="center", va="center", fontsize=15, fontweight="bold", color=TITLE, zorder=3)
    ax.text(cx, cy + 22, sub, ha="center", va="center", fontsize=12, color=SUB, zorder=3)


def diamond(cx, cy, w, h, title, sub):
    face, edge = STYLES["decision"]
    ax.add_patch(Polygon([(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)],
                         closed=True, fc=face, ec=edge, lw=3, zorder=2))
    ax.text(cx, cy - 13, title, ha="center", va="center", fontsize=14, fontweight="bold", color=TITLE, zorder=3)
    ax.text(cx, cy + 18, sub, ha="center", va="center", fontsize=11.5, color=SUB, zorder=3)


def path(points, dashed=False):
    xs, ys = zip(*points)
    ax.plot(xs, ys, color=INK, lw=2.6, ls=(0, (6, 4)) if dashed else "-", zorder=1, solid_capstyle="butt")
    (x0, y0), (x1, y1) = points[-2], points[-1]
    ax.annotate("", xy=(x1, y1), xytext=(x0 + (x1 - x0) * 0.9, y0 + (y1 - y0) * 0.9),
                arrowprops=dict(arrowstyle="-|>,head_length=0.9,head_width=0.45", color=INK, lw=2.6), zorder=4)


def label(x, y, text, color=TITLE, ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=12, fontweight="bold", color=color, zorder=3,
            bbox=dict(fc="white", ec="none", pad=2))


NW, NH = 262, 120  # branch node size
X_PERSONA, X_RAG, X_CHECK, X_EMAIL = 160, 480, 860, 1200
Y_INPUT, Y_LOAD, Y_ROUTER, Y_INTENT = 107, 297, 500, 727
Y_ROW1, Y_ROW2, Y_COMPOSER, Y_PHASE, Y_TICKET, Y_END = 980, 1200, 1420, 1650, 1880, 2135

# Spine
box(679, Y_INPUT, 590, 82, "User Input Received", "HTTP REST / SSE Stream / WebSocket", "io", pill=True)
box(679, Y_LOAD, 612, 106, "1. Session Loader Node", "Rehydrate Persona, Plan & Progress (SQLite)", "infra")
box(679, Y_ROUTER, 612, 106, "2. Router Node", "Rule-Based Intent + LLM Fallback", "router")
diamond(679, Y_INTENT, 474, 126, "Intent / Phase?", "Branch Decision")
path([(679, Y_INPUT + 41), (679, Y_LOAD - 53)])
path([(679, Y_LOAD + 53), (679, Y_ROUTER - 53)])
path([(679, Y_ROUTER + 53), (679, Y_INTENT - 63)])

# Router branches
box(X_PERSONA, Y_ROW1, NW, NH, "3. Persona Node", "Role Detection & Plan", "node")
box(X_RAG, Y_ROW1, NW, NH, "4. RAG Node", "Persona-Aware Context", "node")
box(X_CHECK, Y_ROW1, NW, NH, "5. Checklist Node", "Evidence-Aware Updates", "node")
box(X_CHECK, Y_ROW2, NW, NH, "6. Verify Node", "Confirm Change Persisted", "verify")
box(X_EMAIL, Y_ROW2, NW, NH, "7. Email Node", "HR Completion Report", "node")

path([(442, Y_INTENT), (X_PERSONA, Y_INTENT), (X_PERSONA, Y_ROW1 - NH / 2)])
label(300, Y_INTENT - 32, "greeting / intro")
path([(590, Y_INTENT + 50), (X_RAG, Y_INTENT + 50), (X_RAG, Y_ROW1 - NH / 2)])
label(X_RAG - 30, Y_INTENT + 92, "question")
path([(768, Y_INTENT + 50), (X_CHECK, Y_INTENT + 50), (X_CHECK, Y_ROW1 - NH / 2)])
label(X_CHECK + 105, Y_INTENT + 92, "checklist_action")
path([(916, Y_INTENT), (X_EMAIL, Y_INTENT), (X_EMAIL, Y_ROW2 - NH / 2)])
label(X_EMAIL - 15, Y_INTENT - 32, "complete")
path([(679, Y_INTENT + 63), (679, Y_COMPOSER - 53)], dashed=True)
label(679, Y_ROW1 + 110, "already\ncompleted")

path([(X_CHECK, Y_ROW1 + NH / 2), (X_CHECK, Y_ROW2 - NH / 2)])
path([(X_CHECK + NW / 2, Y_ROW2), (X_EMAIL - NW / 2, Y_ROW2)])
label((X_CHECK + X_EMAIL) / 2, Y_ROW2 - 85, "all verified")

# Converge on composer
box(679, Y_COMPOSER, 612, 106, "8. Composer Node", "Grounded Reply + Verified Citations", "composer")
CTOP = Y_COMPOSER - 53
path([(X_PERSONA, Y_ROW1 + NH / 2), (X_PERSONA, 1320), (440, 1320), (440, CTOP)])
path([(X_RAG, Y_ROW1 + NH / 2), (X_RAG, 1290), (560, 1290), (560, CTOP)])
path([(X_CHECK, Y_ROW2 + NH / 2), (X_CHECK, 1290), (800, 1290), (800, CTOP)])
label(X_CHECK + 52, 1275, "otherwise")
path([(X_EMAIL, Y_ROW2 + NH / 2), (X_EMAIL, 1320), (918, 1320), (918, CTOP)])

# Starter ticket branch
diamond(679, Y_PHASE, 550, 114, "Phase == 'first_task'?", "& not ticket_assigned")
path([(679, Y_COMPOSER + 53), (679, Y_PHASE - 57)])
box(388, Y_TICKET, 374, 106, "9. Ticket Node", "Assign Starter Ticket", "ticket")
box(679, Y_END, 612, 82, "Return Response to User", "Streamed Markdown & Action State", "end", pill=True)
path([(404, Y_PHASE), (388, Y_PHASE), (388, Y_TICKET - 53)])
label(340, Y_PHASE - 26, "Yes", color="#059669")
path([(954, Y_PHASE), (1075, Y_PHASE), (1075, Y_END), (985, Y_END)])
label(1050, Y_PHASE - 26, "No", color="#dc2626")
path([(388, Y_TICKET + 53), (388, Y_END - 41)])

fig.savefig(OUT, dpi=163, facecolor="white")
print(f"wrote {OUT}")
