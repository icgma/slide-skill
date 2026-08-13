"""Shared trace logging for AI interactions."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .util import ensure_dir

TRACE_FILE = "ai-trace.jsonl"
TRACE_ARTIFACT_DIR = "ai-trace-artifacts"
MAX_EXCERPT_CHARS = 700


def write_ai_trace(
    project_path: Path | str | None,
    *,
    stage: str,
    model: str,
    status: str,
    prompt: str | None = None,
    raw: str | None = None,
    request: dict | None = None,
    attempt: int | None = None,
    metadata: dict | None = None,
) -> None:
    """Append one AI interaction event to ``qa/ai-trace.jsonl``."""
    if project_path is None:
        return
    project = Path(project_path)
    qa_dir = ensure_dir(project / "qa")
    path = qa_dir / TRACE_FILE
    event_index = _next_event_index(path)
    artifact_paths = _write_trace_artifacts(
        qa_dir,
        event_index=event_index,
        stage=stage,
        attempt=attempt,
        prompt=prompt,
        raw=raw,
        request=request,
    )
    request_text = json.dumps(request or {}, ensure_ascii=False, indent=2) if request else ""
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "model": model,
        "status": status,
        "attempt": attempt,
        "prompt_chars": len(prompt or ""),
        "raw_chars": len(raw or ""),
        "request_chars": len(request_text),
        "prompt_excerpt": _excerpt(prompt),
        "raw_excerpt": _excerpt(raw),
        **artifact_paths,
        "metadata": metadata or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def ai_response_metadata(response) -> dict:
    """Extract stable provider response signals for trace diagnostics."""
    metadata: dict = {}
    response_id = _scalar_attr(response, "id")
    if response_id:
        metadata["response_id"] = response_id
    finish_reason = _response_finish_reason(response)
    if finish_reason:
        metadata["finish_reason"] = finish_reason
    usage = _scalar_usage(response)
    if usage:
        metadata.update(usage)
    return metadata


def read_ai_trace(project_path: Path | str) -> list[dict]:
    """Read AI trace events from a project, returning an empty list if absent."""
    path = Path(project_path) / "qa" / TRACE_FILE
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            events.append({"stage": "unknown", "status": "invalid-json", "metadata": {"line": line}})
            continue
        if isinstance(payload, dict):
            events.append(_annotate_trace_event(payload))
    return events


def summarize_ai_trace(
    project_path: Path | str,
    events: list[dict] | None = None,
    *,
    start_index: int = 0,
    scope_label: str = "",
) -> str:
    """Format AI trace events as a compact human-readable audit."""
    project = Path(project_path)
    events = read_ai_trace(project) if events is None else events
    trace_path = project / "qa" / TRACE_FILE
    if not events:
        suffix = f" ({scope_label})" if scope_label else ""
        return f"No AI trace events found at {trace_path}{suffix}"

    suffix = f" ({scope_label})" if scope_label else ""
    lines = [f"AI trace: {trace_path}{suffix}", f"events: {len(events)}"]
    failure_hints = _failure_hint_counts(events)
    if failure_hints:
        lines.append(f"failure-hints: {_format_counts(failure_hints)}")
    for index, event in enumerate(events, start=start_index + 1):
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        parts = [
            f"{index}. {event.get('stage', 'unknown')}",
            f"status={event.get('status', 'unknown')}",
            f"attempt={event.get('attempt', '-')}",
            f"model={event.get('model', '-')}",
        ]
        for key in (
            "slide",
            "slides",
            "blocking_count",
            "blocking_issues",
            "severity",
            "finish_reason",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "error",
            "has_qa_feedback",
            "has_executor_brief",
            "has_visual_feedback",
            "feedback",
        ):
            if key in metadata:
                parts.append(f"{key}={_format_metadata_value(metadata[key])}")
        parts.append(f"prompt_chars={event.get('prompt_chars', 0)}")
        parts.append(f"raw_chars={event.get('raw_chars', 0)}")
        if event.get("prompt_path"):
            parts.append(f"prompt={event['prompt_path']}")
        if event.get("raw_path"):
            parts.append(f"raw={event['raw_path']}")
        if event.get("request_path"):
            parts.append(f"request={event['request_path']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def diagnose_ai_trace(
    project_path: Path | str,
    events: list[dict] | None = None,
    *,
    start_index: int = 0,
    scope_label: str = "",
    iteration_result: dict | None = None,
) -> str:
    """Return an actionable diagnosis of recorded AI interactions."""
    project = Path(project_path)
    events = read_ai_trace(project) if events is None else events
    trace_path = project / "qa" / TRACE_FILE
    if not events:
        suffix = f" ({scope_label})" if scope_label else ""
        return "\n".join([
            f"AI trace diagnosis: {trace_path}{suffix}",
            "- missing: no AI trace events were recorded",
            "- next: confirm the command reached the model call; if not, check API key/base URL gating first",
        ])

    suffix = f" ({scope_label})" if scope_label else ""
    lines = [f"AI trace diagnosis: {trace_path}{suffix}", f"- events: {len(events)}"]
    status_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}
    for event in events:
        status = str(event.get("status", "unknown"))
        stage = str(event.get("stage", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    lines.append(f"- stages: {_format_counts(stage_counts)}")
    lines.append(f"- statuses: {_format_counts(status_counts)}")
    failure_hints = _failure_hint_counts(events)
    if failure_hints:
        lines.append(f"- failure-hints: {_format_counts(failure_hints)}")
    if iteration_result:
        _append_iteration_result_diagnosis(lines, iteration_result)
    smoke_result = _current_smoke_result(project, events) if start_index == 0 and not iteration_result else None
    if smoke_result:
        _append_smoke_result_diagnosis(lines, smoke_result)
    smoke_visual_ok_gate = bool(
        smoke_result and smoke_result.get("require_visual_ok") and smoke_result.get("status") == "failed"
    )
    iteration_visual_ok_gate = bool(
        iteration_result and iteration_result.get("require_visual_ok") and iteration_result.get("status") == "failed"
    )
    visual_ok_gate = smoke_visual_ok_gate or iteration_visual_ok_gate

    _append_failure_diagnosis(lines, project, events, start_index=start_index, visual_ok_gate=visual_ok_gate)
    _append_stage_diagnosis(lines, events, iteration_result=iteration_result)
    _append_sidecar_diagnosis(lines, project, events, start_index=start_index)

    if visual_ok_gate and _latest_visual_repair_gate(events, visual_ok_gate=True):
        gate_label = "AI smoke visual-ok gate" if smoke_visual_ok_gate else "AI visual-ok gate"
        lines.append(f"- result: {gate_label} is still failing despite passed model calls")
    elif not any(event.get("status") not in {"passed", "ok", "success"} for event in events):
        lines.append("- result: all recorded AI events passed their current gates")
    elif events[-1].get("status") in {"passed", "ok", "success"} and not _latest_visual_repair_gate(events):
        lines.append("- result: latest recorded AI event passed; earlier failures in this scope were recovered by retry")
    return "\n".join(lines)


def latest_iteration_trace_scope(project_path: Path | str) -> tuple[list[dict], int, str, dict]:
    """Return trace events scoped to the latest ``qa/AI-ITERATION.json`` run."""
    project = Path(project_path)
    iteration_path = project / "qa" / "AI-ITERATION.json"
    if not iteration_path.exists():
        raise FileNotFoundError(f"AI iteration result not found: {iteration_path}")
    payload = json.loads(iteration_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"AI iteration result must be a JSON object: {iteration_path}")
    trace_start = int(payload.get("trace_start") or 0)
    events = read_ai_trace(project)
    if trace_start < 0 or trace_start > len(events):
        raise ValueError(f"AI iteration trace_start {trace_start} is outside trace length {len(events)}")
    label = f"latest iteration, events {trace_start + 1}-{len(events)}"
    return events[trace_start:], trace_start, label, payload


def read_ai_trace_part(project_path: Path | str, event_index: int, part: str) -> str:
    """Read the full prompt, raw-response, or request sidecar for a trace event."""
    if part not in {"prompt", "raw", "request"}:
        raise ValueError("part must be 'prompt', 'raw', or 'request'")
    if event_index < 1:
        raise ValueError("event index must be 1-based")

    project = Path(project_path)
    events = read_ai_trace(project)
    if event_index > len(events):
        raise IndexError(f"trace event {event_index} not found; trace has {len(events)} event(s)")
    key = f"{part}_path"
    path_value = events[event_index - 1].get(key)
    if not path_value:
        raise FileNotFoundError(f"trace event {event_index} has no {part} sidecar")
    path = project / "qa" / path_value
    if not path.exists():
        raise FileNotFoundError(f"trace sidecar not found: {path}")
    return path.read_text(encoding="utf-8")


def write_ai_trace_bundle(
    project_path: Path | str,
    output_path: Path | str,
    events: list[dict] | None = None,
    *,
    start_index: int = 0,
    scope_label: str = "",
) -> Path:
    """Write a zip bundle with trace sidecars and machine-readable AI reports."""
    project = Path(project_path)
    qa_dir = project / "qa"
    selected_events = read_ai_trace(project) if events is None else events
    output = Path(output_path)
    ensure_dir(output.parent)

    included: list[str] = []
    seen: set[str] = set()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": str(project),
            "scope": scope_label or "all trace events",
            "start_index": start_index,
            "event_count": len(selected_events),
            "events": [
                {
                    "event": start_index + offset,
                    "stage": event.get("stage", "unknown"),
                    "status": event.get("status", "unknown"),
                    "attempt": event.get("attempt"),
                    "model": event.get("model", ""),
                    "prompt_path": event.get("prompt_path", ""),
                    "raw_path": event.get("raw_path", ""),
                    "request_path": event.get("request_path", ""),
                    "metadata": event.get("metadata", {}),
                }
                for offset, event in enumerate(selected_events, start=1)
            ],
        }
        _zip_write_text(bundle, "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", included, seen)
        _zip_write_text(
            bundle,
            "qa/ai-trace.selected-events.json",
            json.dumps(selected_events, ensure_ascii=False, indent=2) + "\n",
            included,
            seen,
        )

        for name in (
            TRACE_FILE,
            "AI-SMOKE.json",
            "AI-ITERATION.json",
            "AI-RELEASE-CHECK.json",
            "QA.md",
            "FIX-VERIFY.md",
            "VISUAL-REVIEW.md",
            "visual-feedback.json",
        ):
            _zip_add_file(bundle, qa_dir / name, f"qa/{name}", included, seen)

        for event in selected_events:
            for key in ("prompt_path", "raw_path", "request_path"):
                value = str(event.get(key) or "")
                if not value:
                    continue
                _zip_add_file(bundle, qa_dir / value, f"qa/{value}", included, seen)

        _zip_write_text(
            bundle,
            "included-files.json",
            json.dumps(included, ensure_ascii=False, indent=2) + "\n",
            included,
            seen,
        )
    return output


def format_ai_trace_command(
    project_path: Path | str,
    *,
    event_index: int | None = None,
    part: str = "raw",
    diagnose: bool = False,
    latest_iteration: bool = False,
) -> str:
    """Return a copy-pasteable ``slide-skill ai-trace`` command for a project."""
    command = f"slide-skill ai-trace {_format_cli_path(Path(project_path))}"
    if latest_iteration:
        command += " --latest-iteration"
    if diagnose:
        command += " --diagnose"
    if event_index is not None:
        command += f" --event {event_index} --part {part}"
    return command


def format_cli_path(path: Path | str) -> str:
    """Return a command-safe path fragment for slide-skill CLI hints."""
    return _format_cli_path(Path(path))


def _zip_add_file(bundle: zipfile.ZipFile, path: Path, arcname: str, included: list[str], seen: set[str]) -> None:
    if arcname in seen or not path.exists() or not path.is_file():
        return
    bundle.write(path, arcname)
    seen.add(arcname)
    included.append(arcname)


def _zip_write_text(
    bundle: zipfile.ZipFile,
    arcname: str,
    text: str,
    included: list[str],
    seen: set[str],
) -> None:
    if arcname in seen:
        return
    bundle.writestr(arcname, text)
    seen.add(arcname)
    included.append(arcname)


def _append_failure_diagnosis(
    lines: list[str],
    project: Path,
    events: list[dict],
    *,
    start_index: int = 0,
    visual_ok_gate: bool = False,
) -> None:
    repair_gate = _latest_visual_repair_gate(events, visual_ok_gate=visual_ok_gate)
    repair_gate_idx = events.index(repair_gate) if repair_gate else -1
    failed = [event for event in events if event.get("status") not in {"passed", "ok", "success"}]
    if not failed:
        if repair_gate:
            repair_gate_index = start_index + repair_gate_idx + 1
            metadata = repair_gate.get("metadata") if isinstance(repair_gate.get("metadata"), dict) else {}
            lines.append(
                f"- {'visual-ok-gate' if visual_ok_gate else 'active-repair-gate'}: "
                f"event={repair_gate_index} | stage=visual-critic | slide={metadata.get('slide', '-')} | severity={metadata.get('severity', '-')}"
            )
            lines.append(f"- inspect-repair-gate: {_trace_command(project, repair_gate_index)}")
            _append_visual_repair_targets(
                lines,
                project,
                min_severity="minor" if visual_ok_gate else "major",
            )
            if visual_ok_gate:
                lines.append("- next: review visual feedback and run iterate-ai; this smoke requires severity ok")
        return
    latest = failed[-1]
    latest_idx = events.index(latest)
    latest_index = start_index + latest_idx + 1
    metadata = latest.get("metadata") if isinstance(latest.get("metadata"), dict) else {}
    historical_retry = latest_idx < len(events) - 1
    recovered_failure = historical_retry and not repair_gate
    parts = [
        f"event={latest_index}",
        f"stage={latest.get('stage', 'unknown')}",
        f"attempt={latest.get('attempt', '-')}",
        f"model={latest.get('model', '-')}",
    ]
    if "slide" in metadata:
        parts.append(f"slide={metadata['slide']}")
    failure_label = "recovered-failure" if recovered_failure else "latest-failure"
    lines.append(f"- {failure_label}: {' | '.join(parts)}")
    lines.append(f"- inspect-event: {_trace_command(project, latest_index)}")
    if metadata.get("error"):
        error_label = "recovered-error" if recovered_failure else "latest-error"
        lines.append(f"- {error_label}: {_format_metadata_value(metadata['error'])}")
    if metadata.get("blocking_issues"):
        lines.append(f"- blocking-issues: {_format_metadata_value(metadata['blocking_issues'])}")
    elif metadata.get("blocking_count"):
        lines.append(f"- blocking-issues: {metadata['blocking_count']} blocking issue(s); inspect raw executor attempt logs")
    error = str(metadata.get("error") or "")
    if _looks_like_provider_access_error(error):
        lines.append(f"- next: {_provider_access_next_step(latest)}")
    elif historical_retry and not repair_gate:
        lines.append("- note: later AI events passed after this failure; treat it as historical retry evidence unless current QA is failing")
        _append_issue_specific_next_steps(lines, latest, metadata)
    else:
        lines.append("- next: inspect the latest failure prompt/raw sidecars before changing prompts")
        _append_issue_specific_next_steps(lines, latest, metadata)
    if repair_gate and repair_gate_idx > latest_idx:
        repair_gate_index = start_index + repair_gate_idx + 1
        metadata = repair_gate.get("metadata") if isinstance(repair_gate.get("metadata"), dict) else {}
        lines.append(
            f"- {'visual-ok-gate' if visual_ok_gate else 'active-repair-gate'}: "
            f"event={repair_gate_index} | stage=visual-critic | slide={metadata.get('slide', '-')} | severity={metadata.get('severity', '-')}"
        )
        lines.append(f"- inspect-repair-gate: {_trace_command(project, repair_gate_index)}")
        _append_visual_repair_targets(
            lines,
            project,
            min_severity="minor" if visual_ok_gate else "major",
        )
        if visual_ok_gate:
            lines.append("- next: review visual feedback and run iterate-ai; this smoke requires severity ok")
        else:
            lines.append("- next: run repair-feedback or iterate-ai before tuning earlier successful stages")


def _append_stage_diagnosis(lines: list[str], events: list[dict], *, iteration_result: dict | None = None) -> None:
    planner_events = [event for event in events if event.get("stage") == "planner"]
    executor_events = [event for event in events if event.get("stage") == "executor"]
    critic_events = [event for event in events if event.get("stage") == "visual-critic"]
    if planner_events and not any(event.get("status") == "passed" for event in planner_events):
        lines.append("- planner: no passed planner event recorded")
    if executor_events and not any(event.get("status") == "passed" for event in executor_events):
        lines.append("- executor: no passed executor event recorded")
    if not executor_events and not _iteration_skipped_executor(iteration_result):
        lines.append("- executor: no executor event recorded")
    for event in executor_events:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if event.get("status") == "passed" and metadata.get("has_executor_brief") is False:
            lines.append("- executor: passed without planner brief injection; verify planner artifact handoff")
            break
    latest_critic_by_slide: dict[object, dict] = {}
    for event in critic_events:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        latest_critic_by_slide[metadata.get("slide", "unknown")] = event
    for event in latest_critic_by_slide.values():
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if event.get("status") == "passed" and metadata.get("severity") in {"major", "critical"}:
            lines.append("- visual-critic: passed feedback contains repair-worthy severity; run repair-feedback or iterate-ai")
            break


def _append_iteration_result_diagnosis(lines: list[str], result: dict) -> None:
    feedback = result.get("latest_visual_feedback") if isinstance(result.get("latest_visual_feedback"), dict) else {}
    parts = [
        f"status={result.get('status', 'unknown')}",
        f"strict={'yes' if result.get('strict_qa') else 'no'}",
        f"ok-gate={'yes' if result.get('require_visual_ok') else 'no'}",
        f"latest-sev={result.get('latest_visual_severity') or '-'}",
    ]
    if feedback:
        repair_prompts = feedback.get("repair_prompt_count", "-")
        actionable_repairs = feedback.get("actionable_repair_count")
        parts.extend([
            f"issues={feedback.get('issue_count', '-')}",
            f"non-ok={feedback.get('non_ok_count', '-')}",
            f"repairs={repair_prompts}",
        ])
        if actionable_repairs not in {None, "", repair_prompts}:
            parts.append(f"actionable-repairs={actionable_repairs}")
    if result.get("error"):
        parts.append(f"error={_format_metadata_value(result['error'])}")
    lines.append(f"- iteration: {' | '.join(parts)}")


def _current_smoke_result(project: Path, events: list[dict]) -> dict | None:
    path = project / "qa" / "AI-SMOKE.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("trace_events") or -1) != len(events):
        return None
    return payload


def _append_smoke_result_diagnosis(lines: list[str], result: dict) -> None:
    parts = [
        f"status={result.get('status', 'unknown')}",
        f"visual={'yes' if result.get('visual_critic') else 'no'}",
        f"ok-gate={'yes' if result.get('require_visual_ok') else 'no'}",
    ]
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    if metrics:
        parts.extend([
            f"latest-sev={metrics.get('max_visual_severity') or '-'}",
            f"failed={metrics.get('failed_events', '-')}",
            f"block={metrics.get('blocking_count', '-')}",
        ])
    if result.get("error"):
        parts.append(f"error={_format_metadata_value(result['error'])}")
    lines.append(f"- smoke: {' | '.join(parts)}")


def _iteration_skipped_executor(result: dict | None) -> bool:
    """True when iterate-ai reviewed slides but no repair target required executor work."""
    if not isinstance(result, dict):
        return False
    cycles = result.get("repair_cycles")
    if not isinstance(cycles, list) or not cycles:
        return False
    for cycle in cycles:
        if not isinstance(cycle, dict):
            return False
        repaired = cycle.get("repaired")
        if repaired:
            return False
    return True


def _latest_visual_repair_gate(events: list[dict], *, visual_ok_gate: bool = False) -> dict | None:
    latest_by_slide: dict[object, dict] = {}
    for event in events:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if event.get("stage") == "visual-critic":
            latest_by_slide[metadata.get("slide", "unknown")] = event
    for event in reversed(list(latest_by_slide.values())):
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        gated = {"minor", "major", "critical"} if visual_ok_gate else {"major", "critical"}
        if metadata.get("severity") in gated:
            return event
    return None


def _append_sidecar_diagnosis(lines: list[str], project: Path, events: list[dict], *, start_index: int = 0) -> None:
    missing: list[str] = []
    empty_raw: list[str] = []
    for index, event in enumerate(events, start=start_index + 1):
        for key in ("prompt_path", "raw_path", "request_path"):
            value = event.get(key)
            if value and not (project / "qa" / value).exists():
                missing.append(f"event {index} {key}={value}")
        if event.get("raw_path") and int(event.get("raw_chars") or 0) == 0:
            empty_raw.append(f"event {index}")
    if missing:
        lines.append(f"- missing-sidecars: {_format_metadata_value(missing)}")
    if empty_raw:
        lines.append(f"- empty-raw: {_format_metadata_value(empty_raw)}")


def _append_visual_repair_targets(lines: list[str], project: Path, *, min_severity: str) -> None:
    targets = visual_repair_targets(project, min_severity=min_severity)
    if not targets:
        return
    command_project = format_cli_path(project)
    lines.append(f"- repair-targets: {len(targets)} slide(s) at severity >= {min_severity}")
    for target in targets[:3]:
        parts = [
            f"slide={target['slide']}",
            f"severity={target['severity']}",
        ]
        if target["summary"]:
            parts.append(f"summary={target['summary']}")
        if target.get("repair_source"):
            parts.append(f"source={target['repair_source']}")
        if target["repair"]:
            parts.append(f"repair={target['repair']}")
        lines.append(f"- repair-target: {' | '.join(parts)}")
    if len(targets) > 3:
        lines.append(f"- repair-targets-more: {len(targets) - 3} additional slide(s); inspect qa/visual-feedback.json")
    lines.append(f"- repair-command: slide-skill repair-feedback {command_project} --min-severity {min_severity}")


def visual_repair_targets(project_path: Path | str, *, min_severity: str) -> list[dict[str, str]]:
    """Return compact visual repair targets from ``qa/visual-feedback.json``."""
    project = Path(project_path)
    feedback_path = project / "qa" / "visual-feedback.json"
    if not feedback_path.exists():
        return []
    try:
        payload = json.loads(feedback_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    slides = payload.get("slides", []) if isinstance(payload, dict) else []
    if not isinstance(slides, list):
        return []

    severity_rank = {"ok": 0, "minor": 1, "major": 2, "critical": 3}
    threshold = severity_rank.get(min_severity, 2)
    targets: list[dict[str, str]] = []
    for index, item in enumerate(slides, start=1):
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "").strip().lower()
        rank = severity_rank.get(severity)
        if rank is None or rank < threshold:
            continue
        repair, repair_source = _visual_repair_text(item)
        summary = str(item.get("summary") or "").strip()
        if not repair:
            continue
        slide = item.get("slide") or item.get("slide_index") or item.get("page") or item.get("index") or index
        targets.append({
            "slide": str(slide),
            "severity": severity,
            "summary": _compact_repair_text(summary),
            "repair": _compact_repair_text(repair),
            "repair_source": repair_source,
        })
    return targets


def _visual_repair_text(item: dict) -> tuple[str, str]:
    repair = str(item.get("repair_prompt") or "").strip()
    if repair:
        return repair, "repair_prompt"
    actions = item.get("actions")
    if isinstance(actions, list):
        parts = [_flatten_repair_action(action) for action in actions]
        repair = "; ".join(part for part in parts if part)
        return repair, "actions" if repair else ""
    action = item.get("action")
    repair = _flatten_repair_action(action)
    return repair, "action" if repair else ""


def _flatten_repair_action(value) -> str:
    """Return executor-ready text from scalar or nested visual repair actions."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "; ".join(part for item in value if (part := _flatten_repair_action(item)))
    if isinstance(value, dict):
        preferred_keys = (
            "instruction",
            "repair",
            "action",
            "description",
            "preserve",
            "keep",
        )
        parts = [
            str(value[key]).strip()
            for key in preferred_keys
            if key in value and str(value[key]).strip()
        ]
        if parts:
            return " ".join(parts)
        return "; ".join(
            part for key, item in value.items()
            if key not in {"slide", "slide_index", "page", "index", "severity"}
            if (part := _flatten_repair_action(item))
        )
    return str(value).strip()


