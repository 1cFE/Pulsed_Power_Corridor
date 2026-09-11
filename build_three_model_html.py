"""Three-model rep-rate cost breakdown (GEM | 1costingFE | Hawker), all in $/MWh,
+ an LCOE overlay. Harmonized: net power 1 GWe, availability 0.85. Each model's
cost METHODOLOGY is native. Emits a self-contained Plotly HTML artifact.
"""
import sys, json, math
sys.path.insert(0, r"c:\Users\mallo\Deterministic_Concept_scoring\1costingfe\src")
sys.path.insert(0, r"c:\Users\mallo\Deterministic_Concept_scoring\fusion-tea")
sys.path.insert(0, r"c:\Users\mallo\Deterministic_Concept_scoring")

from costingfe import CostModel
from costingfe.types import ConfinementConcept as C, Fuel, LaserDriverType as LDT
import llnl_gem as gem
import hawker_model as hm

AVAIL = 0.85
PNET = 1000.0
AMWH = PNET * 8760.0 * AVAIL   # 7.446e6 MWh/yr

# ---------------- GEM ----------------
def gem_solveE(f):
    lo, hi = 2.0, 10.0
    for _ in range(60):
        m = (lo + hi) / 2
        n = gem.run_gem(gem.GEMInputs(laser_energy_MJ=m, pulse_rep_freq_Hz=f, plant_type=2,
                                      plant_availability=AVAIL))['outputs']['net_electric_MWe']
        lo, hi = (m, hi) if n < PNET else (lo, m)
    return (lo + hi) / 2

def gem_break(f):
    E = gem_solveE(f)
    r = gem.run_gem(gem.GEMInputs(laser_energy_MJ=E, pulse_rep_freq_Hz=f, plant_type=2,
                                  plant_availability=AVAIL))
    o = r['outputs']; td = o['total_direct_cost_M']
    dfrac = o['driver_direct_cost_M'] / td
    cfrac = r['chamber']['total_chamber_cost_M'] / td      # break chamber out of BOP
    cap = o['COE_capital_per_MWh']
    return dict(f=f, driver=cap * dfrac, chamber=cap * cfrac, bop=cap * (1 - dfrac - cfrac),
                om=o['COE_om_per_MWh'], fuel=o['COE_fuel_per_MWh'], total=o['COE_total_per_MWh'])

# ---------------- 1costingFE ----------------
LIQ = dict(wall_improvement_factor=50.0, neutron_wall_load_max_mw_m2=20.0)
def fe_break(f):
    m = CostModel(C.LASER_IFE, Fuel.DT, laser_driver_type=LDT.DPSSL)
    r = m.forward(net_electric_mw=PNET, availability=AVAIL, lifetime_yr=30.0, size_from_power=True,
                  sizing_axis="target_yield", sizing_mode="single_chamber",
                  target_cost_mode="capsule_fab", drive_mode="direct", f_rep=f, **LIQ)
    c = r.costs; d = r.cas22_detail
    fcr = c.cas90 / c.total_capital
    pm = lambda annual_M: annual_M * 1e6 / AMWH
    driver = pm(d["C220104"] * fcr); chamber = pm(d["C220101"] * fcr); factory = pm(d["C220108"] * fcr)
    replace = pm(c.cas72); consumable = pm(c.cas80); om = pm(c.cas71); total = c.lcoe
    targets = consumable + factory   # fold target-factory capital into one targets line
    other = total - (driver + chamber + factory + replace + consumable + om)
    return dict(f=f, driver=driver, chamber=chamber, replace=replace,
                targets=targets, om=om, other=other, total=total)

