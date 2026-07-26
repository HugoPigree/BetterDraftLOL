"""Profiling temporel pour predict_draft() et suggest_bot_pick()."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger("draft_profiling")

PROFILE_ENABLED = os.environ.get("DRAFT_PROFILE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_active: ContextVar["ProfileReport | None"] = ContextVar("draft_profile", default=None)


@dataclass
class ProfileReport:
    label: str
    steps_ms: dict[str, float] = field(default_factory=dict)
    data_loads: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)

    def add_ms(self, step: str, elapsed_ms: float) -> None:
        self.steps_ms[step] = self.steps_ms.get(step, 0.0) + elapsed_ms

    def inc(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount


def profiling_active() -> bool:
    return _active.get() is not None


def current_profile() -> ProfileReport | None:
    return _active.get()


def begin_profile(label: str) -> ProfileReport:
    report = ProfileReport(label=label)
    _active.set(report)
    return report


def end_profile() -> ProfileReport | None:
    report = _active.get()
    _active.set(None)
    return report


@contextmanager
def profile_step(name: str) -> Iterator[None]:
    report = current_profile()
    if report is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        report.add_ms(name, (time.perf_counter() - start) * 1000)


def increment_counter(name: str, amount: int = 1) -> None:
    report = current_profile()
    if report is not None:
        report.inc(name, amount)


def record_data_load(
    resource: str,
    *,
    hit: bool,
    duration_ms: float = 0.0,
    detail: str | None = None,
) -> None:
    report = current_profile()
    if report is None:
        return
    if hit:
        report.inc(f"cache_hit_{resource}")
        return
    report.data_loads.append(
        {
            "resource": resource,
            "hit": hit,
            "duration_ms": round(duration_ms, 2),
            "detail": detail,
        }
    )
    report.inc(f"cache_miss_{resource}")


def format_steps(steps_ms: dict[str, float]) -> str:
    if not steps_ms:
        return "  (aucune étape)"
    total = sum(steps_ms.values())
    lines = []
    for name, ms in sorted(steps_ms.items(), key=lambda item: item[1], reverse=True):
        pct = (ms / total * 100) if total else 0
        lines.append(f"  {name:<36} {ms:8.1f} ms  ({pct:5.1f}%)")
    lines.append(f"  {'TOTAL (étapes)':<36} {total:8.1f} ms")
    return "\n".join(lines)


def format_data_loads(loads: list[dict[str, Any]], counters: dict[str, int] | None = None) -> str:
    lines: list[str] = []
    if loads:
        lines.append("  Misses (rechargements disques) :")
        for entry in loads:
            detail = f" — {entry['detail']}" if entry.get("detail") else ""
            ms = entry.get("duration_ms", 0)
            lines.append(
                f"    {entry['resource']:<28} {ms:8.1f} ms{detail}"
            )
    if counters:
        hits = sorted(
            (key.removeprefix("cache_hit_"), value)
            for key, value in counters.items()
            if key.startswith("cache_hit_") and value > 0
        )
        if hits:
            lines.append("  Hits cache (accès mémoire, non listés un par un) :")
            for resource, count in hits:
                lines.append(f"    {resource:<28} x{count}")
    if not lines:
        return "  (aucun chargement instrumenté)"
    miss_count = len(loads)
    hit_count = sum(
        value for key, value in (counters or {}).items() if key.startswith("cache_hit_")
    )
    lines.append(f"  -> {miss_count} miss / {miss_count + hit_count} acces instrumentes")
    return "\n".join(lines)


def log_report(report: ProfileReport, *, header: str | None = None) -> None:
    title = header or report.label
    total_wall = report.steps_ms.get("_wall_total_ms", sum(report.steps_ms.values()))
    lines = [
        "",
        "=" * 72,
        title,
        "=" * 72,
        f"Temps total mesuré : {total_wall:.1f} ms",
    ]
    if report.counters:
        counter_bits = ", ".join(f"{k}={v}" for k, v in sorted(report.counters.items()))
        lines.append(f"Compteurs : {counter_bits}")
    lines.extend(
        [
            "",
            "Décomposition par étape :",
            format_steps({k: v for k, v in report.steps_ms.items() if not k.startswith("_")}),
            "",
            "Chargements de données (cache hit/miss) :",
            format_data_loads(report.data_loads, report.counters),
            "=" * 72,
        ]
    )
    block = "\n".join(lines)
    logger.info(block)
    print(block)


def log_batch_summary(reports: list[ProfileReport], *, title: str) -> None:
    if not reports:
        return
    totals = [r.steps_ms.get("_wall_total_ms", sum(r.steps_ms.values())) for r in reports]
    avg = sum(totals) / len(totals)
    min_t = min(totals)
    max_t = max(totals)
    predict_calls = [r.counters.get("predict_draft_calls", 0) for r in reports]
    miss_counts = [
        sum(value for key, value in r.counters.items() if key.startswith("cache_miss_"))
        for r in reports
    ]

    lines = [
        "",
        "#" * 72,
        title,
        "#" * 72,
        f"Appels : {len(reports)}",
        f"Temps total (ms) : min={min_t:.1f}  avg={avg:.1f}  max={max_t:.1f}  "
        f"écart={max_t - min_t:.1f}",
        f"predict_draft() / appel : min={min(predict_calls)}  avg={sum(predict_calls)/len(predict_calls):.1f}  max={max(predict_calls)}",
        f"Cache misses / appel : min={min(miss_counts)}  avg={sum(miss_counts)/len(miss_counts):.1f}  max={max(miss_counts)}",
        "",
        "Détail par appel :",
    ]
    for index, (report, total) in enumerate(zip(reports, totals, strict=True), start=1):
        misses = sum(
            value for key, value in report.counters.items() if key.startswith("cache_miss_")
        )
        pd_calls = report.counters.get("predict_draft_calls", 0)
        pd_ms = report.steps_ms.get("predict_draft_inner", 0)
        lines.append(
            f"  #{index}: {total:7.1f} ms | predict_draft x{pd_calls} ({pd_ms:.1f} ms) | "
            f"cache_miss={misses} | {report.label}"
        )
    lines.append("#" * 72)
    block = "\n".join(lines)
    logger.info(block)
    print(block)
