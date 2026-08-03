"""Parameter metadata — browse dataset variables via local cache or Master CDFs."""

import json
import logging
import re
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MASTER_CDF_BASE = "https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS"

# CDF type string -> parameter type mapping
_CDF_TYPE_MAP = {
    "CDF_REAL4": "double", "CDF_REAL8": "double",
    "CDF_DOUBLE": "double", "CDF_FLOAT": "double",
    "CDF_INT1": "integer", "CDF_INT2": "integer",
    "CDF_INT4": "integer", "CDF_INT8": "integer",
    "CDF_UINT1": "integer", "CDF_UINT2": "integer",
    "CDF_UINT4": "integer", "CDF_BYTE": "integer",
}

_SKIP_TYPES = {
    "CDF_EPOCH", "CDF_EPOCH16", "CDF_TIME_TT2000",
    "CDF_CHAR", "CDF_UCHAR",
}


def get_cache_dir() -> Path:
    """Return the metadata cache directory."""
    from spedas_agent_kit.backends.cdaweb.config import get_cache_root
    return get_cache_root() / "metadata"


def browse_parameters(
    dataset_id: str | None = None,
    dataset_ids: list[str] | None = None,
) -> dict:
    """Browse parameters for one or more datasets.

    Resolution chain:
    1. Local metadata cache (~/.cdawebmcp/metadata/{dataset_id}.json)
    2. Master CDF download from CDAWeb (fallback, then cached)

    Args:
        dataset_id: Single dataset ID.
        dataset_ids: Multiple dataset IDs for batch lookup.

    Returns:
        Dict with status and parameter metadata.
    """
    ids: list[str] = []
    if dataset_ids:
        ids = dataset_ids
    elif dataset_id:
        ids = [dataset_id]

    if not ids:
        return {"status": "error", "message": "Missing required parameter: dataset_id or dataset_ids"}

    results: dict[str, dict] = {}
    for ds_id in ids:
        try:
            info = _resolve_metadata(ds_id)
            params = [p for p in info.get("parameters", [])
                      if p.get("name", "").lower() != "time"]
            entry: dict = {"status": "success", "parameters": params}
            start = info.get("startDate", "")
            stop = info.get("stopDate", "")
            if start or stop:
                entry["time_range"] = {"start": start, "stop": stop}
            # Add validation status if available
            try:
                from spedas_agent_kit.backends.cdaweb.validation import get_quality_report
                from spedas_agent_kit.backends.cdaweb.catalog import get_observatory_stem_from_dataset
                obs_stem = get_observatory_stem_from_dataset(ds_id)
                if obs_stem:
                    report = get_quality_report(ds_id, mission_stem=obs_stem)
                    if report:
                        entry["validated"] = report["validated"]
                        entry["quality_report"] = report
            except Exception:
                pass
        except Exception as e:
            logger.warning("Could not load parameters for %s: %s", ds_id, e)
            entry = {
                "status": "error",
                "parameters": [],
                "error": str(e),
                "hint": (
                    "Parameter metadata could not be resolved (no cached metadata "
                    "and the Master CDF was unavailable). Check the dataset_id "
                    "and network access to CDAWeb, then retry."
                ),
            }
        results[ds_id] = entry

    # Flatten for single-dataset calls
    if len(results) == 1:
        ds_id, entry = next(iter(results.items()))
        return {"dataset_id": ds_id, **entry}

    failed = [ds_id for ds_id, entry in results.items()
              if entry.get("status") != "success"]
    status = "error" if failed and len(failed) == len(results) else "success"
    return {"status": status, "datasets": results}


def _resolve_metadata(dataset_id: str) -> dict:
    """Resolve parameter metadata: local cache first, then Master CDF.

    Side effect: caches the result locally after Master CDF download.
    """
    cache_dir = get_cache_dir()
    cache_file = cache_dir / f"{dataset_id}.json"

    # Try local cache
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: Master CDF
    info = _fetch_from_master_cdf(dataset_id)
    if info is None:
        raise RuntimeError(f"Could not fetch metadata for {dataset_id}")

    # Cache the result
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

    return info


