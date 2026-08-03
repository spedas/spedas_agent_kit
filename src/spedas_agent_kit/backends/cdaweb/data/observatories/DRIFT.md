# CDF/Skeleton Drift Registry — cdaweb

**Layer**: CDAWeb Master-CDF skeleton drift  
**Catalog root**: `src/spedas_agent_kit/backends/cdaweb/data/observatories/`  
**Host**: 0MASTERS master CDFs at cdaweb.gsfc.nasa.gov (server is case-sensitive)  
**Scan timestamp**: 2026-08-03T05:41:30Z (UTC)  
**Scanner**: `python scripts/scan_drift.py --layer cdaweb` (see README "Periodic catalog drift scans")

## Totals

| metric | value |
|---|---|
| seeded from audit artifacts | 866 checked / 854 ok / 12 drift / 0 fail |
| seed scope | 22/65 observatories (ace..genesis), first audit shard |
| seed source | audit artifacts shard1_results.json + cdaweb_shard1_report.md |
| live checks (this run) | 5 checked / 5 ok / 0 drift / 0 fail |
| registry state | 12 drifted datasets, 0 failed checks |

Drift types: `renamed` | `case_change` | `404` | `param_change` | `date_anomaly`; `fail` = network error / unexpected HTTP status (not a skeleton-drift classification).

## Drifted datasets (top 200)

| dataset_id | observatory/mission | drift_type | detail | first_seen |
|---|---|---|---|---|
| CNOFS_VEFI_LD_500MS | cnofs | case_change | (audit 2026-08-03): NO — master CDF exists but code URL is wrong case (404) | 2026-08-03 |
| DAWN_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2043-10-29T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| EARTH_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| JUPITER_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| MARS_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| MERCURY_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| NEPTUNE_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| PLUTO_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| SATURN_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| URANUS_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| VENUS_HELIO1HR_POSITION | galileo | date_anomaly | catalog stop_date 2035-12-31T23:00:00.000Z >= 2031 (audit 2026-08-03) | 2026-08-03 |
| AC_K0_GIFWALK | ace | param_change | master CDF resolves but only Time variable present (audit 2026-08-03): yes (0 params — Time only) | 2026-08-03 |

## Scan history
Initial snapshot — no previous manifest on disk. All entries are first_seen at their seed/live scan date; subsequent runs classify new / recovered / persistent drift against this snapshot.

## How to run

```bash
python scripts/scan_drift.py --layer cdaweb --limit 50
```
