import json
import zipfile

from slide_skill.ai_trace import (
    diagnose_ai_trace,
    latest_iteration_trace_scope,
    read_ai_trace,
    read_ai_trace_part,
    summarize_ai_trace,
    write_ai_trace,
    write_ai_trace_bundle,
)


def test_ai_trace_summary_shows_interaction_metadata(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test", "messages": [{"role": "user", "content": "Create a plan"}]},
        attempt=1,
        metadata={"slides": 2, "feedback": False},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        attempt=2,
        metadata={
            "slide": 1,
            "blocking_count": 3,
            "blocking_issues": [
                "Layout intent: planner requested left/right structure but visible elements do not occupy both left and right regions",
                "Content fidelity: missing planned content item",
            ],
            "has_executor_brief": True,
            "has_visual_feedback": True,
        },
    )

    summary = summarize_ai_trace(project)
    events = read_ai_trace(project)

    assert "events: 2" in summary
    assert "1. planner" in summary
    assert "model=planner-test" in summary
    assert "slides=2" in summary
    assert "2. executor" in summary
    assert "blocking_count=3" in summary
    assert "blocking_issues=Layout intent: planner requested left/right structure" in summary
    assert "has_executor_brief=True" in summary
    assert "has_visual_feedback=True" in summary
    assert "prompt=ai-trace-artifacts/" in summary
    assert "raw=ai-trace-artifacts/" in summary
    assert "request=ai-trace-artifacts/" in summary
    assert (project / "qa" / events[0]["prompt_path"]).read_text(encoding="utf-8") == "Create a plan"
    assert (project / "qa" / events[1]["raw_path"]).read_text(encoding="utf-8") == "<svg></svg>"
    assert read_ai_trace_part(project, 1, "prompt") == "Create a plan"
    assert read_ai_trace_part(project, 2, "raw") == "<svg></svg>"
    request = json.loads(read_ai_trace_part(project, 1, "request"))
    assert request["model"] == "planner-test"


def test_ai_trace_command_outputs_summary_and_json(tmp_path, capsys):
    from slide_skill.cli import main

    project = tmp_path / "project"
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze image",
        raw='{"severity":"major"}',
        request={"model": "vision-test", "messages": [{"role": "user", "content": "Analyze image"}]},
        attempt=1,
        metadata={"slide": 1, "severity": "major"},
    )

    assert main(["ai-trace", str(project)]) == 0
    summary = capsys.readouterr().out
    assert "visual-critic" in summary
    assert "severity=major" in summary

    assert main(["ai-trace", str(project), "--json"]) == 0
    raw = capsys.readouterr().out
    events = json.loads(raw)
    assert events == read_ai_trace(project)
    assert events[0]["stage"] == "visual-critic"
    assert events[0]["prompt_path"].endswith(".prompt.txt")

    assert main(["ai-trace", str(project), "--event", "1", "--part", "prompt"]) == 0
    prompt = capsys.readouterr().out
    assert prompt == "Analyze image"

    assert main(["ai-trace", str(project), "--event", "1", "--part", "raw"]) == 0
    raw_response = capsys.readouterr().out
    assert raw_response == '{"severity":"major"}'

    assert main(["ai-trace", str(project), "--event", "1", "--part", "request"]) == 0
    request_text = capsys.readouterr().out
    assert '"model": "vision-test"' in request_text


