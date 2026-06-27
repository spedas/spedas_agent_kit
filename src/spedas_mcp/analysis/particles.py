"""Phase-2 particle analysis tools (issues #18, #19).

Two MCP tools that turn 3D particle velocity distributions into the standard
thermodynamic and spectral observables:

- :func:`compute_particle_moments` (#18) - plasma moments (density, velocity,
  temperature, pressure tensor, heat-flux summaries) from a time series of 3D
  distributions, via ``pyspedas.particles.moments.moments_3d``.
- :func:`compute_particle_spectra` (#19) - energy / azimuth (phi) / elevation
  (theta) spectrograms via ``pyspedas`` ``spd_pgs_make_e_spec`` /
  ``spd_pgs_make_phi_spec`` / ``spd_pgs_make_theta_spec``; field-aligned
  pitch-angle spectra are gated on the (optional) ``spd_pgs_make_pad_spec``
  backend plus a magnetic-field reference.

Design contract (mirrors :mod:`spedas_mcp.analysis.spectral` /
:mod:`spedas_mcp.analysis.fieldmodels`, roadmap epics #5/#9):

- **File-in / file-out, artifact-first.** The input is a path to an explicit
  distribution artifact (``.npz`` preferred; JSON accepted) holding the
  per-slice cubes. Bulk moment time-series and spectrogram matrices are written
  to ``output_dir`` (CSV/JSON for moments, ``.npz`` for spectra). Returns are
  small JSON-serializable dicts with ``status``, file paths, and **scalar
  summaries / ranges / shapes only**. Full particle cubes, pressure tensors, and
  spectrogram matrices are never returned inline.
- **Explicit, documented distribution schema.** Rather than pretend to ingest
  every mission's CDF distribution struct, this module defines one explicit
  schema (see :data:`DIST_SCHEMA_DOC`) that maps 1:1 onto the ``data_in`` dict
  ``moments_3d`` / the ``spd_pgs_make_*`` functions consume. Mission CDFs can be
  bridged into this schema by a future loader (#20-#22); the pyspedas algorithms
  themselves run on the real arrays.
- **Lazy, gated backends.** ``pyspedas`` is imported only inside these
  functions; a missing ``[analysis]`` extra yields a clean
  ``status="error", code="dependency_missing"`` payload. Each pyspedas function
  is additionally checked for *exact* availability before use, because installed
  ``pyspedas`` builds vary (e.g. ``spd_pgs_make_pad_spec`` is absent in some
  releases). A missing-but-required backend yields ``code="unsupported"`` rather
  than a raw ``ImportError``.
- **No network.** All computation is local; the tools never download data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import AnalysisDependencyError, require_pyspedas

# Per-slice distribution fields consumed by the pyspedas particle algorithms.
# ``data``/``energy``/``theta``/``phi``/``dtheta``/``dphi``/``denergy``/``bins``
# are per-slice 2D arrays of shape ``(n_energy, n_angle)``; stacked over time
# they are 3D ``(n_time, n_energy, n_angle)``. ``charge``/``mass`` are scalars.
_SLICE_FIELDS = (
    "data",
    "energy",
    "denergy",
    "theta",
    "dtheta",
    "phi",
    "dphi",
    "bins",
)
_SCALAR_FIELDS = ("charge", "mass")

# Fields each backend strictly requires. moments_3d needs the full set; the
# spectra functions need only the geometry + data they average over.
_MOMENTS_REQUIRED = set(_SLICE_FIELDS) | set(_SCALAR_FIELDS)
_SPECTRA_REQUIRED = {
    "energy": {"data", "energy", "bins"},
    "phi": {"data", "theta", "dtheta", "phi", "dphi", "bins"},
    "theta": {"data", "theta", "dtheta", "dphi", "bins"},
    # pitch_angle additionally needs a mag reference + the (optional) pad backend.
    "pitch_angle": {"data", "energy", "theta", "dtheta", "phi", "dphi", "bins"},
}

# Spectrum types this tool knows about. "azimuth" is accepted as an alias for
# "phi" and "elevation" for "theta" (mission-neutral naming).
_SPECTRUM_ALIASES = {
    "azimuth": "phi",
    "elevation": "theta",
    "pad": "pitch_angle",
    "pitchangle": "pitch_angle",
}
_KNOWN_SPECTRA = ("energy", "phi", "theta", "pitch_angle")

DIST_SCHEMA_DOC = (
    "Distribution artifact schema (file-in). Provide an .npz (preferred) or a "
    "JSON object with these keys: 'times' (T Unix seconds), 'data' (T,E,A flux), "
    "'energy' (T,E,A or E,A eV), 'denergy', 'theta', 'dtheta', 'phi', 'dphi', "
    "'bins' (same shape as 'data'; 1=active, 0=inactive), and scalars 'charge' "
    "(in e) and 'mass' (in eV/(km/s)^2, pyspedas convention). E=energy bins, "
    "A=solid-angle bins. Per-slice 2D fields may be given once (E,A) and are "
    "broadcast across all T slices."
)


class ParticleBackendError(AnalysisDependencyError):
    """Raised when a required pyspedas particle backend function is unavailable."""


def _error(
    message: str,
    *,
    code: str = "invalid_argument",
    hint: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build the uniform structured error payload for analysis tools.

    Mirrors :func:`spedas_mcp.analysis.spectral._error` and the server's
    ``_error_response`` envelope so particle errors share the same
    ``{status: "error", code, message, ...}`` contract (issue #27).
    """
    payload: dict[str, Any] = {"status": "error", "code": code, "message": message}
    if hint is not None:
        payload["hint"] = hint
    payload.update(extra)
    return payload


