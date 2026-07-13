#!/usr/bin/env python3
"""Read-only raw-EMG availability/QC audit for the DEJA-VU dataset.

The script identifies true EMG channels from XDF descriptors, audits all
participant-sessions, and evaluates raw-EMG temporal coverage for the existing
presentation and transition manifests. It never modifies dataset files.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyxdf

DEFAULT_REPO = Path('/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition')
DEFAULT_DATA = Path('/mnt/HDD/AliWorks/DEJA-VU')
SUB_RE = re.compile(r'^sub-(P\d+)$', re.I)
SES_RE = re.compile(r'^ses-(S\d+)$', re.I)
EMG_RE = re.compile(r'(^|_)EMG_CH([12])(_|$)', re.I)


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', type=Path, default=DEFAULT_REPO)
    p.add_argument('--data-root', type=Path, default=DEFAULT_DATA)
    p.add_argument('--expected-xdf-count', type=int, default=34)
    p.add_argument('--coverage-tolerance-sec', type=float, default=1.0)
    p.add_argument('--max-gap-factor', type=float, default=5.0)
    return p.parse_args()


def scalar(v: Any, default: str = '') -> str:
    while isinstance(v, (list, tuple)):
        if not v:
            return default
        v = v[0]
    return default if v is None else str(v)


def finite_float(v: Any) -> float | None:
    try:
        x = float(scalar(v))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def sname(stream: dict[str, Any]) -> str:
    return scalar(stream.get('info', {}).get('name'))


def stype(stream: dict[str, Any]) -> str:
    return scalar(stream.get('info', {}).get('type'))


def channel_meta(stream: dict[str, Any]) -> list[dict[str, str]]:
    try:
        desc = stream['info']['desc'][0]
        items = desc['channels'][0]['channel']
        if isinstance(items, dict):
            items = [items]
    except (KeyError, IndexError, TypeError):
        items = []
    out = []
    for i, item in enumerate(items):
        item = item if isinstance(item, dict) else {}
        out.append({
            'index': i,
            'label': scalar(item.get('label'), f'channel_{i}'),
            'unit': scalar(item.get('unit')),
            'type': scalar(item.get('type')),
        })
    return out


def identity_from_path(path: Path) -> tuple[str, str]:
    sub = ses = ''
    for part in path.parts:
        m = SUB_RE.match(part)
        if m:
            sub = m.group(1).upper()
        m = SES_RE.match(part)
        if m:
            ses = m.group(1).upper()
    if not sub or not ses:
        raise RuntimeError(f'Cannot parse participant/session from {path}')
    return sub, ses


def filename_identity(path: Path) -> tuple[str, str] | None:
    m = re.search(r'sub-(P\d+)_ses-(S\d+)', path.name, re.I)
    return (m.group(1).upper(), m.group(2).upper()) if m else None


def true_emg_indices(labels: list[str]) -> list[int]:
    found: list[tuple[int, int]] = []
    for i, label in enumerate(labels):
        upper = label.upper()
        if 'STATUS' in upper or 'BATTERY' in upper:
            continue
        m = EMG_RE.search(upper)
        if m:
            found.append((int(m.group(2)), i))
    found.sort()
    return [i for _, i in found]


def find_eeg(streams: list[dict[str, Any]]) -> dict[str, Any]:
    exact = [s for s in streams if sname(s).upper() == 'DSI_FLEX']
    if len(exact) == 1:
        return exact[0]
    typed = [s for s in streams if stype(s).upper() == 'EEG']
    if len(typed) == 1:
        return typed[0]
    raise RuntimeError(f'EEG stream unresolved: exact={len(exact)}, typed={len(typed)}')


def find_emg(streams: list[dict[str, Any]]) -> tuple[dict[str, Any], list[int], list[dict[str, str]]]:
    candidates = []
    for stream in streams:
        meta = channel_meta(stream)
        idx = true_emg_indices([m['label'] for m in meta])
        if len(idx) >= 2:
            candidates.append((stream, idx[:2], meta))
    exact = [c for c in candidates if sname(c[0]).upper() == 'SHIMMER_BBBD']
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(f'Descriptor-confirmed EMG stream unresolved: {[sname(c[0]) for c in candidates]}')


def as_numeric_2d(values: Any) -> np.ndarray:
    arr = np.asarray(values)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2:
        raise RuntimeError(f'Expected 2-D signal array, got {arr.shape}')
    return arr.astype(np.float64, copy=False)


def time_metrics(values: Any) -> dict[str, Any]:
    ts = np.asarray(values, dtype=np.float64).reshape(-1)
    finite = ts[np.isfinite(ts)]
    if not finite.size:
        return dict(n=len(ts), start=None, end=None, duration=None, monotonic=False,
                    duplicates=0, nonfinite=int((~np.isfinite(ts)).sum()), median_gap=None,
                    max_gap=None, effective_rate=None)
    d = np.diff(finite)
    pos = d[d > 0]
    med = float(np.median(pos)) if pos.size else None
    return dict(
        n=len(ts), start=float(finite[0]), end=float(finite[-1]),
        duration=float(finite[-1] - finite[0]) if len(finite) > 1 else 0.0,
        monotonic=bool(np.all(d >= 0)) if d.size else True,
        duplicates=int((d == 0).sum()), nonfinite=int((~np.isfinite(ts)).sum()),
        median_gap=med, max_gap=float(np.max(pos)) if pos.size else None,
        effective_rate=(1.0 / med) if med and med > 0 else None,
    )


def channel_stats(sub: str, ses: str, filename: str, stream: str, values: np.ndarray,
                  index: int, label: str, unit: str, is_true: bool) -> dict[str, Any]:
    x = np.asarray(values[:, index], dtype=np.float64)
    ok = np.isfinite(x)
    f = x[ok]
    mean = float(np.mean(f)) if f.size else None
    std = float(np.std(f)) if f.size else None
    p01, p99 = np.quantile(f, [0.01, 0.99]) if f.size else (np.nan, np.nan)
    constant = bool(f.size and np.ptp(f) == 0)
    near_constant = bool(std is not None and std <= np.finfo(float).eps * max(abs(mean or 0), 1.0) * 10)
    issues = []
    if not x.size:
        issues.append('EMPTY')
    if ok.mean() < 1.0:
        issues.append('NONFINITE')
    if constant:
        issues.append('CONSTANT')
    elif near_constant:
        issues.append('NEAR_CONSTANT')
    return {
        'participant_id': sub, 'session_id': ses, 'xdf_filename': filename,
        'stream_name': stream, 'channel_index': index, 'channel_label': label,
        'channel_unit': unit, 'is_true_emg': is_true,
        'is_official_code_selected_index_0_or_1': index in (0, 1),
        'sample_count': int(x.size), 'finite_count': int(f.size),
        'nan_count': int(np.isnan(x).sum()), 'posinf_count': int(np.isposinf(x).sum()),
        'neginf_count': int(np.isneginf(x).sum()), 'finite_fraction': float(ok.mean()) if x.size else 0.0,
        'mean': mean, 'std': std, 'minimum': float(np.min(f)) if f.size else None,
        'maximum': float(np.max(f)) if f.size else None,
        'robust_range_p01_p99': float(p99 - p01) if f.size else None,
        'constant_channel': constant, 'near_constant_channel': near_constant,
        'qc_status': 'PASS' if not issues else ';'.join(issues),
    }


def interval_coverage(ts: np.ndarray, start: float, end: float, rate: float | None,
                      tolerance: float, max_gap_factor: float) -> dict[str, Any]:
    if not (math.isfinite(start) and math.isfinite(end)) or end <= start:
        return {'raw_emg_any_overlap': False, 'raw_emg_full_coverage': False,
                'raw_emg_observed_samples': 0, 'raw_emg_expected_samples': None,
                'raw_emg_sample_coverage_ratio': None, 'raw_emg_interval_max_gap_sec': None,
                'raw_emg_interval_gap_ok': False, 'raw_emg_coverage_reason': 'INVALID_INTERVAL'}
    ts = ts[np.isfinite(ts)]
    if not ts.size:
        return {'raw_emg_any_overlap': False, 'raw_emg_full_coverage': False,
                'raw_emg_observed_samples': 0, 'raw_emg_expected_samples': None,
                'raw_emg_sample_coverage_ratio': 0.0, 'raw_emg_interval_max_gap_sec': None,
                'raw_emg_interval_gap_ok': False, 'raw_emg_coverage_reason': 'NO_EMG_TIMESTAMPS'}
    selected = ts[(ts >= start - tolerance) & (ts <= end + tolerance)]
    boundary = bool(ts[0] <= start + tolerance and ts[-1] >= end - tolerance)
    expected = int(round((end - start) * rate)) if rate and rate > 0 else None
    ratio = min(float(len(selected) / expected), 1.0) if expected else None
    if len(selected) >= 2:
        gaps = np.diff(selected)
        max_gap = float(np.max(gaps))
        typical = (1.0 / rate) if rate and rate > 0 else float(np.median(gaps[gaps > 0]))
        gap_ok = bool(max_gap <= max(max_gap_factor * typical, tolerance))
    else:
        max_gap, gap_ok = None, False
    sample_ok = ratio is None or ratio >= 0.98
    full = bool(boundary and gap_ok and sample_ok)
    reasons = []
    if not len(selected):
        reasons.append('NO_OVERLAP')
    if not boundary:
        reasons.append('BOUNDARY_NOT_COVERED')
    if not gap_ok:
        reasons.append('GAP_OR_TOO_FEW_SAMPLES')
    if not sample_ok:
        reasons.append('LOW_SAMPLE_COVERAGE')
    return {
        'raw_emg_any_overlap': bool(len(selected)), 'raw_emg_full_coverage': full,
        'raw_emg_observed_samples': int(len(selected)), 'raw_emg_expected_samples': expected,
        'raw_emg_sample_coverage_ratio': ratio, 'raw_emg_interval_max_gap_sec': max_gap,
        'raw_emg_interval_gap_ok': gap_ok,
        'raw_emg_coverage_reason': 'PASS' if full else ';'.join(reasons),
    }


def audit_manifest(path: Path, unit_type: str, lookup: dict[str, dict[str, Any]],
                   tolerance: float, max_gap_factor: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    if unit_type == 'presentation':
        id_col, start_col, end_col = 'presentation_id', 'timeline_start_sec', 'timeline_end_sec'
    else:
        id_col, start_col, end_col = None, 'transition_start_sec', 'transition_end_sec'
    rows = []
    for _, row in df.iterrows():
        sub, ses = str(row.participant_id), str(row.session_id)
        key = f'{sub}_{ses}'
        uid = str(row[id_col]) if id_col else f"{sub}_{ses}_t{int(row.transition_position)}"
        start, end = row.get(start_col), row.get(end_col)
        out = {
            'unit_type': unit_type, 'unit_id': uid, 'participant_id': sub, 'session_id': ses,
            'participant_session_key': key, 'start_sec': start, 'end_sec': end,
            'duration_sec': float(end - start) if pd.notna(start) and pd.notna(end) else None,
            'video_name': row.get('video_name', ''), 'is_baseline': row.get('is_baseline', ''),
            'transition_type': row.get('transition_type', ''),
        }
        if key not in lookup:
            out.update({'raw_emg_any_overlap': False, 'raw_emg_full_coverage': False,
                        'raw_emg_observed_samples': 0, 'raw_emg_expected_samples': None,
                        'raw_emg_sample_coverage_ratio': None, 'raw_emg_interval_max_gap_sec': None,
                        'raw_emg_interval_gap_ok': False,
                        'raw_emg_coverage_reason': 'SESSION_AUDIT_UNAVAILABLE'})
        elif pd.isna(start) or pd.isna(end):
            out.update({'raw_emg_any_overlap': False, 'raw_emg_full_coverage': False,
                        'raw_emg_observed_samples': 0, 'raw_emg_expected_samples': None,
                        'raw_emg_sample_coverage_ratio': None, 'raw_emg_interval_max_gap_sec': None,
                        'raw_emg_interval_gap_ok': False, 'raw_emg_coverage_reason': 'MISSING_TIMELINE'})
        else:
            out.update(interval_coverage(lookup[key]['ts'], float(start), float(end),
                                         lookup[key]['rate'], tolerance, max_gap_factor))
        rows.append(out)
    return pd.DataFrame(rows)


def json_safe(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): json_safe(x) for k, x in v.items()}
    if isinstance(v, list):
        return [json_safe(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def write_report(path: Path, summary: dict[str, Any], sessions: pd.DataFrame,
                 coverage: pd.DataFrame) -> None:
    bad_sessions = sessions[sessions.session_qc_status != 'PASS']
    bad_units = coverage[coverage.raw_emg_full_coverage != True]  # noqa: E712
    lines = [
        '# DEJA-VU Raw EMG Availability and QC Audit', '',
        f"Generated: `{summary['generated_at_utc']}`", '',
        'Read-only audit of descriptor-identified true EMG channels in raw XDF files. '
        'No filtering, resampling, segmentation, or training was performed.', '',
        '## Headline results', '', '| Metric | Value |', '|---|---:|',
        f"| Raw XDF files discovered | {summary['xdf_files_discovered']} |",
        f"| Sessions passed | {summary['sessions_passed']} |",
        f"| Sessions with warning/error | {summary['sessions_not_passed']} |",
        f"| True EMG channel rows | {summary['true_emg_channel_rows']} |",
        f"| True EMG channels with non-finite samples | {summary['true_emg_channels_with_nonfinite']} |",
        f"| True EMG channels constant/near-constant | {summary['true_emg_channels_constant_or_near_constant']} |",
        f"| Presentations with full raw-EMG coverage | {summary['presentations_full_coverage']} / {summary['presentation_rows']} |",
        f"| Transitions with full raw-EMG coverage | {summary['transitions_full_coverage']} / {summary['transition_rows']} |",
        '', '## Session-level exceptions', '',
    ]
    if bad_sessions.empty:
        lines.append('None.')
    else:
        lines += ['| Session | Status | EMG duration | EEG duration | End gap | Error |',
                  '|---|---|---:|---:|---:|---|']
        for _, r in bad_sessions.iterrows():
            lines.append(f"| {r.participant_session_key} | {r.session_qc_status} | {r.emg_duration_sec} | "
                         f"{r.eeg_duration_sec} | {r.emg_end_gap_vs_eeg_sec} | {r.error} |")
    lines += ['', '## Event intervals without full raw-EMG coverage', '']
    if bad_units.empty:
        lines.append('None.')
    else:
        lines += ['| Type | ID | Session | Start | End | Coverage | Reason |',
                  '|---|---|---|---:|---:|---:|---|']
        for _, r in bad_units.iterrows():
            ratio = '' if pd.isna(r.raw_emg_sample_coverage_ratio) else f'{r.raw_emg_sample_coverage_ratio:.4f}'
            lines.append(f"| {r.unit_type} | {r.unit_id} | {r.participant_session_key} | "
                         f"{r.start_sec} | {r.end_sec} | {ratio} | {r.raw_emg_coverage_reason} |")
    lines += ['', '## Interpretation boundary', '',
              'This audit establishes availability, numeric integrity, and interval coverage only. '
              'It does not establish final physiological signal quality.', '',
              'The official distributed EMG HDF5 groups are not trusted because the official code '
              'selected columns 0-1; this audit uses descriptor-resolved true EMG channels.', '']
    path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> int:
    a = args()
    repo, data = a.repo_root.resolve(), a.data_root.resolve()
    raw_root = data / 'extracted/dataset/DEJA-VU/raw'
    docs, manifests = repo / 'docs', repo / 'manifests'
    if not (repo / '.git').is_dir():
        print(f'ERROR: repository not found: {repo}', file=sys.stderr)
        return 2
    if not raw_root.is_dir():
        print(f'ERROR: raw root not found: {raw_root}', file=sys.stderr)
        return 2
    docs.mkdir(parents=True, exist_ok=True)
    xdfs = sorted(raw_root.glob('sub-*/ses-*/eeg/*.xdf'))
    if not xdfs:
        print('ERROR: no XDF files found', file=sys.stderr)
        return 2
    print(f'Discovered {len(xdfs)} XDF files')
    if len(xdfs) != a.expected_xdf_count:
        print(f'WARNING: expected {a.expected_xdf_count}, found {len(xdfs)}', file=sys.stderr)

    session_rows, channel_rows, lookup = [], [], {}
    for n, path in enumerate(xdfs, 1):
        sub, ses = identity_from_path(path)
        key = f'{sub}_{ses}'
        print(f'[{n:02d}/{len(xdfs):02d}] {key}: {path.name}', flush=True)
        file_id = filename_identity(path)
        conflict = bool(file_id and file_id != (sub, ses))
        try:
            streams, _ = pyxdf.load_xdf(str(path), verbose=False)
            eeg = find_eeg(streams)
            emg, idx, meta = find_emg(streams)
            eeg_tm, emg_tm = time_metrics(eeg.get('time_stamps', [])), time_metrics(emg.get('time_stamps', []))
            values = as_numeric_2d(emg.get('time_series', []))
            if values.shape[0] != emg_tm['n'] or values.shape[1] != len(meta):
                raise RuntimeError(f'EMG shape mismatch: values={values.shape}, timestamps={emg_tm["n"]}, descriptors={len(meta)}')
            if eeg_tm['start'] is None or emg_tm['start'] is None:
                raise RuntimeError('Missing finite EEG/EMG timestamp origin')
            labels, units = [m['label'] for m in meta], [m['unit'] for m in meta]
            for i in range(values.shape[1]):
                channel_rows.append(channel_stats(sub, ses, path.name, sname(emg), values, i,
                                                  labels[i], units[i], i in idx))
            nominal = finite_float(emg.get('info', {}).get('nominal_srate'))
            rate = nominal or emg_tm['effective_rate']
            lookup[key] = {'ts': np.asarray(emg.get('time_stamps', []), dtype=float) - eeg_tm['start'], 'rate': rate}
            ratio = emg_tm['duration'] / eeg_tm['duration'] if eeg_tm['duration'] and emg_tm['duration'] is not None else None
            end_gap = eeg_tm['end'] - emg_tm['end'] if eeg_tm['end'] is not None and emg_tm['end'] is not None else None
            true_rows = [r for r in channel_rows if r['participant_id'] == sub and r['session_id'] == ses and r['is_true_emg']]
            issues = []
            if len(idx) != 2:
                issues.append('TRUE_EMG_CHANNELS_UNRESOLVED')
            if any(r['finite_fraction'] < 1 for r in true_rows):
                issues.append('TRUE_EMG_NONFINITE')
            if any(r['constant_channel'] or r['near_constant_channel'] for r in true_rows):
                issues.append('TRUE_EMG_CONSTANT')
            if not emg_tm['monotonic']:
                issues.append('NONMONOTONIC_TIMESTAMPS')
            if emg_tm['nonfinite']:
                issues.append('NONFINITE_TIMESTAMPS')
            if ratio is not None and ratio < 0.95:
                issues.append('SHORT_EMG_COVERAGE')
            session_rows.append({
                'participant_id': sub, 'session_id': ses, 'participant_session_key': key,
                'xdf_path': str(path), 'xdf_filename': path.name,
                'identity_filename_conflict': conflict, 'xdf_stream_count': len(streams),
                'eeg_stream_name': sname(eeg), 'eeg_sample_count': eeg_tm['n'],
                'eeg_start_timestamp': eeg_tm['start'], 'eeg_end_timestamp': eeg_tm['end'],
                'eeg_duration_sec': eeg_tm['duration'], 'emg_stream_name': sname(emg),
                'emg_stream_found': True, 'emg_stream_channel_count': values.shape[1],
                'emg_channel_indices': ';'.join(map(str, idx)),
                'emg_channel_labels': ';'.join(labels[i] for i in idx),
                'emg_channel_units': ';'.join(units[i] for i in idx),
                'emg_nominal_srate_hz': nominal, 'emg_effective_srate_hz': emg_tm['effective_rate'],
                'emg_sample_count': emg_tm['n'], 'emg_start_timestamp': emg_tm['start'],
                'emg_end_timestamp': emg_tm['end'],
                'emg_start_relative_to_eeg_sec': emg_tm['start'] - eeg_tm['start'],
                'emg_end_relative_to_eeg_sec': emg_tm['end'] - eeg_tm['start'],
                'emg_duration_sec': emg_tm['duration'], 'emg_to_eeg_duration_ratio': ratio,
                'emg_end_gap_vs_eeg_sec': end_gap, 'emg_timestamp_monotonic': emg_tm['monotonic'],
                'emg_duplicate_timestamp_count': emg_tm['duplicates'],
                'emg_nonfinite_timestamp_count': emg_tm['nonfinite'],
                'emg_max_gap_sec': emg_tm['max_gap'], 'emg_median_gap_sec': emg_tm['median_gap'],
                'true_emg_channels_resolved': len(idx) == 2,
                'official_indices_0_1_are_true_emg': set(idx) == {0, 1},
                'session_qc_status': 'PASS' if not issues else ';'.join(issues), 'error': '',
            })
        except Exception as exc:
            traceback.print_exc()
            session_rows.append({
                'participant_id': sub, 'session_id': ses, 'participant_session_key': key,
                'xdf_path': str(path), 'xdf_filename': path.name,
                'identity_filename_conflict': conflict, 'xdf_stream_count': 0,
                'eeg_stream_name': '', 'eeg_sample_count': 0, 'eeg_start_timestamp': None,
                'eeg_end_timestamp': None, 'eeg_duration_sec': None, 'emg_stream_name': '',
                'emg_stream_found': False, 'emg_stream_channel_count': 0,
                'emg_channel_indices': '', 'emg_channel_labels': '', 'emg_channel_units': '',
                'emg_nominal_srate_hz': None, 'emg_effective_srate_hz': None,
                'emg_sample_count': 0, 'emg_start_timestamp': None, 'emg_end_timestamp': None,
                'emg_start_relative_to_eeg_sec': None, 'emg_end_relative_to_eeg_sec': None,
                'emg_duration_sec': None, 'emg_to_eeg_duration_ratio': None,
                'emg_end_gap_vs_eeg_sec': None, 'emg_timestamp_monotonic': False,
                'emg_duplicate_timestamp_count': 0, 'emg_nonfinite_timestamp_count': 0,
                'emg_max_gap_sec': None, 'emg_median_gap_sec': None,
                'true_emg_channels_resolved': False, 'official_indices_0_1_are_true_emg': False,
                'session_qc_status': 'ERROR', 'error': f'{type(exc).__name__}: {exc}',
            })
        finally:
            if 'streams' in locals():
                del streams
            gc.collect()

    sessions = pd.DataFrame(session_rows).sort_values(['participant_id', 'session_id'])
    channels = pd.DataFrame(channel_rows).sort_values(['participant_id', 'session_id', 'channel_index'])
    presentations = audit_manifest(manifests / 'dejavu_stimulus_presentation_manifest.csv',
                                   'presentation', lookup, a.coverage_tolerance_sec, a.max_gap_factor)
    transitions = audit_manifest(manifests / 'dejavu_transition_manifest.csv',
                                 'transition', lookup, a.coverage_tolerance_sec, a.max_gap_factor)
    coverage = pd.concat([presentations, transitions], ignore_index=True)
    true = channels[channels.is_true_emg == True]  # noqa: E712
    summary = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'repo_root': str(repo), 'data_root': str(data), 'raw_root': str(raw_root),
        'xdf_files_discovered': len(xdfs), 'expected_xdf_count': a.expected_xdf_count,
        'sessions_passed': int((sessions.session_qc_status == 'PASS').sum()),
        'sessions_not_passed': int((sessions.session_qc_status != 'PASS').sum()),
        'session_status_counts': sessions.session_qc_status.value_counts().to_dict(),
        'true_emg_channel_rows': len(true),
        'true_emg_channels_with_nonfinite': int((true.finite_fraction < 1).sum()),
        'true_emg_channels_constant_or_near_constant': int((true.constant_channel | true.near_constant_channel).sum()),
        'official_indices_0_1_match_true_emg_sessions': int(sessions.official_indices_0_1_are_true_emg.sum()),
        'presentation_rows': len(presentations),
        'presentations_full_coverage': int(presentations.raw_emg_full_coverage.sum()),
        'transition_rows': len(transitions),
        'transitions_full_coverage': int(transitions.raw_emg_full_coverage.sum()),
        'coverage_reason_counts': coverage.raw_emg_coverage_reason.value_counts().to_dict(),
        'coverage_tolerance_sec': a.coverage_tolerance_sec, 'max_gap_factor': a.max_gap_factor,
        'hard_errors': sessions.loc[sessions.session_qc_status == 'ERROR', 'participant_session_key'].tolist(),
    }
    sessions.to_csv(docs / 'dejavu_raw_emg_qc_by_session.csv', index=False)
    channels.to_csv(docs / 'dejavu_raw_emg_channel_stats.csv', index=False)
    coverage.to_csv(docs / 'dejavu_raw_emg_interval_coverage.csv', index=False)
    (docs / 'dejavu_raw_emg_qc.json').write_text(json.dumps(json_safe(summary), indent=2, sort_keys=True), encoding='utf-8')
    write_report(docs / 'dejavu_raw_emg_qc.md', summary, sessions, coverage)

    print('\nDEJA-VU RAW EMG QC CHECKPOINT')
    print(f"XDF files: {len(xdfs)}")
    print(f"Sessions PASS: {summary['sessions_passed']}")
    print(f"Sessions not PASS: {summary['sessions_not_passed']}")
    print(f"Presentation full coverage: {summary['presentations_full_coverage']}/{summary['presentation_rows']}")
    print(f"Transition full coverage: {summary['transitions_full_coverage']}/{summary['transition_rows']}")
    print(f"Report: {docs / 'dejavu_raw_emg_qc.md'}")
    return 1 if summary['hard_errors'] else 0


if __name__ == '__main__':
    sys.exit(main())