def test_ai_trace_json_adds_failure_hint_alias(tmp_path, capsys):
    from slide_skill.cli import main

    project = tmp_path / "project"
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={
            "slide": 1,
            "blocking_issues": ["Missing visible planned content: Market size"],
        },
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=2,
        metadata={"slide": 1},
    )

    assert main(["ai-trace", str(project), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload[0]["failure_hint_alias"] == "content-fidelity"
    assert "failure_hint_alias" not in payload[1]


def test_ai_trace_bundle_includes_sidecars_and_ai_reports(tmp_path, capsys):
    from slide_skill.cli import main

    project = tmp_path / "project"
    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="failed",
        prompt="Create a plan",
        raw="not-json",
        request={"model": "planner-test", "messages": [{"role": "user", "content": "Create a plan"}]},
        attempt=1,
        metadata={"error": "AI planner did not return JSON."},
    )
    (project / "qa" / "AI-SMOKE.json").write_text(json.dumps({
        "status": "failed",
        "error": "AI planner did not return JSON.",
    }), encoding="utf-8")
    bundle = write_ai_trace_bundle(project, project / "qa" / "trace-bundle.zip")

    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        request = json.loads(zf.read("qa/ai-trace-artifacts/event-0001-planner-attempt-01.request.json").decode("utf-8"))

    assert manifest["event_count"] == 1
    assert manifest["events"][0]["event"] == 1
    assert "qa/ai-trace.jsonl" in names
    assert "qa/AI-SMOKE.json" in names
    assert "qa/ai-trace.selected-events.json" in names
    assert "qa/ai-trace-artifacts/event-0001-planner-attempt-01.prompt.txt" in names
    assert "qa/ai-trace-artifacts/event-0001-planner-attempt-01.raw.txt" in names
    assert request["model"] == "planner-test"

    cli_bundle = project / "qa" / "trace-bundle-cli.zip"
    assert main(["ai-trace", str(project), "--bundle", str(cli_bundle)]) == 0
    assert str(cli_bundle) in capsys.readouterr().out
    assert cli_bundle.exists()


def test_ai_trace_latest_iteration_scopes_summary_diagnosis_and_json(tmp_path, capsys):
    from slide_skill.cli import main

    project = tmp_path / "project"
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="failed",
        prompt="Analyze old image",
        raw="not-json",
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "error": "Visual critic did not return valid JSON."},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Repair SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "has_executor_brief": True},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze latest image",
        raw='{"severity":"ok"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "ok"},
    )
    (project / "qa" / "AI-ITERATION.json").write_text(json.dumps({
        "trace_start": 1,
        "trace_events": 2,
        "status": "passed",
        "strict_qa": True,
        "require_visual_ok": True,
        "latest_visual_severity": "ok",
        "latest_visual_feedback": {
            "issue_count": 0,
            "non_ok_count": 0,
            "repair_prompt_count": 0,
            "actionable_repair_count": 0,
        },
    }), encoding="utf-8")

    events, start_index, label, iteration_result = latest_iteration_trace_scope(project)
    scoped_summary = summarize_ai_trace(project, events, start_index=start_index, scope_label=label)
    scoped_diagnosis = diagnose_ai_trace(
        project,
        events,
        start_index=start_index,
        scope_label=label,
        iteration_result=iteration_result,
    )

    assert len(events) == 2
    assert start_index == 1
    assert "latest iteration, events 2-3" in scoped_summary
    assert "2. executor" in scoped_summary
    assert "3. visual-critic" in scoped_summary
    assert "1. visual-critic" not in scoped_summary
    assert "latest iteration, events 2-3" in scoped_diagnosis
    assert "- iteration: status=passed | strict=yes | ok-gate=yes | latest-sev=ok | issues=0 | non-ok=0 | repairs=0" in scoped_diagnosis
    assert "latest-failure" not in scoped_diagnosis
    assert "planner: no passed planner event recorded" not in scoped_diagnosis
    assert "- result: all recorded AI events passed their current gates" in scoped_diagnosis

    assert main(["ai-trace", str(project), "--latest-iteration", "--diagnose"]) == 0
    output = capsys.readouterr().out
    assert "latest iteration, events 2-3" in output
    assert "iteration: status=passed | strict=yes | ok-gate=yes | latest-sev=ok" in output
    assert "Visual critic did not return valid JSON" not in output

    assert main(["ai-trace", str(project), "--latest-iteration", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [event["stage"] for event in payload] == ["executor", "visual-critic"]

    bundle = project / "qa" / "latest-iteration-bundle.zip"
    assert main(["ai-trace", str(project), "--latest-iteration", "--bundle", str(bundle)]) == 0
    with zipfile.ZipFile(bundle) as zf:
        selected = json.loads(zf.read("qa/ai-trace.selected-events.json").decode("utf-8"))
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert [event["stage"] for event in selected] == ["executor", "visual-critic"]
    assert manifest["scope"] == "latest iteration, events 2-3"
    assert [event["event"] for event in manifest["events"]] == [2, 3]


def test_ai_trace_diagnosis_marks_scoped_retry_recovered_without_planner_noise(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="failed",
        prompt="Analyze",
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "error": "Visual critic did not return valid JSON."},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"ok"}',
        request={"model": "vision-test"},
        attempt=2,
        metadata={"slide": 1, "severity": "ok"},
    )

    diagnosis = diagnose_ai_trace(project)
    scoped_diagnosis = diagnose_ai_trace(project, read_ai_trace(project), start_index=4, scope_label="latest iteration, events 5-6")

    assert "- recovered-failure: event=1 | stage=visual-critic | attempt=1 | model=vision-test | slide=1" in diagnosis
    assert "- recovered-failure: event=5 | stage=visual-critic | attempt=1 | model=vision-test | slide=1" in scoped_diagnosis
    assert "- failure-hints: critic-protocol=1" in diagnosis
    assert "- failure-hints: critic-protocol=1" in scoped_diagnosis
    assert f"- inspect-event: slide-skill ai-trace {project} --event 1 --part raw" in diagnosis
    assert f"- inspect-event: slide-skill ai-trace {project} --event 5 --part raw" in scoped_diagnosis
    assert "- recovered-error: Visual critic did not return valid JSON." in diagnosis
    assert "- note: later AI events passed after this failure; treat it as historical retry evidence unless current QA is failing" in diagnosis
    assert "- result: latest recorded AI event passed; earlier failures in this scope were recovered by retry" in diagnosis
    assert "planner: no passed planner event recorded" not in diagnosis