def _compact_repair_text(text: str, *, limit: int = 160) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _trace_command(project: Path, event_index: int, part: str = "raw") -> str:
    return format_ai_trace_command(project, event_index=event_index, part=part)


def _format_cli_path(path: Path) -> str:
    text = str(path)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or '"' in text:
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _looks_like_provider_access_error(error: str) -> bool:
    clean = error.lower()
    access_markers = (
        "401",
        "403",
        "authenticationerror",
        "permission",
        "forbidden",
        "unauthorized",
        "unsupported image",
        "image input",
        "vision",
    )
    return any(marker in clean for marker in access_markers)


def _provider_access_next_step(event: dict) -> str:
    stage = str(event.get("stage") or "").strip().lower()
    model = str(event.get("model") or "").strip()
    current = f" Current model={model}." if model else ""
    if stage == "planner":
        return (
            "verify OPENAI_PLANNER_MODEL or --planner-model, API key, base URL, "
            f"and planner account access before changing prompts.{current}"
        )
    if stage == "executor":
        return (
            "verify OPENAI_EXECUTOR_MODEL or --executor-model, API key, base URL, "
            f"and executor account access before changing prompts or repair rules.{current}"
        )
    if stage == "visual-critic":
        return (
            "use a vision-capable OPENAI_VISION_MODEL or --vision-model with image input support "
            f"before changing prompts.{current}"
        )
    return f"verify API key, base URL, model access, and provider account status before changing prompts.{current}"


