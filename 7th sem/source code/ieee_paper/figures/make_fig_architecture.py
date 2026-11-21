"""
Render figures/fig_architecture.png: the NovaByte system architecture block diagram.

Original diagram, © 2026 Team CodeCraft (NovaByte). Mirrors the current codebase
(frontend/, backend/app/, docker-compose.yml). Run from anywhere:
    python ieee_paper/figures/make_fig_architecture.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon  # noqa: E402

COPYRIGHT = "© 2026 Team CodeCraft (NovaByte). All rights reserved."
OUT = Path(__file__).with_name("fig_architecture.png")

W, H = 1200, 1900  # drawing units; y grows downward
INK, TITLE, SUB, MUTED = "#334155", "#0f172a", "#475569", "#94a3b8"
TIERS = {  # tier number -> (name, fill, accent)
    1: ("Users", "#f8fafc", "#475569"),
    2: ("Web App", "#fdf4ff", "#a21caf"),
    3: ("Backend API", "#f0fdfa", "#0f766e"),
    4: ("Onboarding Agent", "#fff7ed", "#c2410c"),
    5: ("Data & Services", "#eff6ff", "#1d4ed8"),
}
RAIL_X, BODY_X, BODY_W = 40, 150, W - 190  # left tier rail, then tier bodies

fig = plt.figure(figsize=(W / 100, H / 100), dpi=200)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(H, 0)
ax.axis("off")


def rounded(x, y, w, h, fc, ec, lw=2.0, r=14, z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=z))


def tier(n, y, h):
    name, fill, accent = TIERS[n]
    # Numbered rail badge, then the tier body with its name.
    rounded(RAIL_X, y, 90, h, accent, accent, r=16)
    ax.text(RAIL_X + 45, y + h / 2 - 16, str(n), ha="center", va="center", fontsize=26, fontweight="bold", color="white")
    ax.text(RAIL_X + 45, y + h / 2 + 22, "TIER", ha="center", va="center", fontsize=9, fontweight="bold", color="white")
    rounded(BODY_X, y, BODY_W, h, fill, accent, lw=2.2, r=16)
    ax.text(BODY_X + 22, y + 28, name, ha="left", va="center", fontsize=15, fontweight="bold", color=accent)


def block(cx, cy, w, h, title, lines=(), accent=INK):
    rounded(cx - w / 2, cy - h / 2, w, h, "white", accent, lw=1.8, r=10, z=2)
    top = cy - (len(lines) * 21) / 2
    ax.text(cx, top - 4, title, ha="center", va="center", fontsize=12.5, fontweight="bold", color=TITLE, zorder=3)
    for i, line in enumerate(lines):
        ax.text(cx, top + 22 + i * 21, line, ha="center", va="center", fontsize=10.5, color=SUB, zorder=3)


def down_arrow(x, y0, y1, label=None):
    ax.annotate("", xy=(x, y1), xytext=(x, y0), zorder=4,
                arrowprops=dict(arrowstyle="<|-|>", color=INK, lw=2, mutation_scale=16, shrinkA=0, shrinkB=0))
    if label:
        ax.text(x + 12, (y0 + y1) / 2, label, ha="left", va="center", fontsize=10.5, style="italic", color=SUB)


def person(cx, cy, label, sub, accent):
    ax.add_patch(Circle((cx, cy - 22), 15, fc=accent, ec=accent, zorder=3))
    ax.add_patch(FancyBboxPatch((cx - 24, cy - 2), 48, 26, boxstyle="round,pad=0,rounding_size=12", fc=accent, ec=accent, zorder=3))
    ax.text(cx + 48, cy - 12, label, ha="left", va="center", fontsize=13, fontweight="bold", color=TITLE)
    ax.text(cx + 48, cy + 12, sub, ha="left", va="center", fontsize=10.5, color=SUB)


def stage(x, y, w, h, title, nodes, accent, first=False):
    """A chevron-shaped agent stage listing the LangGraph nodes it groups."""
    notch = 26
    pts = [(x, y), (x + w - notch, y), (x + w, y + h / 2), (x + w - notch, y + h), (x, y + h)]
    if not first:
        pts.append((x + notch, y + h / 2))
    ax.add_patch(Polygon(pts, closed=True, fc="white", ec=accent, lw=1.8, zorder=2))
    cx = x + w / 2 + (0 if first else notch / 4)
    ax.text(cx, y + 26, title, ha="center", va="center", fontsize=12.5, fontweight="bold", color=accent, zorder=3)
    for i, node in enumerate(nodes):
        ax.text(cx, y + 54 + i * 21, node, ha="center", va="center", fontsize=10.2, color=SUB, zorder=3)


# ── Title
ax.text(W / 2, 40, "NovaByte — System Architecture", ha="center", va="center", fontsize=19, fontweight="bold", color=TITLE)
ax.text(W / 2, 72, "AI-assisted developer onboarding: five tiers from people to services",
        ha="center", va="center", fontsize=11.5, color=SUB)

# ── Tier 1: Users
tier(1, 105, 120)
person(300, 175, "Employee", "Onboards with a personalized plan", TIERS[1][2])
person(760, 175, "HR Admin", "Invites, monitors and curates", TIERS[1][2])
down_arrow(W / 2 + 35, 225, 265, "browser · HTTPS")

# ── Tier 2: Web App
tier(2, 265, 210)
acc = TIERS[2][2]
block(420, 370, 440, 120, "Employee portal",
      ("Profile view & edit · Dashboard", "Checklist with evidence · AI chat", "Knowledge search · Roadmap"), acc)
block(905, 370, 440, 120, "HR portal",
      ("Live progress · Employee details", "Invites (send · resend · cancel)", "Document editor · Analytics"), acc)
ax.text(BODY_X + BODY_W - 20, 456, "React 19 · TypeScript · Vite · Tailwind CSS", ha="right", va="center", fontsize=10, color=MUTED)
down_arrow(W / 2 + 35, 475, 515, "REST · SSE / WebSocket streaming")

# ── Tier 3: Backend API
tier(3, 515, 230)
acc = TIERS[3][2]
for cx, title, lines in [
    (300, "Access", ("JWT sign-in · PBKDF2", "Employee / HR roles")),
    (530, "Gates", ("Profile gate", "Rate limits")),
    (760, "Onboarding", ("Plan generator", "Evidence-based progress")),
    (990, "Admin", ("Invites · Employee view", "Knowledge publishing")),
]:
    block(cx, 625, 210, 100, title, lines, acc)
ax.text(BODY_X + BODY_W - 20, 726, "FastAPI · Uvicorn · Pydantic", ha="right", va="center", fontsize=10, color=MUTED)
down_arrow(W / 2 + 35, 745, 785, "one agent run per chat turn")

# ── Tier 4: Onboarding Agent (9 LangGraph nodes in three stages)
tier(4, 785, 255)
acc = TIERS[4][2]
stage(180, 835, 320, 160, "1  Understand", ("Session Loader", "Router (rules + LLM)"), acc, first=True)
stage(480, 835, 360, 160, "2  Act", ("Persona → personal plan", "RAG → grounded answer", "Checklist → Verify", "Email → HR report"), acc)
stage(820, 835, 310, 160, "3  Respond", ("Composer + citations", "Ticket → starter issue"), acc)
ax.text(BODY_X + BODY_W - 20, 1018, "LangGraph state graph · 9 nodes", ha="right", va="center", fontsize=10, color=MUTED)

# ── Tier 5: Data & Services
tier(5, 1080, 400)
acc = TIERS[5][2]
ax.text(BODY_X + 22, 1135, "Stores", ha="left", va="center", fontsize=11.5, fontweight="bold", color=SUB)
block(320, 1210, 300, 100, "SQLite", ("Users · sessions", "checklists · chat"), acc)
block(665, 1210, 300, 100, "Knowledge documents", ("Markdown, edited by HR",), acc)
block(1000, 1210, 280, 100, "Vector index", ("ChromaDB · 233 chunks",), acc)
ax.annotate("", xy=(860, 1210), xytext=(815, 1210), zorder=4,
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=2, mutation_scale=16))
ax.text(BODY_X + 22, 1300, "External services", ha="left", va="center", fontsize=11.5, fontweight="bold", color=SUB)
for cx, title, lines in [
    (275, "LLM", ("NVIDIA Nemotron", "→ Gemini fallback")),
    (520, "Embeddings", ("MiniLM-L6-v2", "384-dim vectors")),
    (765, "GitHub", ("OAuth · repos", "starter issues")),
    (1005, "Email (SMTP)", ("Invites · resets", "HR reports")),
]:
    block(cx, 1385, 220, 110, title, lines, acc)
down_arrow(W / 2 + 35, 1040, 1080, "reads & writes state · retrieves context · calls services")

# ── Key properties (plain-language summary under the diagram)
rounded(BODY_X, 1515, BODY_W, 250, "#f8fafc", "#cbd5e1", lw=1.5, r=16)
ax.text(BODY_X + 22, 1545, "How it works", ha="left", va="center", fontsize=13, fontweight="bold", color=TITLE)
for i, line in enumerate([
    "Employees get a plan built from their profile; tasks count as done only with evidence.",
    "Answers come only from company documents, with verified citations.",
    "HR sees every employee's live progress and can invite, review and publish documents.",
    "If the primary LLM fails, the call moves to the fallback model automatically.",
    "Every integration runs in mock mode for development or live mode in production.",
]):
    ax.add_patch(Circle((BODY_X + 34, 1585 + i * 36), 5, fc=TIERS[4][2], ec="none", zorder=3))
    ax.text(BODY_X + 50, 1585 + i * 36, line, ha="left", va="center", fontsize=11, color=SUB)

# ── Copyright footer
ax.plot([40, W - 40], [1815, 1815], color="#e2e8f0", lw=1.2)
ax.text(W / 2, 1850, COPYRIGHT, ha="center", va="center", fontsize=11, color=SUB)

fig.savefig(OUT, dpi=200, facecolor="white", metadata={"Copyright": COPYRIGHT, "Author": "Team CodeCraft"})
print(f"wrote {OUT}")