def test_ai_trace_summary_reports_failure_hint_counts(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={
            "slide": 1,
            "blocking_issues": ["Missing visible planned content: Market size"],
        },
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=2,
        metadata={
            "slide": 2,
            "blocking_issues": ["Bullet rendering uses primary title color"],
        },
    )

    summary = summarize_ai_trace(project)

    assert "failure-hints: content-fidelity=1, style-token=1" in summary


def test_latest_iteration_diagnosis_does_not_require_executor_when_no_repair_needed(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"ok"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "ok"},
    )

    diagnosis = diagnose_ai_trace(
        project,
        read_ai_trace(project),
        iteration_result={
            "status": "passed",
            "strict_qa": True,
            "require_visual_ok": True,
            "latest_visual_severity": "ok",
            "repair_cycles": [{"round": 1, "repaired": []}],
            "latest_visual_feedback": {
                "issue_count": 0,
                "non_ok_count": 0,
                "repair_prompt_count": 0,
                "actionable_repair_count": 0,
            },
        },
    )

    assert "- iteration: status=passed | strict=yes | ok-gate=yes | latest-sev=ok | issues=0 | non-ok=0 | repairs=0" in diagnosis
    assert "executor: no executor event recorded" not in diagnosis
    assert "- result: all recorded AI events passed their current gates" in diagnosis


def test_latest_iteration_diagnosis_surfaces_actionable_repair_count(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"major"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "major"},
    )

    diagnosis = diagnose_ai_trace(
        project,
        read_ai_trace(project),
        iteration_result={
            "status": "failed",
            "strict_qa": True,
            "require_visual_ok": False,
            "latest_visual_severity": "major",
            "latest_visual_feedback": {
                "issue_count": 1,
                "non_ok_count": 1,
                "repair_prompt_count": 0,
                "actionable_repair_count": 1,
            },
        },
    )

    assert "- iteration: status=failed | strict=yes | ok-gate=no | latest-sev=major | issues=1 | non-ok=1 | repairs=0 | actionable-repairs=1" in diagnosis


def test_ai_trace_diagnosis_flags_latest_failure_and_missing_sidecars(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test"},
        attempt=1,
        metadata={"slides": 1},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=2,
        metadata={
            "slide": 1,
            "blocking_count": 2,
            "blocking_issues": ["Content fidelity: missing planned content item"],
            "has_executor_brief": True,
        },
    )
    events = read_ai_trace(project)
    missing_request = project / "qa" / events[1]["request_path"]
    missing_request.unlink()

    diagnosis = diagnose_ai_trace(project)

    assert "AI trace diagnosis:" in diagnosis
    assert "- stages: executor=1, planner=1" in diagnosis
    assert "- statuses: failed=1, passed=1" in diagnosis
    assert "- latest-failure: event=2 | stage=executor | attempt=2 | model=executor-test | slide=1" in diagnosis
    assert f"- inspect-event: slide-skill ai-trace {project} --event 2 --part raw" in diagnosis
    assert "- blocking-issues: Content fidelity: missing planned content item" in diagnosis
    assert "- next: inspect the latest failure prompt/raw sidecars before changing prompts" in diagnosis
    assert "- next-detail: Fix content fidelity before visual polish" in diagnosis
    assert "- executor: no passed executor event recorded" in diagnosis
    assert "- missing-sidecars: event 2 request_path=" in diagnosis


