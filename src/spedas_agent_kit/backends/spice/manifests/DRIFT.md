# CDF/Skeleton Drift Registry — spice

**Layer**: SPICE NAIF kernel manifest drift  
**Catalog root**: `src/spedas_agent_kit/backends/spice/manifests/`  
**Host**: NAIF kernel URLs at naif.jpl.nasa.gov  
**Scan timestamp**: 2026-08-03T05:41:31Z (UTC)  
**Scanner**: `python scripts/scan_drift.py --layer spice` (see README "Periodic catalog drift scans")

## Totals

| metric | value |
|---|---|
| seeded from audit artifacts | 1646 checked / 1631 ok / 15 drift / 0 fail |
| seed scope | 15 catalog problems across mission manifests |
| seed source | audit artifact spice_audit_results.json |
| live checks (this run) | 20 checked / 20 ok / 0 drift / 0 fail |
| registry state | 15 drifted datasets, 0 failed checks |

Drift types: `renamed` | `case_change` | `404` | `param_change` | `date_anomaly`; `fail` = network error / unexpected HTTP status (not a skeleton-drift classification).

## Drifted datasets (top 200)

| dataset_id | observatory/mission | drift_type | detail | first_seen |
|---|---|---|---|---|
| naif_id:-140 | multi-mission | param_change | duplicate NAIF ID assignment (identity metadata conflict, audit 2026-08-03): DATA duplicate NAIF ID -140 assigned to: ['DEEP_IMPACT', 'EPOXI'] | 2026-08-03 |
| naif_id:-30 | multi-mission | param_change | duplicate NAIF ID assignment (identity metadata conflict, audit 2026-08-03): DATA duplicate NAIF ID -30 assigned to: ['VIKING_2', 'DEEP_SPACE_1'] | 2026-08-03 |
| naif_id:-5 | multi-mission | param_change | duplicate NAIF ID assignment (identity metadata conflict, audit 2026-08-03): DATA duplicate NAIF ID -5 assigned to: ['AKATSUKI', 'LUNAR_ORBITER_5'] | 2026-08-03 |
| naif_id:4 | multi-mission | param_change | duplicate NAIF ID assignment (identity metadata conflict, audit 2026-08-03): DATA duplicate NAIF ID 4 assigned to: ['MARS', 'MARS_BARYCENTER'] | 2026-08-03 |
| naif_id:5 | multi-mission | param_change | duplicate NAIF ID assignment (identity metadata conflict, audit 2026-08-03): DATA duplicate NAIF ID 5 assigned to: ['JUPITER', 'JUPITER_BARYCENTER'] | 2026-08-03 |
| naif_id:6 | multi-mission | param_change | duplicate NAIF ID assignment (identity metadata conflict, audit 2026-08-03): DATA duplicate NAIF ID 6 assigned to: ['SATURN', 'SATURN_BARYCENTER'] | 2026-08-03 |
| kernel:grail_110910_120102_nav_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_110910_120102_nav_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_110910_120102_nav_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_120102_120301_nav_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_120102_120301_nav_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_120102_120301_nav_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_120301_120529_nav_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_120301_120529_nav_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_120301_120529_nav_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_120301_120529_sci_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_120301_120529_sci_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_120301_120529_sci_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_120301_120529_sci_v02.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_120301_120529_sci_v02.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_120301_120529_sci_v02.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_120529_120830_nav_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_120529_120830_nav_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_120529_120830_nav_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_120830_121026_sci_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_120830_121026_sci_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_120830_121026_sci_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_120830_121217_nav_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_120830_121217_nav_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_120830_121217_nav_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |
| kernel:grail_121026_121214_sci_v01.bsp | grail | renamed | duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): DATA filename 'grail_121026_121214_sci_v01.bsp' used by multiple missions [('GRAIL_A', 'https://naif.jpl.nasa.gov/pub/naif/pds/data/grail-l-spice-6-v1.0/grlsp_1000/data/spk/grail_121026_121214_sci_v01.bsp'), ('GRAIL_B',  | 2026-08-03 |

## Scan history
Initial snapshot — no previous manifest on disk. All entries are first_seen at their seed/live scan date; subsequent runs classify new / recovered / persistent drift against this snapshot.

## How to run

```bash
python scripts/scan_drift.py --layer spice --limit 50
```
