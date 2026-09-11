"""Hawker (2020) simplified IFE economic model, Phil. Trans. R. Soc. A 378:20200053.
Implements eqs 2.1-2.20. Validated against his published lowest-cost point
(LCOE = $24.6/MWh). Then scans rep rate at fixed 1 GWe for comparison with
1costingFE / GEM.
"""
import numpy as np

SEC_YR = 365 * 24 * 3600.0  # 3.1536e7 s/yr


def gain_betti(E_t_J, mu_c=0.10, V=4.0e5):
    """Betti areal-density gain model, eqs 2.18-2.20. E_t in J -> gain (fusion/E_t)."""
    rho_r = 0.178 * E_t_J ** (1.0 / 3.0)      # kg/m^2 (eq 2.18)
    theta = rho_r / (rho_r + 70.0)            # burn fraction (eq 2.19, H_B=70 kg/m^2)
    return 6.75e14 * theta * mu_c / V ** 2    # eq 2.20


def solve_Ed(P_e_MW, f, p, G_fixed=None):
    """Solve driver bank energy E_d [J] for net power P_e at frequency f.
    Power cascade (eqs 2.12-2.16): P_e = mu_th*(E_b*G*E_t*f - 2*E_d*f), E_t=mu_d*E_d."""
    P_e = P_e_MW * 1e6  # W
    def net(E_d):
        E_t = p["mu_d"] * E_d
        G = G_fixed if G_fixed is not None else gain_betti(E_t)
        P_fus = G * E_t * f
        P_th = p["E_b"] * P_fus
        P_rc = 2.0 * E_d * f
        return p["mu_th"] * (P_th - P_rc), G
    lo, hi = 1e3, 1e10  # J
    for _ in range(200):
        mid = np.sqrt(lo * hi)
        n, _ = net(mid)
        if n < P_e:
            lo = mid
        else:
            hi = mid
    E_d = np.sqrt(lo * hi)
    _, G = net(E_d)
    return E_d, G


def lcoe(P_e_MW, f, p, G_fixed=None):
    E_d, G = solve_Ed(P_e_MW, f, p, G_fixed)          # J, -
    E_t = p["mu_d"] * E_d
    E_f_GJ = G * E_t / 1e9                              # fusion energy/shot [GJ]
    N_y = SEC_YR * f * p["mu_a"]                        # shots/yr (eq 2.9)
    P_e_kW = P_e_MW * 1e3
    # capital ($): plant + yield-vessel + driver (eqs 2.4-2.6)
    C_p = p["alpha"] * P_e_kW
    C_y = p["beta"] * E_f_GJ
    C_d = p["gamma"] * E_d
    cap_total = C_p + C_y + C_d
    # annual operating ($/yr): target + O&M (eqs 2.10-2.11)
    C_t = p["delta"] * N_y
    C_om = p["eps"] * P_e_kW
    op_annual = C_t + C_om
    # driver replacement every L_d yrs (eqs 2.7-2.8)
    L_d = p["N_d"] / N_y
    E_op_MWh = P_e_MW * 8760.0 * p["mu_a"]              # MWh/yr (eq 2.2)
    Yc, Nop, d = 5, 40, p["d"]
    num = den = 0.0
    for i in range(1, Yc + Nop + 1):
        disc = (1 + d) ** i
        C_i = 0.0
        if i <= Yc:                       # construction: spread capital over Yc yrs
            C_i += cap_total / Yc
        else:                             # operation
            C_i += op_annual
            if L_d > 0 and (i - Yc) % max(L_d, 1e-9) < 1.0 and (i - Yc) >= L_d:
                C_i += C_d                # driver replacement event
            den += E_op_MWh / disc
        num += C_i / disc
    return num / den, dict(E_d_MJ=E_d / 1e6, G=G, E_f_GJ=E_f_GJ, N_y=N_y, L_d=L_d)


# ---- nominal base parameter set (Section 3b) ----
BASE = dict(alpha=3000.0, gamma=5.0, delta=10.0, beta=5.0e6, d=0.08, mu_a=0.70,
            mu_th=0.40, mu_d=0.10, E_b=1.2, N_d=50e6, eps=30.0)
# ---- his lowest-cost point (should give ~$24.6/MWh) ----
LOW = dict(alpha=1500.0, gamma=3.0, delta=2.0, beta=5.0e6, d=0.04, mu_a=0.80,
           mu_th=0.50, mu_d=0.20, E_b=1.2, N_d=40e6, eps=20.0)

# validation: his lowest point, E_t=5 MJ, f=0.05, G=1000 -> ~147.5 MWe, $24.6/MWh
val, info = lcoe(147.5, 0.05, LOW, G_fixed=1000.0)
print(f"VALIDATION (Hawker lowest point): LCOE = ${val:.1f}/MWh  (paper: $24.6)  "
      f"E_d={info['E_d_MJ']:.1f}MJ")
print()

# ---- rep-rate scan at 1 GWe, base params ----
print("Rep-rate scan @ 1 GWe (Hawker base params):")
print(f"{'f_Hz':>6} {'LCOE_fixedG500':>15} {'LCOE_gainmodel':>15} {'G(model)':>9} {'E_d_MJ':>8} {'Ef_GJ':>7}")
for f in [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]:
    lf, _ = lcoe(1000.0, f, BASE, G_fixed=500.0)
    lg, ig = lcoe(1000.0, f, BASE)
    print(f"{f:6.2f} {lf:15.1f} {lg:15.1f} {ig['G']:9.0f} {ig['E_d_MJ']:8.1f} {ig['E_f_GJ']:7.2f}")