def test_ai_trace_diagnosis_adds_planner_json_protocol_next_detail(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="failed",
        prompt="Create a plan",
        raw="```json\n{}\n```",
        request={"model": "planner-test"},
        attempt=2,
        metadata={"error": "Planner did not return raw JSON: markdown fence found."},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- latest-failure: event=1 | stage=planner | attempt=2 | model=planner-test" in diagnosis
    assert "- next-detail: Fix planner protocol first: enforce JSON-only output" in diagnosis


def test_ai_trace_diagnosis_adds_visual_critic_repair_prompt_next_detail(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="failed",
        prompt="Analyze image",
        raw='{"severity":"major","issues":["crowded"]}',
        request={"model": "vision-test"},
        attempt=2,
        metadata={
            "slide": 1,
            "error": "Visual critic feedback missing repair_prompt for non-ok slide.",
        },
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- latest-failure: event=1 | stage=visual-critic | attempt=2 | model=vision-test | slide=1" in diagnosis
    assert "- next-detail: Fix visual-critic protocol before repair" in diagnosis
    assert "repair_prompt text or concrete actions" in diagnosis


def test_ai_trace_diagnosis_surfaces_visual_repair_targets(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze image",
        raw='{"severity":"major"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "major"},
    )
    (project / "qa" / "visual-feedback.json").write_text(json.dumps({
        "source": "ai-visual-critic",
        "slides": [
            {
                "slide": 1,
                "severity": "major",
                "summary": "Title is clipped against the top edge.",
                "issues": ["Title clipping"],
                "actions": ["Move title lower"],
                "repair_prompt": "Move the title block down 32 px while preserving the footer.",
            },
            {
                "slide": 2,
                "severity": "minor",
                "summary": "Small spacing issue.",
                "repair_prompt": "Add more whitespace.",
            },
        ],
    }), encoding="utf-8")

    diagnosis = diagnose_ai_trace(project)

    assert "- active-repair-gate: event=1 | stage=visual-critic | slide=1 | severity=major" in diagnosis
    assert "- repair-targets: 1 slide(s) at severity >= major" in diagnosis
    assert "- repair-target: slide=1 | severity=major | summary=Title is clipped against the top edge. | source=repair_prompt | repair=Move the title block down 32 px while preserving the footer." in diagnosis
    assert f"- repair-command: slide-skill repair-feedback {project} --min-severity major" in diagnosis
    assert "slide=2 | severity=minor" not in diagnosis


def test_visual_repair_targets_require_actionable_repair_text(tmp_path):
    from slide_skill.ai_trace import visual_repair_targets

    project = tmp_path / "project"
    (project / "qa").mkdir(parents=True)
    (project / "qa" / "visual-feedback.json").write_text(json.dumps({
        "source": "ai-visual-critic",
        "slides": [
            {
                "slide": 1,
                "severity": "major",
                "summary": "Title hierarchy is weak.",
                "issues": ["Title hierarchy is weak"],
            },
            {
                "slide": 2,
                "severity": "major",
                "summary": "Footer is missing.",
                "actions": ["Add the footer page number to the bottom-right corner."],
            },
        ],
    }), encoding="utf-8")

    targets = visual_repair_targets(project, min_severity="major")

    assert targets == [{
        "slide": "2",
        "severity": "major",
        "summary": "Footer is missing.",
        "repair": "Add the footer page number to the bottom-right corner.",
        "repair_source": "actions",
    }]


def test_visual_repair_targets_flatten_nested_actions(tmp_path):
    from slide_skill.ai_trace import visual_repair_targets

    project = tmp_path / "project"
    (project / "qa").mkdir(parents=True)
    (project / "qa" / "visual-feedback.json").write_text(json.dumps({
        "source": "ai-visual-critic",
        "slides": [
            {
                "slide": 1,
                "severity": "major",
                "summary": "Title and body are crowded.",
                "actions": [
                    {
                        "target": "title",
                        "instruction": "Move the title block down by 32 px.",
                        "preserve": "Keep the footer page number visible.",
                    },
                    {
                        "target": "body",
                        "repair": "Increase the gap between body rows to at least 24 px.",
                    },
                ],
                "repair_prompt": "",
            },
        ],
    }), encoding="utf-8")

    targets = visual_repair_targets(project, min_severity="major")

    assert targets == [{
        "slide": "1",
        "severity": "major",
        "summary": "Title and body are crowded.",
        "repair": (
            "Move the title block down by 32 px. Keep the footer page number visible.; "
            "Increase the gap between body rows to at least 24 px."
        ),
        "repair_source": "actions",
    }]
    assert "{" not in targets[0]["repair"]


def test_ai_trace_diagnosis_surfaces_minor_targets_for_visual_ok_gate(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze image",
        raw='{"severity":"minor"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "minor"},
    )
    (project / "qa" / "AI-SMOKE.json").write_text(json.dumps({
        "status": "failed",
        "require_visual_ok": True,
        "visual_critic": True,
        "trace_events": 1,
    }), encoding="utf-8")
    (project / "qa" / "visual-feedback.json").write_text(json.dumps({
        "source": "ai-visual-critic",
        "slides": [
            {
                "slide": 1,
                "severity": "minor",
                "summary": "Bullets are slightly crowded.",
                "repair_prompt": "Increase vertical gap between bullet rows by 12 px.",
            },
        ],
    }), encoding="utf-8")

    diagnosis = diagnose_ai_trace(project)

    assert "- visual-ok-gate: event=1 | stage=visual-critic | slide=1 | severity=minor" in diagnosis
    assert "- repair-targets: 1 slide(s) at severity >= minor" in diagnosis
    assert "- repair-target: slide=1 | severity=minor | summary=Bullets are slightly crowded. | source=repair_prompt | repair=Increase vertical gap between bullet rows by 12 px." in diagnosis
    assert f"- repair-command: slide-skill repair-feedback {project} --min-severity minor" in diagnosis


def test_latest_iteration_diagnosis_surfaces_minor_visual_ok_repair_targets(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze image",
        raw='{"severity":"minor"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "minor"},
    )
    (project / "qa" / "AI-ITERATION.json").write_text(json.dumps({
        "trace_start": 0,
        "trace_events": 1,
        "status": "failed",
        "strict_qa": False,
        "require_visual_ok": True,
        "latest_visual_severity": "minor",
        "latest_visual_feedback": {
            "issue_count": 1,
            "non_ok_count": 1,
            "repair_prompt_count": 1,
        },
    }), encoding="utf-8")
    (project / "qa" / "visual-feedback.json").write_text(json.dumps({
        "source": "ai-visual-critic",
        "slides": [
            {
                "slide": 1,
                "severity": "minor",
                "summary": "Footer alignment is slightly off.",
                "repair_prompt": "Align the footer baseline with the progress indicator by 8 px.",
            },
        ],
    }), encoding="utf-8")

    events, start_index, label, iteration_result = latest_iteration_trace_scope(project)
    diagnosis = diagnose_ai_trace(
        project,
        events,
        start_index=start_index,
        scope_label=label,
        iteration_result=iteration_result,
    )

    assert "- iteration: status=failed | strict=no | ok-gate=yes | latest-sev=minor | issues=1 | non-ok=1 | repairs=1" in diagnosis
    assert "- visual-ok-gate: event=1 | stage=visual-critic | slide=1 | severity=minor" in diagnosis
    assert "- repair-targets: 1 slide(s) at severity >= minor" in diagnosis
    assert "- repair-target: slide=1 | severity=minor | summary=Footer alignment is slightly off. | source=repair_prompt | repair=Align the footer baseline with the progress indicator by 8 px." in diagnosis
    assert "- result: AI visual-ok gate is still failing despite passed model calls" in diagnosis


def test_ai_trace_diagnosis_quotes_project_path_with_spaces(tmp_path):
    project = tmp_path / "project with spaces"

    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "blocking_issues": ["Text overflow"]},
    )

    diagnosis = diagnose_ai_trace(project)

    assert f'- inspect-event: slide-skill ai-trace "{project}" --event 1 --part raw' in diagnosis


