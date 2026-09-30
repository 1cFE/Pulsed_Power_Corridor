"""Sensitivity of pulsed-power LCOE at 1 GWe, one cost-down lever at a time.

Same convention as stel_tornado_plot.py for the mature corridor: every bar is a
row of that corridor's cost-down lever table, taken from its tier-0 design basis
to the DEEPEST value the evidence ladder reaches for it.  The ladder applies
them cumulatively; this shows each one alone, so the bars do not sum to the
ladder's descent.

Both configurations are drawn, since the corridor's whole point is that the two
ends of the rep-rate axis fail differently: the fiber/direct concept carries its
cost in the driver and the wall, the KrF/hybrid concept in the consumable.

Reads corridor_data.json through corridor_tiers.py's reduced pulsed model, which
reproduces 1costingFE at baseline.  Writes figures/pulsed_tornado.png.

matplotlib's font_manager imports plistlib -> xml.parsers.expat -> pyexpat,
blocked by an Application Control policy here; plistlib is macOS-only, so a stub
lets the rest of matplotlib load.
"""
import sys, types
sys.modules.setdefault("plistlib", types.ModuleType("plistlib"))

import io, contextlib, importlib.util
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

spec = importlib.util.spec_from_file_location("c", "corridor_tiers.py")
C = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(C)

CONCEPTS = [("BLF", "fiber / direct, 10 Hz", "#1f77b4"),
            ("Xcimer", "KrF / hybrid, 1 Hz", "#2ca02c")]


def base(concept):
    return C.plcoe(concept, C.OPT[concept], dict(C.PBASE), 0.0, 0.0)


def delta(concept, eta_f=0.0, wear_f=0.0, **lev):
    """LCOE reduction from applying one lever to the tier-0 machine."""
    L = dict(C.PBASE)
    for k, v in lev.items():
        L[k] = v[concept] if isinstance(v, dict) else v
    return base(concept) - C.plcoe(concept, C.OPT[concept], L, eta_f, wear_f)


# one entry per row of the cost-down lever table, at its deepest tier value
def rows_for(c):
    return [
        ("Cost of capital  7% $\\rightarrow$ 3%",        delta(c, wacc=0.03)),
        ("Book life  30 $\\rightarrow$ 80 yr",           delta(c, life=80.0)),
        ("Construction  5 $\\rightarrow$ 2.5 yr",        delta(c, constr=2.5)),
        ("Availability  0.85 $\\rightarrow$ 0.98",       delta(c, av=0.98)),
        ("Fixed O&M  $-$55%",                             delta(c, om=0.45)),
        ("Brownfield siting",                            delta(c, bld=0.65, elec=0.40, hr=0.60)),
        ("Power cycle  $\\rightarrow$ sCO$_2$ Brayton",  delta(c, sco2=True)),
        ("Driver capital",                               delta(c, drv=C.PT3["drv"])),
        ("Target opex",                                  delta(c, tgt=C.PT3["tgt"])),
        ("Target factory capital",                       delta(c, tfac=0.65)),
        ("Laser wall-plug $\\rightarrow$ ceiling",       delta(c, eta_f=1.0)),
        ("Optics / foil shot life $\\times$3",           delta(c, wear_f=1.0)),
        ("Start-up cost $-$67%",                         delta(c, startup=13.0)),
    ]


# The corridor model works in $/MWh; this dispatch reports ¢/kWh, so every
# delta and baseline is converted once here at the plotting boundary.
# 1 ¢/kWh == $10/MWh.
CENTS = 0.1

data = {c: [(lab, v * CENTS) for lab, v in rows_for(c)] for c, _, _ in CONCEPTS}
labels = [r[0] for r in data["BLF"]]
order = sorted(range(len(labels)),
               key=lambda i: max(data[c][i][1] for c, _, _ in CONCEPTS))
labels = [labels[i] for i in order]

INK, MUTED, RULE, SURFACE = "#1a1c20", "#6a6f78", "#c9c6bf", "#fcfcfb"
fig, ax = plt.subplots(figsize=(11.0, 8.2))
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)
fig.subplots_adjust(left=0.315, right=0.965, top=0.875, bottom=0.145)

h = 0.38
for k, (c, lab, col) in enumerate(CONCEPTS):
    vals = [data[c][i][1] for i in order]
    off = (0.5 - k) * h
    ax.barh([i + off for i in range(len(vals))], vals, h, label=lab,
            color=col, edgecolor="white", linewidth=0.6, zorder=3)
    span = max(max(v for _, v in data[cc]) for cc, _, _ in CONCEPTS)
    for i, v in enumerate(vals):
        ax.text(v + span * 0.012, i + off, f"{v:.2f}", va="center", ha="left",
                fontsize=8.6, color=INK)

ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels, fontsize=9.8, color=INK)
span = max(max(v for _, v in data[c]) for c, _, _ in CONCEPTS)
ax.set_xlim(0, span * 1.11)
ax.set_xlabel("reduction in LCOE  [¢/kWh]", fontsize=10.8, color=INK, fontweight="600")
ax.grid(axis="x", color=RULE, alpha=.35, zorder=0)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(RULE)
ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
for lbl in ax.get_yticklabels():
    lbl.set_color(INK)
leg = ax.legend(frameon=False, fontsize=11, loc="lower right", labelcolor=INK)
for t in leg.get_texts():
    t.set_fontweight("600")

fig.text(0.02, 0.972, "What moves the cost of a 1 GWe pulsed plant",
         fontsize=14.5, color=INK, ha="left", va="top", fontweight="600")
fig.text(0.02, 0.936,
         f"baseline {base('BLF') * CENTS:.1f}¢ fiber / "
         f"{base('Xcimer') * CENTS:.1f}¢ KrF per kWh  ·  "
         "each cost-down lever applied alone, at its deepest evidence tier",
         fontsize=10, color=MUTED, ha="left", va="top")

fig.savefig("figures/pulsed_tornado.png", dpi=155, facecolor=SURFACE)
print(f"wrote figures/pulsed_tornado.png")
print(f"  baseline  fiber {base('BLF') * CENTS:.3f} c/kWh"
      f"   KrF {base('Xcimer') * CENTS:.3f} c/kWh\n")
print(f"  {'lever  [c/kWh reduction]':<40}{'fiber':>9}{'KrF':>9}")
for i in reversed(order):
    lab = data['BLF'][i][0]
    clean = (lab.replace("$_2$", "2").replace("$\\rightarrow$", "->")
                .replace("$\\times$", "x").replace("$-$", "-"))
    print(f"  {clean:<40}{data['BLF'][i][1]:>9.2f}{data['Xcimer'][i][1]:>9.2f}")