# ---------------- Hawker (gain model, amortized replacement costs) ----------------
HP = dict(hm.BASE); HP["mu_a"] = AVAIL
def haw_break(f, p=HP):
    E_d, G = hm.solve_Ed(PNET, f, p)          # gain model
    E_t = p["mu_d"] * E_d
    E_f_GJ = G * E_t / 1e9
    N_y = hm.SEC_YR * f * p["mu_a"]
    P_kW = PNET * 1e3
    C_p = p["alpha"] * P_kW; C_y = p["beta"] * E_f_GJ; C_d = p["gamma"] * E_d
    C_t = p["delta"] * N_y; C_om = p["eps"] * P_kW
    L_d = p["N_d"] / N_y
    E_op = PNET * 8760.0 * p["mu_a"]
    Yc, Nop, dd = 5, 40, p["d"]
    nd = nr = npl = ny = nt = no = den = 0.0
    for i in range(1, Yc + Nop + 1):
        disc = (1 + dd) ** i
        if i <= Yc:
            nd += (C_d / Yc) / disc; npl += (C_p / Yc) / disc; ny += (C_y / Yc) / disc
        else:
            nt += C_t / disc; no += C_om / disc
            nr += (C_d / L_d) / disc       # amortized replacement costs
            den += E_op / disc
    return dict(f=f, driver=nd / den, replace=nr / den, yieldv=ny / den, plant=npl / den,
                target=nt / den, om=no / den, total=(nd + nr + ny + npl + nt + no) / den)

# validation
v = haw_break(0.05, dict(hm.LOW, mu_a=0.80))
print(f"Hawker validation @0.05Hz gain-model: total=${v['total']:.1f}/MWh (paper lowest $24.6 uses G=1000 fixed)")

GEM_F = [2, 2.5, 3, 4, 5, 7, 10, 13, 15, 17, 20]
FE_F = [0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7, 10, 12, 13]  # capped at ~13 Hz (2.5 MJ shot floor)
HAW_F = [0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7, 10, 15, 20]

gem_d = [gem_break(f) for f in GEM_F]
fe_d = [fe_break(f) for f in FE_F]
haw_d = [haw_break(f) for f in HAW_F]

def col(rows, k): return [round(float(r[k]), 3) for r in rows]
GEM = {k: col(gem_d, k) for k in ["f", "driver", "chamber", "bop", "om", "fuel", "total"]}
FE = {k: col(fe_d, k) for k in ["f", "driver", "chamber", "replace", "targets", "om", "other", "total"]}
HAW = {k: col(haw_d, k) for k in ["f", "driver", "replace", "yieldv", "plant", "target", "om", "total"]}

print("GEM min:", min(GEM["total"]), "@", GEM["f"][GEM["total"].index(min(GEM["total"]))], "Hz")
print("FE  min:", min(FE["total"]), "@", FE["f"][FE["total"].index(min(FE["total"]))], "Hz")
print("HAW min:", min(HAW["total"]), "@", HAW["f"][HAW["total"].index(min(HAW["total"]))], "Hz")

# ---------------- 1costingFE by concept (same framework, different driver/drive/wall) ----------------
ADV = dict(wall_improvement_factor=2.0, neutron_wall_load_max_mw_m2=8.0)   # advanced solid wall
DRY = dict(wall_improvement_factor=1.0, neutron_wall_load_max_mw_m2=5.0)   # HAPL dry wall (f_wall=1 / nwl=5 ARIES-AT), aligned with corridor


def fe_generic(r):
    """Category breakdown ($/MWh) for any 1costingFE run. Driver = laser C220104
    OR pulsed-power cap-bank C220107; chamber = FW/blanket + shield + vessel."""
    c, d = r.costs, r.cas22_detail
    g = lambda k: float(d.get(k, 0.0))
    fcr = float(c.cas90) / float(c.total_capital)
    pm = lambda annual_M: annual_M * 1e6 / AMWH
    driver = pm((g("C220104") + g("C220107")) * fcr)
    chamber = pm((g("C220101") + g("C220102") + g("C220106")) * fcr)
    factory = pm(g("C220108") * fcr)
    replace = pm(float(c.cas72)); consumable = pm(float(c.cas80))
    om = pm(float(c.cas71)); total = float(c.lcoe)
    targets = consumable + factory
    other = total - (driver + chamber + replace + targets + om)
    return dict(driver=driver, chamber=chamber, replace=replace, targets=targets,
                om=om, other=other, total=total)


def laser_forward(ldt, wall, drive, f, **ov):
    # First-wall replacement interval is now derived FLUENCE-based inside
    # 1costingFE (core_lifetime = fluence_limit * f_wall / q_n, clamped to plant
    # life) for IFE just like MFE -- so we just pass the wall config (f_wall +
    # neutron-wall-load floor) and let the model size the interval to the actual
    # neutron wall load. No flat core_lifetime override needed.
    m = CostModel(C.LASER_IFE, Fuel.DT, laser_driver_type=LDT(ldt))
    return m.forward(net_electric_mw=PNET, availability=AVAIL, lifetime_yr=30.0,
                     size_from_power=True, sizing_axis="target_yield",
                     sizing_mode="single_chamber", target_cost_mode="capsule_fab",
                     drive_mode=drive, f_rep=f, **wall, **ov)