def test_ai_trace_diagnosis_reports_clean_pass_and_brief_handoff(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test"},
        attempt=1,
        metadata={"slides": 1},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "has_executor_brief": False},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- result: all recorded AI events passed their current gates" in diagnosis
    assert "- executor: passed without planner brief injection" in diagnosis


def test_ai_trace_diagnosis_uses_latest_visual_critic_per_slide(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test"},
        attempt=1,
        metadata={"slides": 1},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "has_executor_brief": True},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"critical"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "critical"},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"ok"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "ok"},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "repair-feedback" not in diagnosis
    assert "- result: all recorded AI events passed their current gates" in diagnosis


def test_ai_trace_diagnosis_clears_visual_repair_gate_after_latest_ok(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="failed",
        prompt="Create a plan",
        raw="{}",
        request={"model": "planner-test"},
        attempt=1,
        metadata={"error": "source coverage missing required anchor"},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"major"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "major"},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"ok"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "ok"},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- recovered-failure: event=1 | stage=planner" in diagnosis
    assert "active-repair-gate" not in diagnosis
    assert "run repair-feedback or iterate-ai" not in diagnosis


def test_ai_trace_diagnosis_marks_resolved_retry_failures_as_historical(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "blocking_issues": ["Text overflow"]},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=2,
        metadata={"slide": 1, "blocking_count": 0},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"ok"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "ok"},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- recovered-failure: event=1 | stage=executor" in diagnosis
    assert "- note: later AI events passed after this failure; treat it as historical retry evidence unless current QA is failing" in diagnosis
    assert "- next: inspect the latest failure prompt/raw sidecars before changing prompts" not in diagnosis