def _load_distribution(dist_file: str) -> dict[str, Any]:
    """Load the explicit distribution artifact into a dict of numpy arrays/scalars.

    Supports ``.npz`` / ``.npy`` (via numpy) and ``.json`` (object of lists).
    Returns the raw mapping; shape validation/normalization happens in
    :func:`_normalize_distribution`.

    Raises
    ------
    ValueError
        If the file is missing or cannot be parsed into a mapping.
    """
    import numpy as np

    path = Path(dist_file)
    if not path.exists():
        raise ValueError(f"distribution file does not exist: {dist_file}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON distribution must be an object mapping field -> values")
        return {k: (np.asarray(v) if isinstance(v, list) else v) for k, v in payload.items()}

    if suffix in (".npz",):
        with np.load(path, allow_pickle=False) as npz:
            return {k: npz[k] for k in npz.files}

    if suffix in (".npy",):
        raise ValueError(
            ".npy holds a single array; the distribution needs multiple named "
            "fields. Provide an .npz or .json (see schema)."
        )

    raise ValueError(
        f"unsupported distribution file type '{suffix}'; use .npz or .json"
    )


def _normalize_distribution(
    raw: dict[str, Any], required: set[str]
) -> tuple[Any, dict[str, Any], dict[str, Any], int]:
    """Validate fields and reshape per-slice cubes to ``(n_time, n_energy, n_angle)``.

    Returns ``(times, slice_cubes, scalars, n_time)`` where ``slice_cubes`` maps
    each present slice field to a 3D ``(T, E, A)`` array (a single 2D ``(E, A)``
    field is broadcast across T) and ``scalars`` holds charge/mass when present.

    Raises
    ------
    ValueError
        On missing required fields or inconsistent shapes.
    """
    import numpy as np

    missing = sorted(required - set(raw.keys()))
    if missing:
        raise ValueError(
            f"distribution is missing required field(s): {missing}. {DIST_SCHEMA_DOC}"
        )

    data = np.asarray(raw["data"], dtype="float64")
    if data.ndim == 2:
        data = data[np.newaxis, ...]  # single time slice -> (1, E, A)
    if data.ndim != 3:
        raise ValueError(
            f"'data' must be 2D (E,A) or 3D (T,E,A); got shape {tuple(np.shape(raw['data']))}"
        )
    n_time, n_energy, n_angle = data.shape

    # Resolve the time axis (default to an index range when absent).
    if "times" in raw:
        times = np.asarray(raw["times"], dtype="float64").reshape(-1)
        if times.shape[0] != n_time:
            raise ValueError(
                f"'times' length {times.shape[0]} != number of data slices {n_time}"
            )
    else:
        times = np.arange(n_time, dtype="float64")

    cubes: dict[str, Any] = {"data": data}
    for field in _SLICE_FIELDS:
        if field == "data":
            continue
        if field not in raw:
            continue
        arr = np.asarray(raw[field], dtype="float64")
        if arr.ndim == 2:
            if arr.shape != (n_energy, n_angle):
                raise ValueError(
                    f"field '{field}' has 2D shape {arr.shape}; expected "
                    f"({n_energy}, {n_angle}) to match 'data' bins"
                )
            arr = np.broadcast_to(arr, (n_time, n_energy, n_angle)).copy()
        elif arr.ndim == 3:
            if arr.shape != (n_time, n_energy, n_angle):
                raise ValueError(
                    f"field '{field}' has 3D shape {arr.shape}; expected "
                    f"{(n_time, n_energy, n_angle)} to match 'data'"
                )
        else:
            raise ValueError(
                f"field '{field}' must be 2D (E,A) or 3D (T,E,A); got ndim {arr.ndim}"
            )
        cubes[field] = arr

    scalars: dict[str, Any] = {}
    for field in _SCALAR_FIELDS:
        if field in raw:
            scalars[field] = float(np.asarray(raw[field]).reshape(-1)[0])

    return times, cubes, scalars, n_time


