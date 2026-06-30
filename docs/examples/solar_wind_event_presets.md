# Solar-wind event preset seeds

These are documentation-only preset seeds for Agent Kit skills. They are not yet
API-level event presets: use them to plan narrow, artifact-first paper
reproductions, then record exact paper/supplement intervals in provenance.

| Event / paper family | DOI | Starting interval | Data route | Quality label until paper interval confirmed | Skill |
|---|---|---|---|---|---|
| PSP Encounter-1 structured slow wind (Bale et al. 2019) | `10.1038/s41586-019-1818-7` | `2018-11-05/00:00:00`–`2018-11-07/00:00:00` | PSP FIELDS MAG RTN 1-min + SWEAP/SPC L3i | `candidate_interval` | `psp-solar-wind-switchbacks` |
| PSP Encounter-1 Alfvénic velocity spikes (Kasper et al. 2019) | `10.1038/s41586-019-1813-z` | `2018-11-06/00:00:00`–`2018-11-06/12:00:00` | PSP FIELDS MAG RTN + SWEAP/SPC velocity moments | `proxy` | `psp-solar-wind-switchbacks` |
| PSP Encounter-1 switchbacks (Dudok de Wit et al. 2020) | `10.3847/1538-4365/ab5853` | `2018-11-05/00:00:00`–`2018-11-07/00:00:00` | PSP FIELDS MAG RTN, optional SWEAP/SPC context | `proxy` | `psp-solar-wind-switchbacks` |
| PSP Encounter-1 sharp Alfvénic impulses (Horbury et al. 2020) | `10.3847/1538-4365/ab5b15` | `2018-11-06/00:00:00`–`2018-11-06/06:00:00` for cache-friendly smoke; replace with paper figure interval when known | PSP FIELDS MAG RTN + SWEAP/SPC velocity moments | `representative_proxy` | `psp-solar-wind-switchbacks` |
| PSP Encounter-1 PVI/intermittent structures (Chhiber et al. 2020) | `10.3847/1538-4365/ab53d2` | `2018-11-06/00:00:00`–`2018-11-06/03:00:00` smoke interval | PSP FIELDS MAG RTN, optional SWEAP/SPC context | `cached_smoke` until lag/cadence/threshold match the paper | `psp-solar-wind-switchbacks` + `solar-wind-turbulence-spectrum` |
| PSP inner-heliosphere turbulence evolution (2020) | `10.3847/1538-4365/ab60a3` | `2018-11-05/12:00:00`–`2018-11-05/18:00:00` smoke interval; use paper-selected E1/E2 intervals for science | PSP FIELDS MAG RTN + SWEAP/SPC | `representative_proxy` | `solar-wind-turbulence-spectrum` |
| PSP enhanced energy-transfer/cascade-rate paper (2020) | `10.3847/1538-4365/ab5dae` | `2018-11-06/00:00:00`–`2018-11-06/06:00:00` smoke interval | PSP FIELDS MAG RTN + SWEAP/SPC proton moments | `proxy` unless third-order-law assumptions and lag range are reproduced | `solar-wind-turbulence-spectrum` |
| PSP magnetic field line switchbacks near the Sun (2020) | `10.3847/1538-4365/ab4da7` | `2018-11-05/00:00:00`–`2018-11-05/06:00:00` smoke interval | PSP FIELDS MAG RTN + SWEAP/SPC | `representative_proxy` | `psp-solar-wind-switchbacks` |
| Halloween 2003 extreme-speed solar wind (Skoug et al. 2004) | `10.1029/2004JA010494` | `2003-10-29/00:00:00`–`2003-10-31/00:00:00` | OMNI HRO 1-min + Wind/ACE context | `paper_quality` only if timing/source choices match target figure | `solar-wind-icme-storm` |
| July 2012 STEREO-A extreme ICME (Liu et al. 2014) | `10.1038/ncomms4481` | `2012-07-23/00:00:00`–`2012-07-25/00:00:00` | STEREO-A MAG + PLASTIC 1-min | `candidate_interval` | `solar-wind-icme-storm` |

## Rules for using these seeds

- Keep the `paper-reproduction` artifact/provenance contract: report, provenance
  JSON, plot/table artifacts, and the script or recipe used to regenerate them.
- Do not claim paper quality from a seed interval alone. Promote to
  `paper_quality` only after matching paper interval, source, coordinate basis,
  calibration choices, and diagnostic definitions.
- Record archive variable aliases exactly, for example OMNI `AE_INDEX` and
  `SYM_H`, PSP `psp_fld_l2_mag_RTN_1min`, PSP SPC `psp_spc_np_fit` /
  `psp_spc_vp_fit_RTN`, and STEREO `BFIELD` / PLASTIC proton moment names.
- For PSP turbulence/switchback seeds, record `interval_quality` (`paper_exact`,
  `representative_proxy`, or `cached_smoke`) plus cadence/lag/threshold choices
  in provenance before using the result as Agent Kit feedback.
