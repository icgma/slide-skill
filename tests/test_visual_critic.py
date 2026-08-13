import json
from unittest.mock import MagicMock, patch

from slide_skill.visual_critic import (
    _apply_structural_feedback_sanity,
    _parse_json_object,
    _repair_prompt_quality_issue,
    _required_chrome_quality_issue,
    _rendered_slide_images,
    _slide_expected_context,
    generate_visual_feedback,
)


def _make_project(tmp_path):
    project = tmp_path / "visual-project"
    (project / "qa" / "rendered").mkdir(parents=True)
    (project / "spec_lock.json").write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720},
        "palette": {"background": "#0F172A", "text": "#F8FAFC"},
        "font_family": "Inter, sans-serif",
    }), encoding="utf-8")
    return project


def test_finds_rendered_slide_images(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-1.jpg").write_bytes(b"jpg")
    (project / "qa" / "rendered" / "slide-02.png").write_bytes(b"png")
    (project / "qa" / "rendered" / "notes.txt").write_text("ignore", encoding="utf-8")

    images = _rendered_slide_images(project / "qa" / "rendered", slides=[2])

    assert images == [(2, project / "qa" / "rendered" / "slide-02.png")]


def test_parse_json_object_from_fenced_response():
    parsed = _parse_json_object('```json\n{"severity":"ok","issues":[]}\n```')
    assert parsed["severity"] == "ok"
    assert parsed["issues"] == []


def test_parse_json_object_from_prose_wrapped_response():
    parsed = _parse_json_object('Here is the review:\n{"severity":"ok","summary":"fine","issues":[]}\nThanks.')
    assert parsed["severity"] == "ok"
    assert parsed["summary"] == "fine"


def test_parse_json_object_handles_braces_inside_strings():
    parsed = _parse_json_object(
        'prefix {"severity":"major","summary":"Use literal {x} safely","issues":["{not a block}"],"actions":[]} suffix {"extra": true}'
    )
    assert parsed["severity"] == "major"
    assert parsed["issues"] == ["{not a block}"]


def test_generate_visual_feedback_writes_json_and_markdown(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        msg.content = json.dumps({
            "severity": "major",
            "summary": "Title is clipped.",
            "issues": ["Title touches the top edge"],
            "actions": ["Move title down by at least 24 px"],
            "repair_prompt": "Rewrite the title block 32 px lower and preserve footer alignment.",
        })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, md_path = generate_visual_feedback(
            project,
            api_key="sk-test",
            model="vision-test",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["source"] == "ai-visual-critic"
    assert payload["slides"][0]["slide"] == 1
    assert payload["slides"][0]["issues"] == ["Title touches the top edge"]
    assert payload["slides"][0]["repair_prompt"].startswith("Rewrite the title block")
    markdown = md_path.read_text(encoding="utf-8")
    assert "Move title down" in markdown
    assert "Repair prompt: Rewrite the title block" in markdown
    assert calls[0]["model"] == "vision-test"
    prompt = calls[0]["messages"][1]["content"][0]["text"]
    assert "repair_prompt" in prompt
    assert "may be empty only when actions are concrete enough" in prompt
    assert "actions must be equally concrete executor-ready repair instructions" in prompt
    content = calls[0]["messages"][1]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_visual_feedback_includes_expected_slide_context(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-02.jpg").write_bytes(b"fake-image")
    brief_dir = project / "qa" / "ai-planner"
    brief_dir.mkdir(parents=True, exist_ok=True)
    (brief_dir / "executor-brief.md").write_text(
        "# AI Executor Brief\n\n"
        "## Slide 1: Intro\n"
        "- Content:\n"
        "  - [text] Do not include this slide\n\n"
        "## Slide 2: Expected Result\n"
        "- Visual strategy: proof card with retained metric\n"
        "- Content:\n"
        "  - [metric] 42% retained users\n",
        encoding="utf-8",
    )
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        msg.content = json.dumps({
            "severity": "ok",
            "summary": "Slide matches expected content.",
            "issues": [],
            "actions": [],
            "repair_prompt": "",
        })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        generate_visual_feedback(project, api_key="sk-test", model="vision-test")

    assert "Expected Result" in _slide_expected_context(project, 2)
    prompt = calls[0]["messages"][1]["content"][0]["text"]
    assert "Expected slide content and design contract" in prompt
    assert "Expected Result" in prompt
    assert "42% retained users" in prompt
    assert "Do not include this slide" not in prompt
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert trace[-1]["metadata"]["has_expected_context"] is True


def test_generate_visual_feedback_retries_weak_feedback(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        if len(calls) == 1:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Title is clipped.",
                "issues": ["Title touches the top edge"],
                "actions": ["Move title down"],
            })
        else:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Title is clipped.",
                "issues": ["Title touches the top edge"],
                "actions": ["Move title down"],
                "repair_prompt": "Move the title block down and keep all content visible.",
            })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, _ = generate_visual_feedback(
            project,
            api_key="sk-test",
            model="vision-test",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["slides"][0]["repair_prompt"].startswith("Move the title block")
    assert len(calls) == 2
    second_prompt = calls[1]["messages"][1]["content"][0]["text"]
    assert "Critic Feedback From Previous Attempt" in second_prompt
    assert "repair_prompt" in second_prompt
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["failed", "passed"]


def test_generate_visual_feedback_accepts_specific_action_without_repair_prompt(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        msg.content = json.dumps({
            "severity": "major",
            "summary": "Title is clipped.",
            "issues": ["Title touches the top edge"],
            "actions": ["Move the title block down by at least 32 px so it no longer touches the top edge."],
            "repair_prompt": "",
        })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, md_path = generate_visual_feedback(
            project,
            api_key="sk-test",
            model="vision-test",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert payload["slides"][0]["repair_prompt"] == ""
    assert payload["slides"][0]["actions"] == [
        "Move the title block down by at least 32 px so it no longer touches the top edge."
    ]
    markdown = md_path.read_text(encoding="utf-8")
    assert "Action: Move the title block down" in markdown
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["passed"]


def test_generate_visual_feedback_accepts_scalar_action_without_repair_prompt(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        msg.content = json.dumps({
            "severity": "major",
            "summary": "Title is clipped.",
            "issues": ["Title touches the top edge"],
            "action": "Move the title block down by at least 32 px so it no longer touches the top edge.",
            "repair_prompt": "",
        })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, md_path = generate_visual_feedback(
            project,
            api_key="sk-test",
            model="vision-test",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert payload["slides"][0]["repair_prompt"] == ""
    assert payload["slides"][0]["actions"] == [
        "Move the title block down by at least 32 px so it no longer touches the top edge."
    ]
    assert "Action: Move the title block down" in md_path.read_text(encoding="utf-8")
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["passed"]


def test_generate_visual_feedback_retries_generic_action_without_repair_prompt(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        if len(calls) == 1:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Title is clipped.",
                "issues": ["Title touches the top edge"],
                "actions": ["Fix the slide"],
                "repair_prompt": "",
            })
        else:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Title is clipped.",
                "issues": ["Title touches the top edge"],
                "actions": ["Move the title block down by at least 32 px so it no longer touches the top edge."],
                "repair_prompt": "",
            })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, _ = generate_visual_feedback(
            project,
            api_key="sk-test",
            model="vision-test",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert payload["slides"][0]["actions"] == [
        "Move the title block down by at least 32 px so it no longer touches the top edge."
    ]
    second_prompt = calls[1]["messages"][1]["content"][0]["text"]
    assert "repair_prompt must be specific" in second_prompt
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["failed", "passed"]


def test_generate_visual_feedback_retries_ok_with_repair_fields(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        if len(calls) == 1:
            msg.content = json.dumps({
                "severity": "ok",
                "summary": "Mostly fine but the footer is missing.",
                "issues": ["Footer is missing"],
                "actions": ["Add footer"],
                "repair_prompt": "Add the footer back to the bottom-right corner.",
            })
        else:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Footer is missing.",
                "issues": ["Footer is missing"],
                "actions": ["Add footer"],
                "repair_prompt": "Add the footer back to the bottom-right corner.",
            })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, _ = generate_visual_feedback(
            project,
            api_key="sk-test",
            model="vision-test",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["slides"][0]["severity"] == "major"
    assert len(calls) == 2
    second_prompt = calls[1]["messages"][1]["content"][0]["text"]
    assert "Severity ok must have empty issues" in second_prompt
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["failed", "passed"]


def test_generate_visual_feedback_retries_generic_repair_prompt(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        if len(calls) == 1:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Title is clipped.",
                "issues": ["Title touches the top edge"],
                "actions": ["Move title down by at least 24 px"],
                "repair_prompt": "fix the slide",
            })
        else:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Title is clipped.",
                "issues": ["Title touches the top edge"],
                "actions": ["Move title down by at least 24 px"],
                "repair_prompt": "Move the title block down by at least 24 px so it no longer touches the top edge.",
            })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, _ = generate_visual_feedback(
            project,
            api_key="sk-test",
            model="vision-test",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["slides"][0]["repair_prompt"].startswith("Move the title block")
    assert len(calls) == 2
    second_prompt = calls[1]["messages"][1]["content"][0]["text"]
    assert "repair_prompt must be specific" in second_prompt
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["failed", "passed"]


def test_visual_feedback_retries_replacing_required_page_number_with_progress_dots(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        msg = MagicMock()
        if len(calls) == 1:
            msg.content = json.dumps({
                "severity": "major",
                "summary": "Footer should use progress dots.",
                "issues": ["Footer displays '01 / 01' instead of accent-colored progress dots"],
                "actions": ["Replace '01 / 01' with progress dots"],
                "repair_prompt": "Replace footer text '01 / 01' with two accent-colored progress dots.",
            })
        else:
            msg.content = json.dumps({
                "severity": "ok",
                "summary": "Footer page number remains visible and the slide is acceptable.",
                "issues": [],
                "actions": [],
                "repair_prompt": "",
            })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        json_path, _ = generate_visual_feedback(project, api_key="sk-test", model="vision-test")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["slides"][0]["severity"] == "ok"
    assert len(calls) == 2
    second_prompt = calls[1]["messages"][1]["content"][0]["text"]
    assert "Footer page number is required deck chrome" in second_prompt
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["failed", "passed"]


def test_required_chrome_quality_rejects_page_number_replacement():
    issue = _required_chrome_quality_issue({
        "severity": "major",
        "issues": ["Footer displays '01 / 01' instead of progress dots"],
        "actions": ["Replace page number with progress dots"],
        "repair_prompt": "Replace footer text '01 / 01' with two progress dots.",
    })

    assert "Footer page number is required" in issue


def test_structural_sanity_filters_gradient_false_positive_and_optional_progress_dot(tmp_path):
    project = _make_project(tmp_path)
    svg_dir = project / "svg_output"
    svg_dir.mkdir(exist_ok=True)
    (svg_dir / "slide_01.svg").write_text('''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="panel-gradient"><stop offset="0%" stop-color="#1E293B"/><stop offset="100%" stop-color="#0F172A"/></linearGradient>
  </defs>
  <rect x="680" y="150" width="520" height="400" fill="url(#panel-gradient)"/>
  <circle cx="60" cy="200" r="8" fill="#3B82F6"/>
</svg>''', encoding="utf-8")
    normalized = {
        "slide": 1,
        "image": "slide-01.png",
        "severity": "major",
        "summary": "Card panel violates gradient specification.",
        "issues": [
            "Right card panel uses solid #1E293B instead of required linearGradient.",
            "Missing geometric chrome dot alignment with left accent stripe",
        ],
        "actions": [
            "Replace right card fill with linearGradient from #1E293B to #0F172A.",
            "Align progress dot vertically with left accent stripe midpoint.",
        ],
        "repair_prompt": "Apply linearGradient to the right card panel and align the progress dot.",
    }

    adjusted = _apply_structural_feedback_sanity(project, 1, normalized)

    assert adjusted["severity"] == "ok"
    assert adjusted["issues"] == []
    assert adjusted["actions"] == []
    assert adjusted["repair_prompt"] == ""


def test_structural_sanity_keeps_gradient_feedback_when_svg_lacks_gradient(tmp_path):
    project = _make_project(tmp_path)
    svg_dir = project / "svg_output"
    svg_dir.mkdir(exist_ok=True)
    (svg_dir / "slide_01.svg").write_text('''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <rect x="680" y="150" width="520" height="400" fill="#1E293B"/>
</svg>''', encoding="utf-8")
    normalized = {
        "slide": 1,
        "image": "slide-01.png",
        "severity": "major",
        "summary": "Card panel violates gradient specification.",
        "issues": ["Right card panel uses solid #1E293B instead of required linearGradient."],
        "actions": ["Replace right card fill with linearGradient from #1E293B to #0F172A."],
        "repair_prompt": "Apply linearGradient to the right card panel.",
    }

    adjusted = _apply_structural_feedback_sanity(project, 1, normalized)

    assert adjusted == normalized


def test_structural_sanity_clears_stale_repair_prompt_after_partial_filter(tmp_path):
    project = _make_project(tmp_path)
    svg_dir = project / "svg_output"
    svg_dir.mkdir(exist_ok=True)
    (svg_dir / "slide_01.svg").write_text('''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="panel-gradient"><stop offset="0%" stop-color="#1E293B"/><stop offset="100%" stop-color="#0F172A"/></linearGradient>
  </defs>
  <rect x="680" y="150" width="520" height="400" fill="url(#panel-gradient)"/>
  <text x="80" y="16" fill="#F8FAFC">Quarterly Results</text>
</svg>''', encoding="utf-8")
    normalized = {
        "slide": 1,
        "image": "slide-01.png",
        "severity": "major",
        "summary": "Panel fill and title placement need repair.",
        "issues": [
            "Right card panel uses solid #1E293B instead of required linearGradient.",
            "Title is clipped against the top edge.",
        ],
        "actions": [
            "Apply linearGradient from #1E293B to #0F172A to the right card.",
            "Move title down by at least 24 px.",
        ],
        "repair_prompt": "Apply the project depth treatment to the right card panel.",
    }

    adjusted = _apply_structural_feedback_sanity(project, 1, normalized)

    assert adjusted["severity"] == "major"
    assert adjusted["issues"] == ["Title is clipped against the top edge."]
    assert adjusted["actions"] == ["Move title down by at least 24 px."]
    assert adjusted["repair_prompt"] == ""


def test_structural_sanity_filters_accent_stripe_width_false_positive(tmp_path):
    project = _make_project(tmp_path)
    svg_dir = project / "svg_output"
    svg_dir.mkdir(exist_ok=True)
    (svg_dir / "slide_01.svg").write_text('''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <rect id="background" x="0" y="0" width="1280" height="720" fill="#0F172A"/>
  <rect id="chrome-stripe" x="0" y="0" width="6" height="720" fill="#3B82F6"/>
</svg>''', encoding="utf-8")
    normalized = {
        "slide": 1,
        "image": "slide-01.png",
        "severity": "major",
        "summary": "Left accent stripe exceeds 6px width specification.",
        "issues": ["Left accent stripe width exceeds 6px specification"],
        "actions": [
            "Reduce left accent stripe width to exactly 6px",
            "Verify stripe uses #3B82F6 with no stroke",
        ],
        "repair_prompt": "Adjust the left accent stripe to 6px width using #3B82F6 fill with no stroke.",
    }

    adjusted = _apply_structural_feedback_sanity(project, 1, normalized)

    assert adjusted["severity"] == "ok"
    assert adjusted["issues"] == []
    assert adjusted["actions"] == []
    assert adjusted["repair_prompt"] == ""


def test_structural_sanity_keeps_accent_stripe_feedback_when_width_is_wrong(tmp_path):
    project = _make_project(tmp_path)
    svg_dir = project / "svg_output"
    svg_dir.mkdir(exist_ok=True)
    (svg_dir / "slide_01.svg").write_text('''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <rect id="chrome-stripe" x="0" y="0" width="12" height="720" fill="#3B82F6"/>
</svg>''', encoding="utf-8")
    normalized = {
        "slide": 1,
        "image": "slide-01.png",
        "severity": "major",
        "summary": "Left accent stripe exceeds 6px width specification.",
        "issues": ["Left accent stripe width exceeds 6px specification"],
        "actions": ["Reduce left accent stripe width to exactly 6px"],
        "repair_prompt": "Adjust the left accent stripe to 6px width.",
    }

    adjusted = _apply_structural_feedback_sanity(project, 1, normalized)

    assert adjusted == normalized


def test_structural_sanity_filters_combined_svg_proven_visual_false_positives(tmp_path):
    project = _make_project(tmp_path)
    svg_dir = project / "svg_output"
    svg_dir.mkdir(exist_ok=True)
    (svg_dir / "slide_01.svg").write_text('''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs><linearGradient id="cardGradient"><stop offset="0%" stop-color="#1E293B"/><stop offset="100%" stop-color="#0F172A"/></linearGradient></defs>
  <g id="background"><rect width="1280" height="720" fill="#0F172A"/></g>
  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="#3B82F6"/></g>
  <g id="content-body-01">
    <rect x="680" y="120" width="540" height="520" fill="url(#cardGradient)"/>
    <text x="740" y="288" fill="#94A3B8">Python 变量无需提前声明类型</text>
    <text x="740" y="358" fill="#94A3B8">常见类型包括 int、float、str 和 bool</text>
    <text x="740" y="428" fill="#94A3B8">动态类型提升入门效率，但需</text>
  </g>
  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#1E293B"/></g>
</svg>''', encoding="utf-8")
    normalized = {
        "slide": 1,
        "image": "slide-01.png",
        "severity": "major",
        "summary": "Footer height and left stripe width exceed spec limits, and card lacks gradient fill.",
        "issues": [
            "Footer bar height is significantly larger than the 32px spec",
            "Left accent stripe is much wider than the 6px spec",
            "Bullet text color appears slightly brighter than #94A3B8",
        ],
        "actions": [
            "Reduce footer bar height to exactly 32px",
            "Narrow the left accent stripe to 6px",
            "Apply linearGradient (#1E293B to #0F172A) to the card panel fill",
            "Force bullet text color to #94A3B8",
        ],
        "repair_prompt": "Set the footer height to 32px, stripe width to 6px, apply linearGradient, and ensure bullet text color is #94A3B8.",
    }

    adjusted = _apply_structural_feedback_sanity(project, 1, normalized)

    assert adjusted["severity"] == "ok"
    assert adjusted["issues"] == []
    assert adjusted["actions"] == []
    assert adjusted["repair_prompt"] == ""


def test_generate_visual_feedback_fails_without_persisting_weak_feedback(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")

    def fake_create(**kwargs):
        msg = MagicMock()
        msg.content = json.dumps({
            "severity": "major",
            "summary": "Title is clipped.",
            "issues": ["Title touches the top edge"],
            "actions": ["Move title down by at least 24 px"],
            "repair_prompt": "fix the slide",
        })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        try:
            generate_visual_feedback(
                project,
                api_key="sk-test",
                model="vision-test",
                retries=1,
            )
        except RuntimeError as exc:
            assert "failed quality gate for slide 1 after 2 attempt(s)" in str(exc)
            assert "repair_prompt must be specific" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")

    assert not (project / "qa" / "visual-feedback.json").exists()
    assert not (project / "qa" / "VISUAL-REVIEW.md").exists()
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["status"] for event in trace] == ["failed", "failed"]
    assert [event["metadata"]["error"] for event in trace] == [
        "repair_prompt must be specific enough for the SVG executor, or provide a concrete action; not a generic instruction.",
        "repair_prompt must be specific enough for the SVG executor, or provide a concrete action; not a generic instruction.",
    ]


def test_generate_visual_feedback_invalid_json_failure_keeps_raw_sidecar(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")

    def fake_create(**kwargs):
        msg = MagicMock()
        msg.content = "This is prose, not JSON."
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        try:
            generate_visual_feedback(
                project,
                api_key="sk-test",
                model="vision-test",
                retries=0,
            )
        except RuntimeError as exc:
            assert "Visual critic did not return valid JSON" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")

    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert trace[0]["status"] == "failed"
    raw_path = project / "qa" / trace[0]["raw_path"]
    assert raw_path.read_text(encoding="utf-8") == "This is prose, not JSON."


def test_generate_visual_feedback_clears_stale_ai_feedback_on_failure(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    (project / "qa" / "visual-feedback.json").write_text(json.dumps({
        "source": "ai-visual-critic",
        "slides": [{"slide": 1, "severity": "major", "issues": ["old issue"]}],
    }), encoding="utf-8")
    (project / "qa" / "VISUAL-REVIEW.md").write_text(
        "# Visual Review\n\nGenerated by AI visual critic.\n\n## Slide 1\n- Issue: old issue\n",
        encoding="utf-8",
    )

    def fake_create(**kwargs):
        msg = MagicMock()
        msg.content = json.dumps({
            "severity": "major",
            "summary": "Title is clipped.",
            "issues": ["Title touches the top edge"],
            "actions": ["Move title down by at least 24 px"],
            "repair_prompt": "fix the slide",
        })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        try:
            generate_visual_feedback(project, api_key="sk-test", model="vision-test", retries=0)
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError")

    assert not (project / "qa" / "visual-feedback.json").exists()
    assert not (project / "qa" / "VISUAL-REVIEW.md").exists()


def test_generate_visual_feedback_preserves_manual_review_on_failure(tmp_path):
    project = _make_project(tmp_path)
    (project / "qa" / "rendered" / "slide-01.jpg").write_bytes(b"fake-image")
    (project / "qa" / "visual-feedback.json").write_text(json.dumps({
        "slides": [{"slide": 1, "severity": "major", "issues": ["manual issue"]}],
    }), encoding="utf-8")
    manual_review = "# Visual Review\n\n## Slide 1\n- Manual issue\n"
    (project / "qa" / "VISUAL-REVIEW.md").write_text(manual_review, encoding="utf-8")

    def fake_create(**kwargs):
        msg = MagicMock()
        msg.content = json.dumps({
            "severity": "major",
            "summary": "Title is clipped.",
            "issues": ["Title touches the top edge"],
            "actions": ["Move title down by at least 24 px"],
            "repair_prompt": "fix the slide",
        })
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        try:
            generate_visual_feedback(project, api_key="sk-test", model="vision-test", retries=0)
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError")

    assert (project / "qa" / "visual-feedback.json").exists()
    assert json.loads((project / "qa" / "visual-feedback.json").read_text(encoding="utf-8"))["slides"][0]["issues"] == ["manual issue"]
    assert (project / "qa" / "VISUAL-REVIEW.md").read_text(encoding="utf-8") == manual_review


def test_repair_prompt_quality_accepts_chinese_overlap():
    normalized = {
        "severity": "major",
        "issues": ["标题贴近顶部边缘"],
        "actions": ["将标题下移 24 像素"],
        "repair_prompt": "将标题块下移 24 像素，确保标题不再贴近顶部边缘，并保持页脚位置不变。",
    }

    assert _repair_prompt_quality_issue(normalized) == ""


def test_generate_visual_feedback_rejects_missing_project(tmp_path):
    missing = tmp_path / "missing-project"

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=MagicMock())}):
        try:
            generate_visual_feedback(missing, api_key="sk-test")
        except FileNotFoundError as exc:
            assert "Project directory not found" in str(exc)
        else:
            raise AssertionError("expected FileNotFoundError")

    assert not missing.exists()


def test_visual_critic_command_uses_ai_gate(monkeypatch):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    result = main(["visual-critic", "missing-project"])

    assert result == 1


def test_visual_critic_command_reports_trace_hint_on_failure(monkeypatch, tmp_path, capsys):
    from slide_skill.cli import main
    from slide_skill.ai_trace import write_ai_trace

    project = _make_project(tmp_path)

    def fake_visual_feedback(project_path, **kwargs):
        write_ai_trace(
            project_path,
            stage="visual-critic",
            model=kwargs.get("model") or "vision-test",
            status="failed",
            attempt=2,
            metadata={
                "slide": 1,
                "error": "repair_prompt must be specific enough for the SVG executor.",
            },
        )
        raise RuntimeError("failed quality gate for slide 1 after 2 attempt(s)")

    monkeypatch.setattr("slide_skill.visual_critic.generate_visual_feedback", fake_visual_feedback)

    result = main([
        "visual-critic",
        str(project),
        "--ai-base-url",
        "http://127.0.0.1:11434/v1",
        "--vision-model",
        "vision-test",
    ])

    stderr = capsys.readouterr().err
    assert result == 1
    assert "failed quality gate for slide 1 after 2 attempt(s)" in stderr
    assert f"slide-skill ai-trace {project}" in stderr
    assert f"slide-skill ai-trace {project} --diagnose" in stderr
    assert "--latest-iteration --diagnose" not in stderr
    assert "last-ai-failure: stage=visual-critic | status=failed | attempt=2 | model=vision-test | slide=1" in stderr
    assert "repair_prompt must be specific enough" in stderr