def _slice_dict(
    cubes: dict[str, Any], scalars: dict[str, Any], index: int
) -> dict[str, Any]:
    """Assemble the per-slice ``data_in`` dict pyspedas particle functions expect."""
    out: dict[str, Any] = {field: cubes[field][index] for field in cubes}
    out.update(scalars)
    return out


def _finite_range(array: Any) -> list[float] | None:
    """Return ``[min, max]`` over finite values, or ``None`` if none are finite."""
    import numpy as np

    arr = np.asarray(array, dtype="float64")
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    return [float(finite.min()), float(finite.max())]


def _finite_stats(array: Any) -> dict[str, float] | None:
    """Return ``{min, max, mean}`` over finite values, or ``None`` if none finite."""
    import numpy as np

    arr = np.asarray(array, dtype="float64")
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    return {
        "min": float(finite.min()),
        "max": float(finite.max()),
        "mean": float(finite.mean()),
    }


def _require_attr(module_path: str, attr: str) -> Any:
    """Import ``module_path`` and return ``attr``; raise ParticleBackendError if absent.

    Used to gate on the *exact* pyspedas function being present (Batch O lesson:
    package presence does not imply a given function exists in this build).
    """
    import importlib

    try:
        module = importlib.import_module(module_path)
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch
        raise ParticleBackendError(
            f"required pyspedas backend '{module_path}' is unavailable in this "
            f"install (import error: {exc}); upgrade pyspedas (spedas-mcp[analysis])"
        ) from exc
    fn = getattr(module, attr, None)
    if fn is None:
        raise ParticleBackendError(
            f"installed pyspedas lacks '{module_path}.{attr}'; upgrade pyspedas "
            "(spedas-mcp[analysis]) to a build that provides it"
        )
    return fn


# --------------------------------------------------------------------------
# Issue #18 - particle moments
# --------------------------------------------------------------------------