def _append_issue_specific_next_steps(lines: list[str], event: dict, metadata: dict) -> None:
    for hint in issue_specific_next_steps(event, metadata):
        lines.append(f"- next-detail: {hint}")


def issue_specific_next_steps(event: dict, metadata: dict | None = None) -> list[str]:
    """Return concrete prompt/model tuning hints for a failed AI event."""
    metadata = metadata if isinstance(metadata, dict) else {}
    stage = str(event.get("stage") or "").lower()
    issue_text = _issue_text(stage, metadata)
    hints: list[str] = []

    def add(hint: str) -> None:
        if hint not in hints:
            hints.append(hint)

    if any(marker in issue_text for marker in ("content fidelity", "missing planned content", "missing visible")):
        add(
            "Fix content fidelity before visual polish: inspect the executor brief/prompt and reduce slide item density if required text cannot fit."
        )
    if any(marker in issue_text for marker in ("layout intent", "left/right", "top/lower", "grid", "comparison layout")):
        add(
            "Fix planner-to-executor layout handoff: make layout_pattern name concrete regions such as left/right panes, grid cards, or top/lower bands."
        )
    if any(marker in issue_text for marker in ("bullet rendering", "primary title color", "text_secondary", "style token", "spec drift", "locked accent", "font safety")):
        add(
            "Fix style-token compliance: inspect the executor raw SVG and force body/bullet text to use locked body or text_secondary colors instead of title/accent colors."
        )
    if any(marker in issue_text for marker in ("invalid svg", "complete <svg", "multiple svg", "markdown fence", "prose before", "output protocol")):
        add(
            "Fix output protocol first: inspect the raw response, lower executor temperature, and keep SVG-only instructions ahead of style tuning."
        )
    if any(marker in issue_text for marker in ("repair_prompt", "generic repair", "visual critic did not return valid json", "severity ok")):
        add(
            "Fix visual-critic protocol before repair: inspect the raw vision response and use a vision-capable model that returns specific repair_prompt text or concrete actions."
        )
    if any(marker in issue_text for marker in ("source coverage", "missing anchor", "coverage anchor", "notes-only coverage")):
        add(
            "Fix planner coverage before SVG generation: inspect coverage anchors and require source phrases in slide titles or visible items."
        )
    if any(marker in issue_text for marker in ("invented numeric", "numeric grounding", "hallucinated numeric")):
        add("Fix numeric grounding: keep numeric values from source text only and inspect the planner raw response.")
    if any(marker in issue_text for marker in ("max token", "context length", "finish_reason", "length", "too many slides", "max_items")):
        add("Reduce source/slide density or increase max tokens before rewriting visual prompts.")
    if stage == "planner" and any(marker in issue_text for marker in ("json", "markdown fence", "raw json", "prose")):
        add("Fix planner protocol first: enforce JSON-only output, lower planner temperature, and inspect planner raw-response sidecars.")
    return hints[:3]