def maglif_forward(f):
    # single_chamber for methodological parity with the lasers (real MagLIF/Z
    # plant concepts are single-driver + rep-rated RTL, not parallel modules)
    m = CostModel(C.MAGLIF, Fuel.DT)
    return m.forward(net_electric_mw=PNET, availability=AVAIL, lifetime_yr=30.0,
                     size_from_power=True, sizing_axis="target_yield",
                     sizing_mode="single_chamber", f_rep=f)


def zap_forward(f):
    # sheared-flow-stabilized Z-pinch (Zap Energy) — pulsed-power cap-bank
    # driver, fixed-gain physics; single chamber for parity with the others
    m = CostModel(C.ZPINCH, Fuel.DT)
    return m.forward(net_electric_mw=PNET, availability=AVAIL, lifetime_yr=30.0,
                     size_from_power=True, sizing_axis="target_yield",
                     sizing_mode="single_chamber", f_rep=f)


def series(fs, fwd):
    rows = [dict(f=f, **fe_generic(fwd(f))) for f in fs]
    keys = ["f", "driver", "chamber", "replace", "targets", "om", "other", "total"]
    d = {k: [round(float(r[k]), 3) for r in rows] for k in keys}
    imin = d["total"].index(min(d["total"]))
    return d, [d["f"][imin], round(min(d["total"]), 1)]


LAS_F = [0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7, 10, 12, 13]
MAG_F = [0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7]
CONC, COPT = {}, {}
for key, fs, fwd in [
    ("blf", LAS_F, lambda f: laser_forward("fiber", DRY, "direct", f)),
    ("xcimer", LAS_F, lambda f: laser_forward("krf", LIQ, "hybrid", f)),
    ("inertia", LAS_F, lambda f: laser_forward("dpssl", DRY, "indirect", f)),
    ("focused", LAS_F, lambda f: laser_forward("dpssl", DRY, "fast_ignition", f, eta_pin=0.15, driver_laser_per_mj=264.0)),
    ("maglif", MAG_F, maglif_forward),
]:
    CONC[key], COPT[key] = series(fs, fwd)
    print(f"{key:8} min ${COPT[key][1]:.1f}/MWh @ {COPT[key][0]} Hz")

HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Rep-rate cost breakdown: three models</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
 body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;background:#f7f8fa;color:#1e2227;margin:0;padding:28px 20px 40px}
 .wrap{max-width:1500px;margin:0 auto}
 h1{font-size:23px;font-weight:650;margin:0 0 3px}
 .sub{color:#5b6169;font-size:14px;margin:0 0 20px}
 .row{display:flex;gap:16px;flex-wrap:wrap}
 .col{flex:1 1 440px;min-width:400px}
 .card{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:8px 10px 4px;box-shadow:0 1px 3px rgba(20,25,35,.05)}
 .legend{display:flex;justify-content:center;flex-wrap:wrap;gap:22px;margin:15px 0 4px;font-size:12.5px;color:#2b2f36}
 .legend span{display:inline-flex;align-items:center;gap:7px}
 .foot{font-size:12px;color:#5b6169;margin-top:16px;line-height:1.55;background:#fff;border:1px solid #e6e8ec;border-left:3px solid #9aa4b0;border-radius:8px;padding:12px 14px}
 .foot b{color:#1e2227}
 .tabs{display:flex;gap:6px;margin:0 0 20px;border-bottom:2px solid #e6e8ec}
 .tab{background:none;border:none;padding:9px 18px;font-size:14.5px;font-weight:560;color:#5b6169;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px}
 .tab:hover{color:#1e2227}
 .tab.active{color:#1e2227;border-bottom-color:#2471a3}
</style></head><body><div class="wrap">
<h1>Rep-rate cost breakdown &mdash; IFE economics</h1>
<p class="sub">All at 1&nbsp;GWe / 0.85 availability, in $/MWh. Hover for values.</p>
<div class="tabs">
 <button class="tab active" onclick="showTab(event,'models')">Three economic models</button>
 <button class="tab" onclick="showTab(event,'concepts')">1costingFE by concept</button>
</div>
<div id="tab-models">
<div style="background:#f4f8fc;border-left:3px solid #2471a3;padding:10px 14px;margin:0 0 16px;font-size:13.5px;color:#2c333b;border-radius:4px">
 All three panels assume a <b>generalized DPSSL driver</b> (direct-drive diode-pumped solid-state laser) applied identically to each model &mdash; this tab isolates <i>model-to-model</i> differences, <b>not</b> driver choice. Specific drivers and concepts (KrF, fiber, MagLIF, &hellip;) are broken out on the <b>1costingFE by concept</b> tab.
</div>
<div class="row">
 <div class="col"><div class="card"><div id="gem" style="height:430px"></div></div></div>
 <div class="col"><div class="card"><div id="fe" style="height:430px"></div></div></div>
 <div class="col"><div class="card"><div id="haw" style="height:430px"></div></div></div>
</div>
<div class="legend">
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#f5333f" stroke-width="2.8"/></svg>driver capital</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#f5333f" stroke-width="2.8" stroke-dasharray="6,3"/></svg>replacement costs</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#1e90ff" stroke-width="2.8"/></svg>reaction chamber</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#7a8697" stroke-width="2.8"/></svg>balance of plant</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#c13bff" stroke-width="2.8"/></svg>targets / consumable</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#12c25a" stroke-width="2.8"/></svg>O&amp;M</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#111" stroke-width="2.4" stroke-dasharray="2,2.5"/></svg>total LCOE</span>
</div>
<div style="margin-top:8px"><div class="card"><div id="ov" style="height:480px"></div></div></div>
<div class="foot">
 <b>Reading the panels.</b> Each stacked-category panel sums to that model's total LCOE. Categories are mapped to a common palette where they correspond &mdash;
 <span style="color:#f5333f">driver capital</span> (solid) &amp; <span style="color:#f5333f">replacement costs</span> (dashed),
 <span style="color:#1e90ff">reaction chamber</span>, <span style="color:#7a8697">balance of plant</span>,
 <span style="color:#c13bff">targets / consumable</span>, <span style="color:#12c25a">O&amp;M</span>.
 <b>GEM</b> costs its chamber+vacuum-vessel bottom-up (same R&nbsp;&prop;&nbsp;&radic;yield law we use) but has <b>no driver-replacement line</b> (flat 3%-of-capital O&amp;M).
 <b>Hawker</b> has no target-factory line (per-target &delta; only). &nbsp;·&nbsp; Harmonized inputs: 1&nbsp;GWe, 0.85 availability; native gain models (ours &amp; Hawker's Betti curve agree to ~15%). Panels span each model's valid range (GEM cannot reach 1&nbsp;GWe below ~2&nbsp;Hz; 1costingFE caps at ~13&nbsp;Hz on its shot floor).
</div>
</div><!-- /tab-models -->

<div id="tab-concepts" style="display:none">
<div class="legend" style="margin:6px 0 14px">
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#f5333f" stroke-width="2.8"/></svg>driver capital</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#f5333f" stroke-width="2.8" stroke-dasharray="6,3"/></svg>replacement costs</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#1e90ff" stroke-width="2.8"/></svg>reaction chamber</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#7a8697" stroke-width="2.8"/></svg>balance of plant</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#c13bff" stroke-width="2.8"/></svg>targets / consumable</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#12c25a" stroke-width="2.8"/></svg>O&amp;M</span>
  <span><svg width="28" height="8"><line x1="1" y1="4" x2="27" y2="4" stroke="#111" stroke-width="2.4" stroke-dasharray="2,2.5"/></svg>total LCOE</span>
</div>
<div class="row">
 <div class="col"><div class="card"><div id="c_blf" style="height:400px"></div></div></div>
 <div class="col"><div class="card"><div id="c_xcimer" style="height:400px"></div></div></div>
</div>
<div class="row" style="margin-top:16px">
 <div class="col"><div class="card"><div id="c_inertia" style="height:400px"></div></div></div>
 <div class="col"><div class="card"><div id="c_focused" style="height:400px"></div></div></div>
</div>
<div class="row" style="margin-top:16px">
 <div class="col"><div class="card"><div id="c_maglif" style="height:400px"></div></div></div>
 <div class="col"></div>
</div>
<div class="foot">
 <b>Five D-T fusion concepts, all costed by 1costingFE</b> with identical plant assumptions (1&nbsp;GWe, 0.85 availability, <b>single chamber</b> for all &mdash; including MagLIF, for methodological parity), differing only in <b>driver, drive mode, and wall</b>. Fast-ignition concepts (Focused Energy) carry a gain credit (~1.5&times; central-hot-spot); direct-drive concepts run an honest HAPL dry wall (f_wall=1). Same palette as the model tab; open circle marks each concept's LCOE-optimal rep rate.
 &nbsp;·&nbsp; <b>Xcimer</b> (cheap KrF driver, $40/J) bottoms out lowest and at low rep (~2&nbsp;Hz) &mdash; its economic case rides on that aggressive driver cost.
 <b>BLF</b> is shown with both a <b>dry</b> and a <b>liquid (wet)</b> wall, now with a <b>wall-dependent first-wall life</b> (dry&nbsp;2.5&nbsp;FPY, advanced&nbsp;4, thick-liquid&nbsp;~plant-life) rather than the stock flat 5&nbsp;FPY. The wet wall shrinks the <span style="color:#1e90ff">chamber</span>, pulls the optimum from ~12&nbsp;Hz back to ~5&nbsp;Hz, and nearly zeroes first-wall <span style="color:#f5333f">replacement</span>. Note the gap widens <b>mostly by penalizing the dry wall</b>, not crediting the liquid one (whose FW replacement was already small &mdash; so liquid is not over-credited). <i>And the liquid wall's own hidden costs are still NOT charged here:</i> recirculating pump power (parasitic load), FLiBe/PbLi inventory + primary-loop capital, tritium extraction, and chamber vapor/droplet clearing between shots &mdash; real costs, not just risk, so the wet wall's true net edge is smaller than these panels show.
 <b>Inertia</b>'s indirect (hohlraum) drive inflates both the <span style="color:#f5333f">driver</span> (poorer coupling &rarr; bigger driver) and the <span style="color:#c13bff">target</span> line.
 <b>Focused Energy</b> keeps the same DPSSL laser but switches to <b>direct drive</b> (fast ignition): better coupling shrinks the <span style="color:#f5333f">driver</span> versus the hohlraum case, so it lands between BLF and Inertia (wall assumed advanced-solid).
 <b>MagLIF</b> is now sized like the lasers (single chamber): a near-free cap-bank <span style="color:#f5333f">driver</span> with a <span style="color:#c13bff">consumable</span> (recyclable transmission line + liner) that rises with rep, so its optimum sits at low rep &mdash; competitive on <i>cost</i>.
 <b>Zap</b> (sheared-flow Z-pinch) is the other pulsed-power concept &mdash; a near-free cap-bank <span style="color:#f5333f">driver</span> and cheap chamber, but at a <b>fixed gain</b> its per-shot electrode <span style="color:#c13bff">consumable</span> climbs with rep, so like MagLIF it optimizes at <b>low rep (~0.5&nbsp;Hz)</b>, cost-competitive &mdash; with the same fixed-gain / pulsed-power feasibility risk not priced here.
 &nbsp;·&nbsp; Driver&nbsp;= laser C220104 or pulsed-power cap-bank C220107; chamber&nbsp;= FW/blanket&nbsp;+&nbsp;shield&nbsp;+&nbsp;vessel. <b>Cost only.</b> The real MagLIF risk is not priced here and lives on the <span style="color:#f5333f">driver</span>: every shot delivers a ~100&nbsp;MJ current pulse through a <i>consumed</i> transmission line to a single liner &mdash; the part that does not scale or rep-rate like external laser beams (feasibility, not $).
</div>
</div><!-- /tab-concepts -->
</div>
<script>
const GEM=__GEM__, FE=__FE__, HAW=__HAW__;
const CO={driver:"#f5333f",replace:"#f5333f",chamber:"#1e90ff",yieldv:"#1e90ff",bop:"#7a8697",plant:"#7a8697",other:"#7a8697",targets:"#c13bff",fuel:"#c13bff",target:"#c13bff",om:"#12c25a"};
const DASH=new Set(["replace"]);
const NM={driver:"driver capital",replace:"replacement costs",chamber:"reaction chamber",yieldv:"reaction chamber",bop:"balance of plant",plant:"balance of plant",other:"balance of plant",targets:"targets / consumable",fuel:"targets / consumable",target:"targets / consumable",om:"O&M"};
// shared tick style; per-panel ranges applied below
const XT=[0.05,0.1,0.2,0.5,1,2,5,10,20], XL=["0.05","0.1","0.2","0.5","1","2","5","10","20"];
const YT=[0.5,1,2,5,10,20,50,100,200], YL=["0.5","1","2","5","10","20","50","100","200"];
const XAX={type:"log",title:{text:"rep rate [Hz]"},gridcolor:"#edeff2",tickvals:XT,ticktext:XL,zeroline:false,ticklen:4};
function panel(div,data,keys,title,xr){
 const tr=keys.map(k=>({x:data.f,y:data[k],mode:"lines+markers",name:NM[k],
   line:{color:CO[k],width:2,dash:DASH.has(k)?"dash":"solid"},marker:{size:5}}));
 const tot={x:data.f,y:data.total,mode:"lines",name:"TOTAL LCOE",line:{color:"#111",width:2.5,dash:"dot"}};
 Plotly.newPlot(div,[...tr,tot],{
  title:{text:title,font:{size:14},x:0.02,xanchor:"left"},
  xaxis:Object.assign({},XAX,{range:xr}),
  yaxis:{type:"log",title:{text:"LCOE contribution [$/MWh]"},gridcolor:"#edeff2",range:[Math.log10(0.4),Math.log10(320)],tickvals:YT,ticktext:YL,zeroline:false,ticklen:4},
  margin:{t:36,r:12,b:40,l:56},showlegend:false,
  paper_bgcolor:"#fff",plot_bgcolor:"#fff"},{responsive:true,displayModeBar:false});
}
const RG=[Math.log10(1.8),Math.log10(22)], RF=[Math.log10(0.27),Math.log10(14.5)], RH=[Math.log10(0.045),Math.log10(22)];
panel("gem",GEM,["driver","chamber","bop","om","fuel"],"LLNL GEM",RG);
panel("fe",FE,["driver","chamber","replace","targets","om","other"],"1costingFE",RF);
panel("haw",HAW,["driver","replace","yieldv","plant","target","om"],"Hawker 2020 (gain model)",RH);

// overlay
const OPT=[["#c0392b",13,191.5,"GEM opt ~13 Hz",8,-32],["#2471a3",6,102.1,"1costingFE opt ~5-7 Hz",0,36],["#16a085",0.3,122.7,"Hawker opt ~0.3 Hz",-4,-34]];
const ov=[
 {x:GEM.f,y:GEM.total,mode:"lines+markers",name:"LLNL GEM",line:{color:"#c0392b",width:3},marker:{size:6}},
 {x:FE.f,y:FE.total,mode:"lines+markers",name:"1costingFE",line:{color:"#2471a3",width:3},marker:{size:6}},
 {x:HAW.f,y:HAW.total,mode:"lines+markers",name:"Hawker 2020",line:{color:"#16a085",width:3},marker:{size:6}},
 {x:OPT.map(o=>o[1]),y:OPT.map(o=>o[2]),mode:"markers",marker:{size:15,symbol:"circle-open",color:OPT.map(o=>o[0]),line:{width:2.5,color:OPT.map(o=>o[0])}},showlegend:false,hoverinfo:"skip"},
];
Plotly.newPlot("ov",ov,{
 title:{text:"Full LCOE vs rep rate — three models (generalized DPSSL driver)",font:{size:16},x:0.02,xanchor:"left"},
 xaxis:Object.assign({},XAX,{range:[Math.log10(0.045),Math.log10(22)],title:{text:"repetition rate [Hz]"}}),
 yaxis:{type:"log",title:{text:"plant LCOE [$/MWh]"},gridcolor:"#edeff2",range:[Math.log10(80),Math.log10(830)],tickvals:[80,100,150,200,300,500,800],ticktext:["80","100","150","200","300","500","800"],zeroline:false,ticklen:4},
 annotations:OPT.map(o=>({x:Math.log10(o[1]),y:Math.log10(o[2]),text:o[3],showarrow:true,arrowhead:2,ax:o[4],ay:o[5],font:{size:11.5,color:o[0]},arrowcolor:o[0]})),
 margin:{t:48,r:22,b:52,l:66},legend:{font:{size:12},x:0.99,y:0.98,xanchor:"right",bgcolor:"rgba(255,255,255,0.82)"},paper_bgcolor:"#fff",plot_bgcolor:"#fff"},
 {responsive:true,displayModeBar:false});

// ---- 1costingFE by-concept tab ----
const CONC=__CONC__, COPT=__COPT__;
const CKEYS=["driver","chamber","replace","targets","om","other"];
const YTC=[0.5,1,2,5,10,20,50,100,200,500], YLC=["0.5","1","2","5","10","20","50","100","200","500"];
function panelC(div,d,title,xr,opt){
 const tr=CKEYS.map(k=>({x:d.f,y:d[k],mode:"lines+markers",name:NM[k],
   line:{color:CO[k],width:2,dash:DASH.has(k)?"dash":"solid"},marker:{size:5}}));
 const tot={x:d.f,y:d.total,mode:"lines",name:"TOTAL LCOE",line:{color:"#111",width:2.5,dash:"dot"}};
 const mk={x:[opt[0]],y:[opt[1]],mode:"markers",marker:{size:14,symbol:"circle-open",color:"#111",line:{width:2}},showlegend:false,hoverinfo:"skip"};
 Plotly.newPlot(div,[...tr,tot,mk],{
  title:{text:title,font:{size:13.5},x:0.02,xanchor:"left"},
  xaxis:Object.assign({},XAX,{range:xr}),
  yaxis:{type:"log",title:{text:"LCOE contribution [$/MWh]"},gridcolor:"#edeff2",range:[Math.log10(0.4),Math.log10(520)],tickvals:YTC,ticktext:YLC,zeroline:false,ticklen:4},
  annotations:[{x:Math.log10(opt[0]),y:Math.log10(opt[1]),text:"opt ~"+opt[0]+" Hz · $"+Math.round(opt[1])+"/MWh",showarrow:true,arrowhead:2,ax:0,ay:-30,font:{size:11,color:"#111"}}],
  margin:{t:34,r:12,b:38,l:56},showlegend:false,paper_bgcolor:"#fff",plot_bgcolor:"#fff"},{responsive:true,displayModeBar:false});
}
const RL=[Math.log10(0.27),Math.log10(14.5)], RM=[Math.log10(0.25),Math.log10(7.5)];
panelC("c_blf",CONC.blf,"BLF — fiber · direct · dry wall",RL,COPT.blf);
panelC("c_xcimer",CONC.xcimer,"Xcimer — KrF · hybrid · liquid wall",RL,COPT.xcimer);
panelC("c_inertia",CONC.inertia,"Inertia — DPSSL · indirect · dry wall",RL,COPT.inertia);
panelC("c_focused",CONC.focused,"Focused Energy — DPSSL · proton fast-ignition · dry wall",RL,COPT.focused);
panelC("c_maglif",CONC.maglif,"MagLIF — cap-bank · magnetic direct · metal liner",RM,COPT.maglif);

function showTab(ev,t){
 document.getElementById("tab-models").style.display   = (t=="models")?"block":"none";
 document.getElementById("tab-concepts").style.display = (t=="concepts")?"block":"none";
 document.querySelectorAll(".tab").forEach(b=>b.classList.remove("active"));
 ev.currentTarget.classList.add("active");
 const ids = (t=="models")?["gem","fe","haw","ov"]:["c_blf","c_xcimer","c_inertia","c_focused","c_maglif"];
 ids.forEach(id=>Plotly.Plots.resize(id));
}
</script></body></html>"""
HTML = (HTML.replace("__GEM__", json.dumps(GEM)).replace("__FE__", json.dumps(FE))
        .replace("__HAW__", json.dumps(HAW))
        .replace("__CONC__", json.dumps(CONC)).replace("__COPT__", json.dumps(COPT)))
out = r"c:\Users\mallo\Deterministic_Concept_scoring\three_model_breakdown.html"
open(out, "w", encoding="utf-8").write(HTML)
print("saved:", out)