def test_ai_trace_recovered_executor_style_token_failure_has_next_detail(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={
            "slide": 1,
            "blocking_count": 1,
            "blocking_issues": [
                "Bullet rendering: bullet body text uses primary title color #F1F5F9; use body/text_secondary color #94A3B8"
            ],
        },
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG with feedback",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=2,
        metadata={"slide": 1, "blocking_count": 0, "has_qa_feedback": True},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- recovered-failure: event=1 | stage=executor | attempt=1 | model=executor-test | slide=1" in diagnosis
    assert "- next-detail: Fix style-token compliance" in diagnosis


def test_ai_trace_diagnosis_prioritizes_active_visual_repair_gate_after_retry_failure(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="failed",
        prompt="Create a plan",
        raw="{}",
        request={"model": "planner-test"},
        attempt=1,
        metadata={"error": "source coverage missing required anchor"},
    )
    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test"},
        attempt=2,
        metadata={"slides": 1},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"major"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "major"},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- latest-failure: event=1 | stage=planner" in diagnosis
    assert "- active-repair-gate: event=3 | stage=visual-critic | slide=1 | severity=major" in diagnosis
    assert f"- inspect-repair-gate: slide-skill ai-trace {project} --event 3 --part raw" in diagnosis
    assert "- next: run repair-feedback or iterate-ai before tuning earlier successful stages" in diagnosis


def test_ai_trace_diagnosis_adds_inspect_command_for_passed_repair_gate(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "has_executor_brief": True},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"major"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "major"},
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- active-repair-gate: event=2 | stage=visual-critic | slide=1 | severity=major" in diagnosis
    assert f"- inspect-repair-gate: slide-skill ai-trace {project} --event 2 --part raw" in diagnosis


def test_ai_trace_diagnosis_uses_current_smoke_visual_ok_gate(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test"},
        attempt=1,
        metadata={"slides": 1},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "has_executor_brief": True},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"minor"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "minor"},
    )
    (project / "qa" / "AI-SMOKE.json").write_text(json.dumps({
        "status": "failed",
        "error": "AI smoke visual-ok gate failed: latest visual severity is minor",
        "visual_critic": True,
        "require_visual_ok": True,
        "trace_events": 3,
        "metrics": {
            "failed_events": 0,
            "blocking_count": 0,
            "max_visual_severity": "minor",
        },
    }), encoding="utf-8")

    diagnosis = diagnose_ai_trace(project)

    assert "- smoke: status=failed | visual=yes | ok-gate=yes | latest-sev=minor | failed=0 | block=0" in diagnosis
    assert "- visual-ok-gate: event=3 | stage=visual-critic | slide=1 | severity=minor" in diagnosis
    assert f"- inspect-repair-gate: slide-skill ai-trace {project} --event 3 --part raw" in diagnosis
    assert "- result: AI smoke visual-ok gate is still failing despite passed model calls" in diagnosis
    assert "- result: all recorded AI events passed their current gates" not in diagnosis