def failure_hint_alias(event: dict, metadata: dict | None = None) -> str:
    """Return a stable machine-readable failure class for an AI trace event."""
    metadata = metadata if isinstance(metadata, dict) else event.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    hints = issue_specific_next_steps(event, metadata)
    if hints:
        return _issue_hint_alias(hints[0]) or "issue-specific"
    if _looks_like_provider_access_error(str(metadata.get("error") or "")):
        return "provider-access"
    return "unclassified"


def _failure_hint_counts(events: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if event.get("status") in {"passed", "ok", "success"}:
            continue
        alias = str(event.get("failure_hint_alias") or failure_hint_alias(event))
        counts[alias] = counts.get(alias, 0) + 1
    return counts


def _annotate_trace_event(event: dict) -> dict:
    """Return a copy of the event with derived diagnostics attached."""
    if event.get("status") in {"passed", "ok", "success"}:
        return event
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    annotated = dict(event)
    annotated["failure_hint_alias"] = failure_hint_alias(event, metadata)
    return annotated


def _issue_hint_alias(hint: str) -> str:
    clean = str(hint or "")
    aliases = (
        ("Fix content fidelity before visual polish", "content-fidelity"),
        ("Fix planner-to-executor layout handoff", "layout-handoff"),
        ("Fix style-token compliance", "style-token"),
        ("Fix output protocol first", "output-protocol"),
        ("Fix visual-critic protocol before repair", "critic-protocol"),
        ("Fix planner coverage before SVG generation", "planner-coverage"),
        ("Fix numeric grounding", "numeric-grounding"),
        ("Reduce source/slide density or increase max tokens", "token-density"),
        ("Fix planner protocol first", "planner-protocol"),
    )
    for marker, alias in aliases:
        if marker in clean:
            return alias
    return ""


def _issue_text(stage: str, metadata: dict) -> str:
    parts: list[str] = [stage]
    for key in ("error", "blocking_issues", "failure_reasons", "issues", "repair_prompt", "finish_reason"):
        value = metadata.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            parts.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
        elif value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _next_event_index(trace_path: Path) -> int:
    if not trace_path.exists():
        return 1
    count = sum(1 for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip())
    return count + 1


def _write_trace_artifacts(
    qa_dir: Path,
    *,
    event_index: int,
    stage: str,
    attempt: int | None,
    prompt: str | None,
    raw: str | None,
    request: dict | None,
) -> dict:
    artifact_dir = ensure_dir(qa_dir / TRACE_ARTIFACT_DIR)
    safe_stage = _safe_name(stage)
    attempt_part = f"attempt-{attempt:02d}" if attempt is not None else "attempt-na"
    stem = f"event-{event_index:04d}-{safe_stage}-{attempt_part}"
    paths: dict[str, str] = {}
    if prompt:
        prompt_path = artifact_dir / f"{stem}.prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        paths["prompt_path"] = str(prompt_path.relative_to(qa_dir)).replace("\\", "/")
    if raw:
        raw_path = artifact_dir / f"{stem}.raw.txt"
        raw_path.write_text(raw, encoding="utf-8")
        paths["raw_path"] = str(raw_path.relative_to(qa_dir)).replace("\\", "/")
    if request:
        request_path = artifact_dir / f"{stem}.request.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths["request_path"] = str(request_path.relative_to(qa_dir)).replace("\\", "/")
    return paths


def _safe_name(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or "event"


def _format_metadata_value(value) -> str:
    if isinstance(value, list):
        text = "; ".join(str(item) for item in value[:3])
        if len(value) > 3:
            text += f"; ... {len(value) - 3} more"
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    clean = " ".join(text.split())
    if len(clean) > 220:
        return clean[:220].rstrip() + "..."
    return clean


def _excerpt(text: str | None) -> str:
    if not text:
        return ""
    clean = " ".join(text.strip().split())
    if len(clean) <= MAX_EXCERPT_CHARS:
        return clean
    return clean[:MAX_EXCERPT_CHARS].rstrip() + "..."


def _response_finish_reason(response) -> str:
    choices = _value(response, "choices")
    if not isinstance(choices, list) or not choices:
        return ""
    return str(_value(choices[0], "finish_reason") or "").strip()


def _scalar_usage(response) -> dict:
    usage = _value(response, "usage")
    if not usage:
        return {}
    fields = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    }
    result: dict = {}
    for output_key, aliases in fields.items():
        for alias in aliases:
            value = _value(usage, alias)
            if isinstance(value, int) and not isinstance(value, bool):
                result[output_key] = value
                break
    return result


def _scalar_attr(obj, key: str):
    value = _value(obj, key)
    if isinstance(value, (str, int, float, bool)) and str(value).strip():
        return value
    return ""


def _value(obj, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
