# Pulsed Power Corridor

Techno-economic analysis of the pulsed-power route to low-cost fusion: laser and
magneto-inertial concepts costed bottom-up on 1costingFE at 1 GWe, with an evidence-tier
LCOE ladder, single-lever sensitivity, and a shared driver-cost landscape across the
field.

Companion to the [1cFE](https://1cf.energy) corridor dispatch of the same name.

## Result

Two configurations are carried, because the two ends of the rep-rate axis fail
differently: the fiber/direct concept carries its cost in the driver and the wall, the
KrF/hybrid concept in the consumable.

| Evidence tier | fiber / direct, 10 Hz | KrF / hybrid, 1 Hz |
|---|---|---|
| 0 · design baseline | $115.4 | $125.5 |
| 1 · applicable record | $99.2 | $106.3 |
| 2 · extrapolation with a known mechanism | $47.6 | $53.1 |
| 3 · speculation, no mechanism | **$24.2** | **$30.1** |

All figures $/MWh. Neither configuration reaches the 1 ¢/kWh ($10/MWh) target, and both
clear $20/MWh only on full speculation.

One convention was brought to the published article on 30 September 2026. The nominal indirect-cost fraction is held at the NETL 20% on every rung and only the build time moves what is charged (CAS30 = fraction × CAS20 × build / 6 yr, so 20 / 16.7 / 10.8 / 8.3% effective at 6 / 5 / 3.25 / 2.5 years), the convention the aneutronic studies use; the earlier 20 / 16 / 12 / 8% ladder charged the schedule twice. The design basis is costed at the current wall-plug efficiencies, 20% fiber and 7% KrF (`eta_source` defaults), and the ladder lifts them to the published ceilings, 25% and 10%, at the speculation tier. Tier 3 had priced lights-out operation (fixed O&M × 0.0855) here alone; it now holds the tier-2 −55% like the other two D-T ladders, which moves the floor from 21.7 / 27.4 to 24.2 / 30.1 $/MWh (2.4 / 3.0 ¢/kWh).

## Reproducing

The analysis runs against a specific 1costingFE commit plus a patch; the patch carries
model changes that are not on `master`. The committed `*.json` datasets are the ones the
published figures were drawn from, so the figure scripts run standalone without
re-solving anything.

```bash
git clone https://github.com/1cFE/Pulsed_Power_Corridor
cd Pulsed_Power_Corridor

python corridor_tiers.py            # evidence ladder -> corridor_tiers.json
python tier_ladder_figs.py          # figures/pulsed_tier_ladder.png
python pulsed_tornado_plot.py       # figures/pulsed_tornado.png
```

`corridor_tiers.py` should print:

```
PULSED POWER  --  fiber/direct at 10 Hz and KrF/hybrid at 1 Hz, 1 GWe
rung                    fiber/direct    KrF/hybrid
0: design baseline             115.4         125.5
1: records                      99.2         106.3
2: extrapolations               47.6          53.1
3: speculation                  24.2          30.1
```

To re-derive the underlying cost points rather than use the committed datasets, you need
1costingFE on disk:

```bash
git clone https://github.com/1cFE/1costingfe
cd 1costingfe && git checkout 4c7f0df
git apply ../Magnetic_DT_Corridor/costingfe-mature-corridor.patch
cd ../Pulsed_Power_Corridor
export COSTINGFE_SRC=../1costingfe/src    # Windows: set COSTINGFE_SRC=..\1costingfe\src
python pulsed_corridor.py
```

The patch lives in the [Magnetic_DT_Corridor](https://github.com/1cFE/Magnetic_DT_Corridor)
repository; its laser-IFE driver terms — KrF `$/J` raised to a published NOAK figure, and
a gas-laser rep-rate BoP penalty — are the parts that matter here.

### A note on the pin

The commit above is pinned deliberately. `master` has moved on, but the drift for this
corridor is small and not in the direction you might expect from the mature corridor:

| Concept | pinned `4c7f0df` | `master` at `44434d9` | |
|---|---|---|---|
| LASER_IFE | $122.79/MWh | $124.61/MWh | +1.5% |
| MAGLIF | *not sizeable* | $333.77/MWh | — |
| TOKAMAK (for reference) | $111.15/MWh | $108.87/MWh | -2.1% |

The large recent change on `master` -- ICRF repriced from $4.38/MW to $1.00/MW, LHCD from
$4.23 to $1.00 -- moves the **tokamak** baseline and barely touches laser IFE, which
carries no ICRF or NBI: its heating is the driver. Between `6276a84` and `master` the
LASER_IFE number moves only 0.08%. `size_from_power` did not support MAGLIF at `4c7f0df`,
so that row has no pinned value; between `6276a84` and `master` it moves +0.9%.

Nothing in this repository depends on which commit you use -- the committed datasets are
the ones the published figures were drawn from. The pin matters only if you re-derive the
cost points yourself.

## What each file does

| File | Role |
|---|---|
| `corridor_tiers.py` | The shared evidence-tier engine across all three 1cFE corridors. One tier vocabulary applied to whichever levers each corridor's model exposes. Writes `corridor_tiers.json`. |
| `ct_tornado.py` | Reduced cost model over the exported CAS accounts, plus the lever definitions. Reproduces the full 1costingFE LCOE at baseline to the cent. |
| `tier_ladder_figs.py` | The cumulative tier-ladder bar chart. Trimmed here to the pulsed corridor; the mature and revenue ladders live in their own repositories. |
| `pulsed_tornado_plot.py` | Single-lever sensitivity: each of fourteen cost-down levers from the tier-0 basis to its deepest tier, for both configurations. |
| `pulsed_corridor.py` | The 1costingFE sweep behind the committed datasets. Needs `COSTINGFE_SRC`. |
| `hawker_model.py` | A port of the Hawker (2020) gain-based IFE cost model, used as one of the three cross-check models. |
| `build_three_model_html.py` | Builds the rep-rate breakdown across LLNL GEM, 1costingFE and Hawker, all on a common generalized DPSSL driver so the comparison isolates model-to-model differences rather than driver choice. |
| `tools/pulsed_landscape.html` | Interactive landscape: net-power margin and annual consumable cost against a shared driver-cost axis. |
| `tools/three_model_breakdown.html` | Interactive rep-rate cost breakdown across the three models. |
| `tools/pulsed_corridor_tool.html` | Interactive corridor explorer. |

Open the tools directly in a browser — each is a single self-contained file.

## A note on shared files

`corridor_tiers.py`, `ct_tornado.py` and three of the datasets are also present in
[Magnetic_DT_Corridor](https://github.com/1cFE/Magnetic_DT_Corridor). They are duplicated
rather than shared so that either repository can be cloned and run on its own. The tier
engine computes all three corridors from one file, and it loads the mature corridor's
datasets at import, which is why they travel with it.

## Scope and limits

- **Target gain is derived, not measured.** Each concept's gain is approximated by
  assuming its burn follows standard ICF physics for its drive mode and size, scaled from
  driver energy per shot. No concept in this corridor has demonstrated its assumed gain.
- **Consumable costs carry the widest uncertainty of any account here.** Target
  fabrication at rep rate has no industrial precedent, and the figures are component-level
  buildups rather than quotes.
- **The landscape mixes published and estimated driver costs.** Where a company has
  published a figure it is used — Xcimer's $60–80/J on target, MagLIF's driver anchor from
  Pacific Fusion's AMPS paper (arXiv:2504.10680). Where none exists the value is our own
  estimate. These are NOAK projections from companies with a commercial interest in
  appearing cheap. Treat the clustering as meaningful and the individual placements as
  indicative.
- **A technical-feasibility filter is applied.** Only concepts scoring above 2 on the
  fusion-tea composite are shown; heavy-ion ICF, dense plasma focus, wire-array Z-pinch,
  Marvel, sonofusion, MTIF, sheared-flow Z-pinch and piston-MIF are excluded. Helion and
  Zap are covered in other corridors.
- **Chamber survival is not modelled dynamically.** First-wall life enters as a
  replacement cost, not as an availability penalty.

## Contact

Questions or challenges to the assumptions and methodology are welcome at
[1cf.energy/contact](https://1cf.energy/contact).

## License

Original code and associated documentation in this repository are available under the [MIT License](LICENSE), copyright 2026 Astera Institute, consistent with [Astera's Open Science Policy](https://astera.org/open-science-policy/). Third-party material retains its original copyright and license.