def test_ai_trace_diagnosis_ignores_stale_smoke_result(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="visual-critic",
        model="vision-test",
        status="passed",
        prompt="Analyze",
        raw='{"severity":"minor"}',
        request={"model": "vision-test"},
        attempt=1,
        metadata={"slide": 1, "severity": "minor"},
    )
    (project / "qa" / "AI-SMOKE.json").write_text(json.dumps({
        "status": "failed",
        "visual_critic": True,
        "require_visual_ok": True,
        "trace_events": 99,
        "metrics": {"max_visual_severity": "minor"},
    }), encoding="utf-8")

    diagnosis = diagnose_ai_trace(project)

    assert "- smoke:" not in diagnosis
    assert "visual-ok-gate" not in diagnosis
    assert "- result: all recorded AI events passed their current gates" in diagnosis


def test_ai_trace_diagnosis_flags_visual_provider_access_failure(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test"},
        attempt=1,
        metadata={"slides": 1},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="passed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "has_executor_brief": True},
    )
    write_ai_trace(
        project,
        stage="visual-critic",
        model="text-only-model",
        status="failed",
        prompt="Analyze image",
        request={"model": "text-only-model"},
        attempt=2,
        metadata={
            "slide": 1,
            "provider_error": True,
            "error": "AuthenticationError: Error code: 401 - {'error': {'message': 'Forbidden'}}",
        },
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- latest-failure: event=3 | stage=visual-critic | attempt=2 | model=text-only-model | slide=1" in diagnosis
    assert "- next: use a vision-capable OPENAI_VISION_MODEL or --vision-model with image input support before changing prompts. Current model=text-only-model." in diagnosis
    assert "- next: inspect the latest failure prompt/raw sidecars before changing prompts" not in diagnosis


def test_ai_trace_diagnosis_flags_text_provider_access_failure(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="text-model",
        status="failed",
        prompt="Create a plan",
        request={"model": "text-model"},
        attempt=2,
        metadata={
            "provider_error": True,
            "error": "AuthenticationError: Error code: 401 - {'error': {'message': 'Forbidden'}}",
        },
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- latest-failure: event=1 | stage=planner | attempt=2 | model=text-model" in diagnosis
    assert "- next: verify OPENAI_PLANNER_MODEL or --planner-model, API key, base URL, and planner account access before changing prompts. Current model=text-model." in diagnosis
    assert "- next: inspect the latest failure prompt/raw sidecars before changing prompts" not in diagnosis


def test_ai_trace_diagnosis_flags_executor_provider_access_failure(tmp_path):
    project = tmp_path / "project"

    write_ai_trace(
        project,
        stage="planner",
        model="planner-test",
        status="passed",
        prompt="Create a plan",
        raw='{"slides":[]}',
        request={"model": "planner-test"},
        attempt=1,
        metadata={"slides": 1},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="blocked-executor-model",
        status="failed",
        prompt="Create SVG",
        request={"model": "blocked-executor-model"},
        attempt=1,
        metadata={
            "slide": 1,
            "provider_error": True,
            "error": "PermissionDeniedError: Error code: 403 - model access forbidden",
        },
    )

    diagnosis = diagnose_ai_trace(project)

    assert "- latest-failure: event=2 | stage=executor | attempt=1 | model=blocked-executor-model | slide=1" in diagnosis
    assert "- next: verify OPENAI_EXECUTOR_MODEL or --executor-model, API key, base URL, and executor account access before changing prompts or repair rules. Current model=blocked-executor-model." in diagnosis
    assert "- next: inspect the latest failure prompt/raw sidecars before changing prompts" not in diagnosis


def test_ai_trace_command_outputs_diagnosis(tmp_path, capsys):
    from slide_skill.cli import main

    project = tmp_path / "project"
    write_ai_trace(
        project,
        stage="executor",
        model="executor-test",
        status="failed",
        prompt="Create SVG",
        raw="<svg></svg>",
        request={"model": "executor-test"},
        attempt=1,
        metadata={"slide": 1, "blocking_count": 1},
    )

    assert main(["ai-trace", str(project), "--diagnose"]) == 0
    output = capsys.readouterr().out

    assert "AI trace diagnosis:" in output
    assert "latest-failure: event=1 | stage=executor" in output
