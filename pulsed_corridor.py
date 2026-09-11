"""Pulsed-power low-cost corridor (laser + MIF/magnetic), 1costingFE PR #43 at
1 GWe. Concepts filtered to technical_feasibility >= 2 (fusion-tea scores).
  x = driver capital $/J (structural: driver hardware)
  y = q_eng = gross electric / recirculating power  (uniform net-power margin;
       the cross-concept generalization of eta*G -- viable > 1, comfortable > ~3)
  bubble = chamber+first-wall capital (C220101)   color/number = LCOE ($/MWh)
Sizing: lasers single-chamber (n_mod=1); MagLIF n_mod-solved; FRC/mag-target/Zap
native modular. n_mod shown per point. FRC is D-He3 + direct conversion (hence
high q_eng, ~$0 chamber); all others D-T thermal.
"""
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, r"c:\Users\mallo\Deterministic_Concept_scoring\1costingfe\src")
from costingfe import CostModel
from costingfe.types import ConfinementConcept as C, Fuel, LaserDriverType as LDT

LIQ = dict(wall_improvement_factor=50.0, neutron_wall_load_max_mw_m2=20.0)
ADV = dict(wall_improvement_factor=2.0, neutron_wall_load_max_mw_m2=8.0)
DRY = dict(wall_improvement_factor=1.0, neutron_wall_load_max_mw_m2=4.0)


def run_laser(ldt, f, wall, drive):
    m = CostModel(C.LASER_IFE, Fuel.DT, laser_driver_type=LDT(ldt))
    return m.forward(net_electric_mw=1000.0, availability=0.85, lifetime_yr=30.0,
                     size_from_power=True, sizing_axis="target_yield",
                     sizing_mode="single_chamber", target_cost_mode="capsule_fab",
                     drive_mode=drive, f_rep=f, **wall)


def run_simple(concept, fuel, ty=False):
    m = CostModel(concept, fuel)
    kw = dict(size_from_power=True)
    if ty:
        kw["sizing_axis"] = "target_yield"
    return m.forward(net_electric_mw=1000.0, availability=0.85,
                     lifetime_yr=30.0, **kw)


# (label, tf, driver $/J, runner)
SPECS = [
    ("Focused Energy\nDPSSL·direct·liq", 2.5, 205, lambda: run_laser("dpssl", 10, LIQ, "direct")),
    ("BLF\nfiber·direct·dry", 4.75, 150, lambda: run_laser("fiber", 10, DRY, "direct")),
    ("GenF\nDPSSL·direct·dry", 4.75, 205, lambda: run_laser("dpssl", 10, DRY, "direct")),
    ("Xcimer\nKrF·hybrid·liq", 3.75, 40, lambda: run_laser("krf", 0.7, LIQ, "hybrid")),
    ("Inertia\nDPSSL·indirect", 5.0, 205, lambda: run_laser("dpssl", 10, ADV, "indirect")),
    ("MagLIF\ncap-bank·liner", 3.0, 0.5, lambda: run_simple(C.MAGLIF, Fuel.DT, ty=True)),
    ("FRC + DEC\nHelion-like (D-He3)", 2.0, 0.5, lambda: run_simple(C.PULSED_FRC, Fuel.DHE3)),
    ("Mag-target\nGeneral Fusion", 2.0, 3.0, lambda: run_simple(C.MAG_TARGET, Fuel.DT)),
    ("Zap\nsheared-flow Z", 2.0, 1.5, lambda: run_simple(C.STAGED_ZPINCH, Fuel.DT)),
]

rows = []
for label, tf, dpj, fn in SPECS:
    r = fn()
    rows.append(dict(label=label, tf=tf, dpj=dpj, q=r.power_table.q_eng,
                     chamber=r.cas22_detail["C220101"], lcoe=r.costs.lcoe,
                     nmod=r.solved_n_mod))
    print(f"{label[:18]:18s} tf={tf:4} $/J={dpj:5} q_eng={rows[-1]['q']:5.2f} "
          f"chamber=${rows[-1]['chamber']:5.0f}M LCOE={rows[-1]['lcoe']:6.1f} "
          f"n_mod={rows[-1]['nmod']}")

# ---- plot -------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 7.8))
XJ = {"GenF\nDPSSL·direct·dry": 1.28}
for x in rows:
    x["xp"] = x["dpj"] * XJ.get(x["label"], 1.0)