def compute_particle_moments(
    dist_file: str,
    output_dir: str,
    sc_potential_v: float = 0.0,
    energy_range_ev: list[float] | None = None,
    output_format: str = "json",
    no_unit_conversion: bool = False,
) -> dict[str, Any]:
    """Plasma moments (n, V, T, P, q) from a 3D distribution time series (#18).

    Backend: ``pyspedas.particles.moments.moments_3d`` applied per time slice.
    Reads the explicit distribution artifact (see the module ``DIST_SCHEMA_DOC``),
    optionally restricts to ``energy_range_ev`` and applies the spacecraft
    potential ``sc_potential_v``, computes density / velocity / temperature /
    pressure tensor (and heat-flux-related quantities) for each slice, writes the
    full moment time series to ``output_dir`` (CSV or JSON), and returns compact
    **scalar summaries** plus the artifact path only. Full pressure/temperature
    tensors and particle cubes are never returned inline. Requires
    ``spedas-mcp[analysis]``.
    """
    fmt = (output_format or "").strip().lower()
    if fmt not in ("csv", "json"):
        return _error(
            f"unsupported output_format '{output_format}'; use 'csv' or 'json'",
            valid_formats=["csv", "json"],
        )
    if energy_range_ev is not None:
        if len(energy_range_ev) != 2:
            return _error("energy_range_ev must be [min_ev, max_ev]")
        lo, hi = float(energy_range_ev[0]), float(energy_range_ev[1])
        if not (lo < hi):
            return _error(
                f"energy_range_ev min ({lo}) must be < max ({hi})"
            )

    try:
        require_pyspedas()
        moments_3d = _require_attr(
            "pyspedas.particles.moments.moments_3d", "moments_3d"
        )
    except AnalysisDependencyError as exc:
        code = "unsupported" if isinstance(exc, ParticleBackendError) else "dependency_missing"
        return _error(str(exc), code=code)

    try:
        import numpy as np

        raw = _load_distribution(dist_file)
        times, cubes, scalars, n_time = _normalize_distribution(raw, _MOMENTS_REQUIRED)
    except ValueError as exc:
        return _error(str(exc))

    # Pre-compute an energy mask (per-slice) when a range is requested. moments_3d
    # honors only the bins flagged active, so we restrict by zeroing the 'bins'
    # flag outside the band rather than mutating the physical arrays.
    energy_mask_band = None
    if energy_range_ev is not None:
        lo, hi = float(energy_range_ev[0]), float(energy_range_ev[1])
        energy_mask_band = (lo, hi)

    rows: list[dict[str, Any]] = []
    for i in range(n_time):
        slice_in = _slice_dict(cubes, scalars, i)
        if energy_mask_band is not None:
            lo, hi = energy_mask_band
            energy = np.asarray(slice_in["energy"], dtype="float64")
            band = (energy >= lo) & (energy <= hi)
            slice_in["bins"] = np.asarray(slice_in["bins"], dtype="float64") * band

        try:
            m = moments_3d(slice_in, sc_pot=float(sc_potential_v),
                           no_unit_conversion=bool(no_unit_conversion))
        except Exception as exc:  # noqa: BLE001 - convert backend failure to envelope
            return _error(
                f"moments_3d failed on slice {i}: {exc}",
                code="backend_error",
                slice_index=i,
            )

        velocity = np.asarray(m["velocity"], dtype="float64").reshape(-1)
        ptens = np.asarray(m["ptens"], dtype="float64").reshape(-1)  # 6: xx,yy,zz,xy,xz,yz
        ttens = np.asarray(m["ttens"], dtype="float64")  # 3x3
        flux = np.asarray(m["flux"], dtype="float64").reshape(-1)
        rows.append(
            {
                "time": float(times[i]),
                "density": float(m["density"]),
                "vx": float(velocity[0]),
                "vy": float(velocity[1]),
                "vz": float(velocity[2]),
                "avgtemp": float(m["avgtemp"]),
                "txx": float(ttens[0, 0]),
                "tyy": float(ttens[1, 1]),
                "tzz": float(ttens[2, 2]),
                "pxx": float(ptens[0]),
                "pyy": float(ptens[1]),
                "pzz": float(ptens[2]),
                "pxy": float(ptens[3]),
                "pxz": float(ptens[4]),
                "pyz": float(ptens[5]),
                "fx": float(flux[0]),
                "fy": float(flux[1]),
                "fz": float(flux[2]),
            }
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        moments_path = out_dir / "particle_moments.json"
        columns: dict[str, list[float]] = {k: [r[k] for r in rows] for k in rows[0]}
        moments_path.write_text(json.dumps(columns), encoding="utf-8")
    else:
        moments_path = out_dir / "particle_moments.csv"
        import csv

        with moments_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    density = np.array([r["density"] for r in rows], dtype="float64")
    speed = np.array(
        [float(np.sqrt(r["vx"] ** 2 + r["vy"] ** 2 + r["vz"] ** 2)) for r in rows],
        dtype="float64",
    )
    avgtemp = np.array([r["avgtemp"] for r in rows], dtype="float64")
    p_trace = np.array([r["pxx"] + r["pyy"] + r["pzz"] for r in rows], dtype="float64")

    return {
        "status": "success",
        "tool": "compute_particle_moments",
        "moments_file": str(moments_path),
        "output_format": fmt,
        "n_time": int(n_time),
        "time_range": _finite_range(times),
        "sc_potential_v": float(sc_potential_v),
        "energy_range_ev": [float(energy_range_ev[0]), float(energy_range_ev[1])]
        if energy_range_ev is not None
        else None,
        "density_summary": _finite_stats(density),
        "velocity_summary": _finite_stats(speed),
        "temperature_summary": _finite_stats(avgtemp),
        "pressure_tensor_summary": {
            "components": ["pxx", "pyy", "pzz", "pxy", "pxz", "pyz"],
            "trace": _finite_stats(p_trace),
            "note": (
                "Per-slice pressure tensor (6 components) and full 3x3 temperature "
                "tensor are written to the moments artifact; only the scalar "
                "pressure-trace summary is returned inline."
            ),
        },
        "columns": list(rows[0].keys()),
        "note": (
            "Density in cm^-3, velocity in km/s, temperature in eV, pressure in "
            "eV/cm^3 (pyspedas moments_3d units). Full time series in the artifact; "
            "this tool returns scalar summaries only."
        ),
    }


# --------------------------------------------------------------------------
# Issue #19 - particle spectra
# --------------------------------------------------------------------------

def _resolve_spectrum_types(spectrum_types: list[str]) -> tuple[list[str], list[str]]:
    """Map requested spectrum types through aliases; return (resolved, unknown)."""
    resolved: list[str] = []
    unknown: list[str] = []
    for raw in spectrum_types:
        key = (raw or "").strip().lower()
        key = _SPECTRUM_ALIASES.get(key, key)
        if key in _KNOWN_SPECTRA:
            if key not in resolved:
                resolved.append(key)
        else:
            unknown.append(raw)
    return resolved, unknown


def compute_particle_spectra(
    dist_file: str,
    output_dir: str,
    spectrum_types: list[str] | None = None,
    mag_file: str | None = None,
    resolution: int | None = None,
) -> dict[str, Any]:
    """Energy / azimuth / elevation / pitch-angle spectrograms from a distribution (#19).

    Backends: ``pyspedas`` ``spd_pgs_make_e_spec`` (energy), ``spd_pgs_make_phi_spec``
    (azimuth/phi), ``spd_pgs_make_theta_spec`` (elevation/theta). Each averages the
    distribution over the complementary dimensions per time slice to build a
    ``(n_time, n_bin)`` spectrogram. Field-aligned **pitch_angle** spectra require
    both a magnetic-field reference (``mag_file``) and the optional
    ``spd_pgs_make_pad_spec`` backend; when either is missing the pitch-angle
    entry is reported as ``unsupported`` / ``needs_input`` instead of failing the
    whole call.

    Each spectrogram matrix (with its axes) is written to ``output_dir`` as a
    compressed ``.npz``; only paths plus ranges/shapes are returned (artifact-
    first). Requires ``spedas-mcp[analysis]``.
    """
    requested = spectrum_types if spectrum_types is not None else ["energy", "pitch_angle"]
    if not isinstance(requested, list) or not requested:
        return _error("spectrum_types must be a non-empty list of strings")

    resolved, unknown = _resolve_spectrum_types(requested)
    if unknown:
        return _error(
            f"unknown spectrum_type(s): {unknown}",
            code="invalid_argument",
            valid_spectrum_types=list(_KNOWN_SPECTRA),
            accepted_aliases=_SPECTRUM_ALIASES,
        )
    if not resolved:
        return _error("no valid spectrum types requested")
    if resolution is not None and resolution <= 0:
        return _error("resolution must be a positive integer when provided")

    try:
        require_pyspedas()
    except AnalysisDependencyError as exc:
        return _error(str(exc), code="dependency_missing")

    try:
        import numpy as np

        # Only the union of fields actually needed by the resolved spectra is
        # required; this lets a caller compute an energy spectrum from a leaner
        # artifact than a full pitch-angle pipeline would demand.
        needed: set[str] = set()
        for stype in resolved:
            needed |= _SPECTRA_REQUIRED[stype]
        raw = _load_distribution(dist_file)
        times, cubes, scalars, n_time = _normalize_distribution(raw, needed)
    except ValueError as exc:
        return _error(str(exc))

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Map each spectrum type to (module_path, attr, axis_label, axis_units,
    # extra-kwargs builder). Energy/phi/theta are always-present backends; we
    # still gate each on exact availability.
    spec_backends = {
        "energy": (
            "pyspedas.particles.spd_part_products.spd_pgs_make_e_spec",
            "spd_pgs_make_e_spec",
            "energy",
            "eV",
        ),
        "phi": (
            "pyspedas.particles.spd_part_products.spd_pgs_make_phi_spec",
            "spd_pgs_make_phi_spec",
            "phi",
            "deg",
        ),
        "theta": (
            "pyspedas.particles.spd_part_products.spd_pgs_make_theta_spec",
            "spd_pgs_make_theta_spec",
            "theta",
            "deg",
        ),
    }

    spectra_out: dict[str, Any] = {}

    for stype in resolved:
        if stype == "pitch_angle":
            spectra_out["pitch_angle"] = _pitch_angle_entry(mag_file)
            continue

        module_path, attr, axis_label, axis_units = spec_backends[stype]
        try:
            fn = _require_attr(module_path, attr)
        except ParticleBackendError as exc:
            spectra_out[stype] = {"status": "unsupported", "message": str(exc)}
            continue

        rows: list[Any] = []
        axis_ref: Any = None
        try:
            for i in range(n_time):
                slice_in = _slice_dict(cubes, scalars, i)
                if stype == "energy":
                    y, ave = fn(slice_in)
                else:
                    y, ave = fn(slice_in, resolution=resolution)
                if axis_ref is None:
                    axis_ref = np.asarray(y, dtype="float64")
                rows.append(np.asarray(ave, dtype="float64"))
        except Exception as exc:  # noqa: BLE001 - convert backend failure to envelope
            spectra_out[stype] = {
                "status": "error",
                "code": "backend_error",
                "message": f"{attr} failed: {exc}",
            }
            continue

        spectrogram = np.vstack(rows)  # (n_time, n_bin)
        spec_path = out_dir / f"particle_spectra_{stype}.npz"
        np.savez_compressed(
            spec_path,
            time=times,
            axis=axis_ref,
            spectrogram=spectrogram,
        )
        spectra_out[stype] = {
            "status": "success",
            "spectrogram_file": str(spec_path),
            "axis_label": axis_label,
            "axis_units": axis_units,
            "shape": list(spectrogram.shape),
            "axis_range": _finite_range(axis_ref),
            "value_range": _finite_range(spectrogram),
        }

    succeeded = [s for s, v in spectra_out.items() if v.get("status") == "success"]

    return {
        "status": "success" if succeeded else "error",
        "tool": "compute_particle_spectra",
        "spectra": spectra_out,
        "requested": resolved,
        "succeeded": succeeded,
        "n_time": int(n_time),
        "time_range": _finite_range(times),
        "resolution": int(resolution) if resolution is not None else None,
        "note": (
            "Each successful spectrum writes a (n_time, n_bin) matrix to its .npz "
            "under key 'spectrogram' with axes 'time' (Unix seconds) and 'axis' "
            "(energy eV / phi deg / theta deg). Pair with a renderer to view; this "
            "tool returns paths/ranges/shapes only."
        ),
    }


def _pitch_angle_entry(mag_file: str | None) -> dict[str, Any]:
    """Resolve the pitch-angle spectrum status (needs B-field + optional backend).

    Returns a structured per-spectrum entry rather than failing the whole call:
    - ``needs_input`` when ``mag_file`` is absent (FAC requires a B reference);
    - ``unsupported`` when this pyspedas build lacks ``spd_pgs_make_pad_spec``;
    - otherwise a ``not_implemented`` marker (the full FAC pad pipeline is
      intentionally out of scope for this PR and tracked as future work).
    """
    if mag_file is None:
        return {
            "status": "needs_input",
            "code": "needs_input",
            "message": (
                "pitch-angle spectra require a magnetic-field reference for the "
                "field-aligned-coordinate rotation; supply mag_file (an Nx3 B "
                "time series matching the distribution times)."
            ),
        }
    if not Path(mag_file).exists():
        return {
            "status": "error",
            "code": "invalid_argument",
            "message": f"mag_file does not exist: {mag_file}",
        }
    # Exact-availability gate: the pad-spec backend is absent in some pyspedas
    # builds (Batch O lesson). Report unsupported rather than crash.
    import importlib

    pad_mod = "pyspedas.particles.spd_part_products.spd_pgs_make_pad_spec"
    try:
        module = importlib.import_module(pad_mod)
        has_pad = getattr(module, "spd_pgs_make_pad_spec", None) is not None
    except Exception:
        has_pad = False
    if not has_pad:
        return {
            "status": "unsupported",
            "code": "unsupported",
            "message": (
                "this pyspedas build lacks spd_pgs_make_pad_spec; field-aligned "
                "pitch-angle spectra are unavailable. Upgrade pyspedas, or use the "
                "energy/phi/theta spectra which are supported here."
            ),
        }
    # Backend + mag reference present, but the full FAC pad pipeline (do_fac +
    # pad spec wiring) is deliberately deferred so this PR ships honest,
    # validated tools rather than an untested path.
    return {
        "status": "not_implemented",
        "code": "not_implemented",
        "message": (
            "spd_pgs_make_pad_spec is available, but the field-aligned pitch-angle "
            "pipeline (FAC rotation + pad spec) is not yet wired in this tool. "
            "Tracked as future work; energy/phi/theta spectra are supported now."
        ),
    }


__all__ = [
    "DIST_SCHEMA_DOC",
    "ParticleBackendError",
    "compute_particle_moments",
    "compute_particle_spectra",
]