def _fetch_from_master_cdf(dataset_id: str) -> dict | None:
    """Download a Master CDF skeleton and extract parameter metadata."""
    try:
        import cdflib
    except ImportError:
        raise RuntimeError("cdflib is required for Master CDF reading")

    from spedas_agent_kit.backends.cdaweb.http import request_with_retry

    # CDAWeb's 0MASTERS server is case-sensitive: 45 of 4409 master filenames
    # contain uppercase letters (e.g. cnofs_vefi_LD_500ms_00000000_v01.cdf), so
    # lowercasing the dataset ID unconditionally 404s those.  Try the original
    # dataset_id casing first, then fall back to lowercase for the (majority)
    # all-lowercase master filenames.
    candidate_urls = [f"{MASTER_CDF_BASE}/{dataset_id}_00000000_v01.cdf"]
    lowered = dataset_id.lower()
    if lowered != dataset_id:
        candidate_urls.append(f"{MASTER_CDF_BASE}/{lowered}_00000000_v01.cdf")

    resp = None
    for url in candidate_urls:
        logger.info("Downloading Master CDF: %s", url)
        try:
            resp = request_with_retry(url)
            break
        except Exception as e:
            logger.warning("Master CDF download failed for %s: %s", dataset_id, e)
    if resp is None:
        return None

    # Write to temp file for cdflib
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".cdf", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = Path(tmp.name)

    try:
        return _extract_metadata(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _extract_metadata(cdf_path: Path) -> dict:
    """Extract parameter metadata from a Master CDF file."""
    import cdflib

    cdf = cdflib.CDF(str(cdf_path))
    cdf_info = cdf.cdf_info()

    parameters = [
        {"name": "Time", "type": "isotime", "units": "UTC", "fill": None}
    ]

    all_vars = list(cdf_info.zVariables) + list(cdf_info.rVariables)

    for var_name in all_vars:
        try:
            var_inq = cdf.varinq(var_name)
        except Exception:
            continue

        dtype_desc = var_inq.Data_Type_Description
        if dtype_desc.split()[0] in _SKIP_TYPES:
            continue

        param_type = _CDF_TYPE_MAP.get(dtype_desc.split()[0])
        if param_type is None:
            continue

        # Check VAR_TYPE (and keep attrs for reuse below)
        attrs = {}
        try:
            attrs = cdf.varattsget(var_name)
            var_type = attrs.get("VAR_TYPE", "")
            if isinstance(var_type, np.ndarray):
                var_type = str(var_type)
            if var_type and var_type.lower() not in ("data", "ignore_data"):
                continue
        except Exception:
            pass

        description = _get_str_attr(attrs, "CATDESC") or _get_str_attr(attrs, "FIELDNAM") or ""
        units = _get_str_attr(attrs, "UNITS") or ""

        fill = None
        raw_fill = attrs.get("FILLVAL", None)
        if raw_fill is not None:
            try:
                fill = str(float(raw_fill))
            except (ValueError, TypeError):
                pass

        dim_sizes = var_inq.Dim_Sizes
        if isinstance(dim_sizes, (list, np.ndarray)) and len(dim_sizes) > 0:
            size = [int(d) for d in dim_sizes]
            while len(size) > 1 and size[0] == 1:
                size = size[1:]
        else:
            size = [1]

        param = {
            "name": var_name,
            "type": param_type,
            "units": units,
            "description": description,
            "fill": fill,
        }
        if size != [1]:
            param["size"] = size

        parameters.append(param)

    start_date, stop_date = _extract_master_time_range(cdf)
    return {
        "parameters": parameters,
        "startDate": start_date,
        "stopDate": stop_date,
    }


def _extract_master_time_range(cdf) -> tuple[str, str]:
    """Extract dataset coverage from Master CDF global attributes.

    CDAWeb Master CDFs are inconsistent: most carry no coverage attributes at
    all (only ``Time_resolution``); some carry ``DATA_START_TIME`` /
    ``DATA_END_TIME`` as ``YYYYMMDD HHMMSS.ffffff`` strings (e.g. ERG); others
    carry ``START_TIME`` / ``STOP_TIME`` as CDF epoch doubles or ISO strings.
    ``START_TI`` / ``END_TI`` use a CDAWeb-internal epoch convention that is
    not safely convertible, so they are intentionally ignored.  Returns
    ``("", "")`` when no usable coverage is present.

    Args:
        cdf: An open :class:`cdflib.CDF` instance.

    Returns:
        ``(start_date, stop_date)`` ISO-8601 UTC strings (possibly empty).
    """
    try:
        attrs = cdf.globalattsget()
    except Exception:
        return "", ""

    start = _coerce_master_time(attrs.get("DATA_START_TIME")) or \
        _coerce_master_time(attrs.get("START_TIME"))
    stop = _coerce_master_time(attrs.get("DATA_END_TIME")) or \
        _coerce_master_time(attrs.get("STOP_TIME"))
    return start, stop


def _coerce_master_time(value) -> str:
    """Convert a Master CDF time attribute value to an ISO-8601 UTC string.

    Handles the two observed encodings: CDAWeb ``YYYYMMDD HHMMSS[.ffffff]``
    strings (``DATA_START_TIME``/``DATA_END_TIME``) and CDF epoch doubles or
    ISO strings (``START_TIME``/``STOP_TIME``).  Returns ``""`` when the value
    is missing or cannot be interpreted.
    """
    if value is None:
        return ""
    arr = np.asarray(value)
    if arr.size == 0:
        return ""
    raw = arr.flat[0]
    if isinstance(raw, (bytes, np.bytes_)):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, (str, np.str_)):
        text = str(raw).strip()
        if not text:
            return ""
        # CDAWeb DATA_START_TIME format: YYYYMMDD HHMMSS[.ffffff]
        m = re.match(
            r"^(\d{4})(\d{2})(\d{2})\s+(\d{2})(\d{2})(\d{2})(?:\.(\d+))?$",
            text,
        )
        if m:
            frac = m.group(7) or ""
            return (f"{m.group(1)}-{m.group(2)}-{m.group(3)}T"
                    f"{m.group(4)}:{m.group(5)}:{m.group(6)}"
                    f"{('.' + frac) if frac else ''}Z")
        # Already ISO-8601?  Pass through as-is.
        if re.match(r"^\d{4}-\d{2}-\d{2}T", text):
            return text
        return ""
    if isinstance(raw, (int, float, np.integer, np.floating)):
        try:
            from cdflib.epochs import CDFepoch
            y, mo, d, h, mi, se, ms = CDFepoch.breakdown(float(raw))
        except Exception:
            return ""
        if not (1900 <= y <= 2100):
            return ""
        return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{se:02d}.{ms:03d}Z"
    return ""


def _get_str_attr(attrs: dict, key: str) -> str:
    """Extract a string attribute from CDF variable attributes."""
    val = attrs.get(key, "")
    if val is None:
        return ""
    if isinstance(val, np.ndarray):
        val = str(val.flat[0]) if val.size > 0 else ""
    if isinstance(val, bytes):
        val = val.decode("utf-8", errors="replace")
    if isinstance(val, (int, float)):
        return str(val)
    return str(val).strip() if val else ""
