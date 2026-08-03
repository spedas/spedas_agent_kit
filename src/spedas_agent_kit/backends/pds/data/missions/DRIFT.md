# CDF/Skeleton Drift Registry — pds

**Layer**: PDS PPI archive slot drift  
**Catalog root**: `src/spedas_agent_kit/backends/pds/data/missions/`  
**Host**: PPI archive slots at pds-ppi.igpp.ucla.edu  
**Scan timestamp**: 2026-08-03T05:41:31Z (UTC)  
**Scanner**: `python scripts/scan_drift.py --layer pds` (see README "Periodic catalog drift scans")

## Totals

| metric | value |
|---|---|
| seeded from audit artifacts | 1171 checked / 1103 ok / 67 drift / 1 fail |
| seed scope | 1171 PPI archive slots across all missions |
| seed source | audit artifact pds_slot_status.json |
| live checks (this run) | 5 checked / 5 ok / 0 drift / 0 fail |
| registry state | 67 drifted datasets, 1 failed checks |

Drift types: `renamed` | `case_change` | `404` | `param_change` | `date_anomaly`; `fail` = network error / unexpected HTTP status (not a skeleton-drift classification).

## Drifted datasets (top 200)

| dataset_id | observatory/mission | drift_type | detail | first_seen |
|---|---|---|---|---|
| pds3:CO-V/E/J/S/SS-RPWS-2-REFDR-ALL-V1.0:ANCILLARY | cassini | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-D-GDDS-5-DUST-V4.1 | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:00_IO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:00_JUPITER | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:01_GANYMEDE | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:02_GANYMEDE | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:03_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:04_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:06_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:07_GANYMEDE | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:08_GANYMEDE | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:09_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:10_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:11_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:12_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:13_JUPITER | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:14_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:15_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:16_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:17_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:18_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:19_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:20_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:21_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:22_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:23_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:24_IO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:25_IO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:26_EUROPA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:27_IO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:28_GANYMEDE | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:29_GANYMEDE | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:30_CALLISTO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:31_IO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:32_IO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:33_IO | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:34_AMALTHEA | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:35_JUPITER | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:GO-J-MAG-2-REDR-RAW-DATA-V1.0:ENG | galileo | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-J-PEPSSI-2-JUPITER-V1.1 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-J-PEPSSI-3-JUPITER-V1.1 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-J-SWAP-2-JUPITER-V4.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-J-SWAP-3-JUPITER-V4.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-P-PEPSSI-2-PLUTO-V3.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-P-PEPSSI-3-PLUTO-V3.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-P-PEPSSI-4-PLASMA-V1.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-P-SWAP-5-DERIVED-SOLARWIND-V1.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-X-PEPSSI-2-LAUNCH-V1.1 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-X-PEPSSI-3-LAUNCH-V1.1 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-X-SWAP-2-LAUNCH-V2.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:NH-X-SWAP-3-LAUNCH-V2.0 | new_horizons | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:ULY-D-UDDS-5-DUST-V3.1 | ulysses | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:ULY-D-UDDS-5-DUST-V3.1:DATA | ulysses | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:VG2-N-MAG-4-RDR-HGCOORDS-1.92SEC-V1.0 | voyager2 | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:VG2-N-MAG-4-RDR-HGCOORDS-1.92SEC-V1.0:DATA | voyager2 | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:VG2-N-MAG-4-RDR-HGCOORDS-9.6SEC-V1.0 | voyager2 | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| pds3:VG2-U-MAG-4-RDR-HGCOORDS-1.92SEC-V1.0 | voyager2 | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-fips-derived:data-erpchang | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-fips-derived:data-espec | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-fips-derived:data-fluxmap | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-fips-derived:data-nobs | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-fips-derived:data-ntp | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-fips-derived:data-pitchang | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-fips-derived:data-rotmso | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-raw:data-long-status | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-epps-raw:data-status | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:mess-mag-field-map:data | messenger | 404 | HTTP 404 at PPI archive slot (audit 2026-08-03) | 2026-08-03 |
| urn:nasa:pds:galileo-mag-jup-raw:data | galileo | fail | slot check ERR_TimeoutError (audit 2026-08-03) | 2026-08-03 |

## Scan history
Initial snapshot — no previous manifest on disk. All entries are first_seen at their seed/live scan date; subsequent runs classify new / recovered / persistent drift against this snapshot.

## How to run

```bash
python scripts/scan_drift.py --layer pds --limit 50
```