lc = [x["lcoe"] for x in rows]
vmin, vmax = min(lc), max(lc)
sizes = [max(30, x["chamber"]) for x in rows]
smax = max(sizes)

ax.axhline(1.0, color="#b03a2e", ls="--", lw=1.2, zorder=1)
ax.text(1300, 1.08, "net-power floor  (q_eng = 1)", fontsize=8,
        color="#b03a2e", ha="right", va="bottom", style="italic")
ax.axhspan(3.0, 10, color="#eaf6ea", zorder=0)
ax.text(0.34, 8.6, "COMFORTABLE net-power margin (q_eng > 3)", fontsize=8.5,
        color="#2e6b2e", style="italic", fontweight="bold", va="center")

sc = ax.scatter([x["xp"] for x in rows], [x["q"] for x in rows],
                s=[300 + 1500 * (max(30, x["chamber"]) / smax) for x in rows],
                c=lc, cmap="RdYlGn_r", vmin=vmin, vmax=vmax,
                edgecolor="k", linewidth=1.0, zorder=3)

OFF = {
    "Focused Energy\nDPSSL·direct·liq": (0.58, 0.95, "center"),
    "BLF\nfiber·direct·dry": (0.75, 0.95, "center"),
    "GenF\nDPSSL·direct·dry": (1.6, -0.4, "left"),
    "Xcimer\nKrF·hybrid·liq": (0.72, -1.05, "center"),
    "Inertia\nDPSSL·indirect": (1.55, 0.55, "left"),
    "MagLIF\ncap-bank·liner": (1.7, 0.55, "left"),
    "FRC + DEC\nHelion-like (D-He3)": (1.5, 0.55, "left"),
    "Mag-target\nGeneral Fusion": (1.7, 0.6, "left"),
    "Zap\nsheared-flow Z": (0.62, 0.85, "center"),
}
for x in rows:
    dxf, dy, ha = OFF[x["label"]]
    ax.annotate(f"{x['label']}\n(tf {x['tf']}, n={x['nmod']})",
                (x["xp"], x["q"]), xytext=(x["xp"] * dxf, x["q"] + dy),
                fontsize=7.6, ha=ha, va="center", fontweight="bold",
                arrowprops=dict(arrowstyle="-", color="0.5", lw=0.6))
for x in rows:
    ax.annotate(f"{x['lcoe']:.0f}", (x["xp"], x["q"]), fontsize=7.6, ha="center",
                va="center", color="white", fontweight="bold", zorder=4)

ax.set_xscale("log")
ax.set_xlim(0.3, 1500)
ax.set_ylim(0, 9.2)
ax.set_xlabel("Driver capital  [$ / J]      "
              "(cap-bank / gun / piston  ←→  laser hardware)", fontsize=10.5)
ax.set_ylabel("q_eng  =  gross electric ÷ recirculating power\n"
              "(net-power margin; viable > 1, comfortable > 3)", fontsize=10.5)
ax.set_title("Pulsed-power low-cost corridor  —  technical feasibility ≥ 2  "
             "(1costingFE PR #43, 1 GWe)\n"
             "bubble = chamber+first-wall capital   •   number/color = LCOE ($/MWh)",
             fontsize=11.5)
cb = fig.colorbar(sc, ax=ax, pad=0.015)
cb.set_label("LCOE  [$/MWh]", fontsize=9)

for s, lab in [(30, "~$30M"), (300, "~$300M")]:
    ax.scatter([], [], s=300 + 1500 * (s / smax), c="0.7", edgecolor="k",
               label=f"chamber {lab}")
ax.legend(loc="upper right", fontsize=8, title="bubble = chamber cost",
          labelspacing=1.5, borderpad=1.0, framealpha=0.9)

fig.text(0.5, 0.008, "Dropped by feasibility filter (tf < 2): Heavy-ion ICF, "
         "Dense Plasma Focus, wire-array Z-pinch, Marvel/nanostructured, "
         "Sonofusion, MTIF.   FRC uses D-He3 + direct conversion (high q_eng, "
         "~$0 chamber); driver $/J for MIF concepts = cap-bank/gun/piston basis.",
         fontsize=7.0, color="0.45", ha="center")

plt.tight_layout(rect=(0, 0.035, 1, 1))
out = r"c:\Users\mallo\Deterministic_Concept_scoring\pulsed_corridor.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print("saved:", out)
