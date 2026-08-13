import json
from unittest.mock import MagicMock, patch

from slide_skill.ai_planner import plan_slides_with_ai
from slide_skill.content_planner import ContentConfig


def _fake_response(payload):
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _fake_text_response(text):
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_ai_planner_converts_json_to_slide_plans(tmp_path):
    project = tmp_path / "project"
    (project / "qa").mkdir(parents=True)
    (project / "spec_lock.json").write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720},
        "palette": {"accent": "#3B82F6"},
    }), encoding="utf-8")

    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "cover",
                "title": "AI Strategy",
                "density": "sparse",
                "rhythm": "anchor",
                "visual_strategy": "hero thesis with diagonal accent rail",
                "layout_pattern": "large title left with full-bleed accent rail",
                "items": [{"type": "text", "primary": "Main argument"}],
            },
            {
                "index": 2,
                "layout": "metric-highlight",
                "title": "Impact",
                "visual_strategy": "oversized metric with source-backed supporting label",
                "layout_pattern": "left metric block with right explanatory note",
                "items": [{"type": "metric", "primary": "Impact improved 42%", "secondary": "improvement"}],
            },
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\nAI improves planning.\n\n- Impact improved 42%.",
            ContentConfig(max_slides=5),
            project_path=project,
            api_key="sk-test",
        )

    assert [plan.index for plan in plans] == [1, 2]
    assert plans[0].layout == "cover"
    assert plans[0].rhythm == "anchor"
    assert plans[0].items[0].primary == "Main argument"
    assert plans[1].items[0].type == "metric"
    assert (project / "qa" / "ai-planner" / "plan.json").exists()
    brief = (project / "qa" / "ai-planner" / "executor-brief.md").read_text(encoding="utf-8")
    assert "AI Executor Brief" in brief
    assert "Visual strategy: hero thesis with diagonal accent rail" in brief
    assert "Layout pattern: left metric block with right explanatory note" in brief
    assert (project / "qa" / "ai-planner" / "attempt_01.json").exists()
    trace = (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8")
    assert '"stage": "planner"' in trace
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Source Markdown" in prompt
    assert "max items per slide" in prompt


def test_ai_planner_accepts_top_level_slide_array(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = [
        {
            "index": 1,
            "layout": "cover",
            "title": "Array Plan",
            "visual_strategy": "hero title with diagonal accent rail",
            "layout_pattern": "large title left with proof card right",
            "items": [{"type": "text", "primary": "Array details"}],
        }
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\nArray details.",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert len(plans) == 1
    assert plans[0].title == "Array Plan"
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert persisted[0]["title"] == "Array Plan"
    brief = (project / "qa" / "ai-planner" / "executor-brief.md").read_text(encoding="utf-8")
    assert "## Slide 1: Array Plan" in brief


def test_ai_planner_accepts_labelled_string_indexes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": "Slide 1",
                "layout": "cover",
                "title": "Launch Plan",
                "visual_strategy": "hero title with diagonal accent rail",
                "layout_pattern": "large title left with proof card right",
                "items": [{"type": "text", "primary": "Launch details"}],
            },
            {
                "index": "slide_02",
                "layout": "metric-highlight",
                "title": "Adoption",
                "visual_strategy": "large metric with compact source-backed explanation",
                "layout_pattern": "metric left with supporting bullet stack right",
                "items": [{"type": "metric", "primary": "Adoption reached 42%"}],
            },
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\nLaunch details.\n\nAdoption reached 42%.",
            ContentConfig(max_slides=5),
            project_path=project,
            api_key="sk-test",
        )

    assert [plan.index for plan in plans] == [1, 2]
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert [slide["index"] for slide in persisted] == [1, 2]


def test_ai_planner_normalizes_string_items(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "bullet-list",
                "title": "Launch Details",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "items": ["Alpha milestone", "Beta rollout"],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\n\n- Alpha milestone\n- Beta rollout",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert [(item.type, item.primary) for item in plans[0].items] == [
        ("text", "Alpha milestone"),
        ("text", "Beta rollout"),
    ]
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert persisted[0]["items"] == [
        {"type": "text", "primary": "Alpha milestone", "secondary": "", "tertiary": "", "meta": {}},
        {"type": "text", "primary": "Beta rollout", "secondary": "", "tertiary": "", "meta": {}},
    ]


def test_ai_planner_normalizes_item_text_key_fallbacks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "bullet-list",
                "title": "Launch Details",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "items": [
                    {"type": "bullet", "text": "Alpha milestone"},
                    {"type": "bullet", "content": "Beta rollout"},
                    {"type": "bullet", "primary": "Primary wins", "text": "Fallback ignored"},
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\n\n- Alpha milestone\n- Beta rollout\n- Primary wins",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert [item.primary for item in plans[0].items] == [
        "Alpha milestone",
        "Beta rollout",
        "Primary wins",
    ]
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert [item["primary"] for item in persisted[0]["items"]] == [
        "Alpha milestone",
        "Beta rollout",
        "Primary wins",
    ]


def test_ai_planner_normalizes_item_detail_key_fallbacks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "bullet-list",
                "title": "Vocabulary",
                "visual_strategy": "stacked vocab cards with clear accent hierarchy",
                "layout_pattern": "single column card list with accent markers",
                "items": [
                    {
                        "type": "vocab",
                        "text": "变量",
                        "translation": "variable",
                        "pinyin": "bian liang",
                    },
                    {
                        "type": "bullet",
                        "primary": "Primary wins",
                        "secondary": "Canonical detail wins",
                        "description": "Fallback detail ignored",
                        "annotation": "preserve note",
                    },
                    {
                        "type": "text",
                        "description": "Description becomes primary when no stronger main text exists",
                    },
                    {
                        "type": "bullet",
                        "label": "Label is primary",
                        "description": "Description becomes secondary when label supplies primary",
                    },
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\n\n- 变量 variable\n- Primary wins\n- Description becomes primary when no stronger main text exists\n- Label is primary",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    items = plans[0].items
    assert (items[0].primary, items[0].secondary, items[0].tertiary) == ("变量", "variable", "bian liang")
    assert (items[1].primary, items[1].secondary, items[1].tertiary) == ("Primary wins", "Canonical detail wins", "preserve note")
    assert (items[2].primary, items[2].secondary) == (
        "Description becomes primary when no stronger main text exists",
        "",
    )
    assert (items[3].primary, items[3].secondary) == (
        "Label is primary",
        "Description becomes secondary when label supplies primary",
    )
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert persisted[0]["items"][0]["secondary"] == "variable"
    assert persisted[0]["items"][0]["tertiary"] == "bian liang"
    assert persisted[0]["items"][1]["secondary"] == "Canonical detail wins"
    assert persisted[0]["items"][1]["tertiary"] == "preserve note"


def test_ai_planner_normalizes_slide_title_key_fallbacks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "cover",
                "heading": "Heading Title",
                "visual_strategy": "hero title with diagonal accent rail",
                "layout_pattern": "large title left with proof card right",
                "items": [{"type": "text", "primary": "Heading details"}],
            },
            {
                "index": 2,
                "layout": "bullet-list",
                "title": "Canonical Title",
                "headline": "Fallback Headline Ignored",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "items": [{"type": "text", "primary": "Canonical details"}],
            },
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\nHeading details.\n\nCanonical details.",
            ContentConfig(max_slides=5),
            project_path=project,
            api_key="sk-test",
        )

    assert [plan.title for plan in plans] == ["Heading Title", "Canonical Title"]
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert [slide["title"] for slide in persisted] == ["Heading Title", "Canonical Title"]
    brief = (project / "qa" / "ai-planner" / "executor-brief.md").read_text(encoding="utf-8")
    assert "## Slide 1: Heading Title" in brief
    assert "Fallback Headline Ignored" not in brief


def test_ai_planner_normalizes_design_contract_key_fallbacks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "cover",
                "title": "Alias Design",
                "visual_intent": "hero title with diagonal accent rail",
                "layout_description": "large title left with proof card right",
                "items": [{"type": "text", "primary": "Alias details"}],
            },
            {
                "index": 2,
                "layout": "bullet-list",
                "title": "Canonical Design",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "visual_intent": "ignored visual fallback",
                "layout_pattern": "single column card list with accent markers",
                "arrangement": "ignored arrangement fallback",
                "items": [{"type": "text", "primary": "Canonical details"}],
            },
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\nAlias details.\n\nCanonical details.",
            ContentConfig(max_slides=5),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].visual_strategy == "hero title with diagonal accent rail"
    assert plans[0].layout_pattern == "large title left with proof card right"
    assert plans[1].visual_strategy == "stacked bullets with compact visual grouping"
    assert plans[1].layout_pattern == "single column card list with accent markers"
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert persisted[0]["visual_strategy"] == "hero title with diagonal accent rail"
    assert persisted[0]["layout_pattern"] == "large title left with proof card right"
    brief = (project / "qa" / "ai-planner" / "executor-brief.md").read_text(encoding="utf-8")
    assert "Visual strategy: hero title with diagonal accent rail" in brief
    assert "Layout pattern: large title left with proof card right" in brief
    assert "ignored visual fallback" not in brief
    assert "ignored arrangement fallback" not in brief


def test_ai_planner_normalizes_layout_key_fallbacks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "slide_layout": "two-column",
                "title": "Alias Layout",
                "visual_strategy": "hero title with diagonal accent rail",
                "layout_pattern": "large title left with proof card right",
                "items": [{"type": "text", "primary": "Alias layout details"}],
            },
            {
                "index": 2,
                "layout": "bullet-list",
                "layout_type": "ignored-layout-type",
                "title": "Canonical Layout",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "items": [{"type": "text", "primary": "Canonical layout details"}],
            },
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\nAlias layout details.\n\nCanonical layout details.",
            ContentConfig(max_slides=5),
            project_path=project,
            api_key="sk-test",
        )

    assert [plan.layout for plan in plans] == ["two-column", "bullet-list"]
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert [slide["layout"] for slide in persisted] == ["two-column", "bullet-list"]
    brief = (project / "qa" / "ai-planner" / "executor-brief.md").read_text(encoding="utf-8")
    assert "- Layout: two-column" in brief
    assert "ignored-layout-type" not in brief


def test_ai_planner_normalizes_auxiliary_key_fallbacks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "metric-highlight",
                "title": "Alias Auxiliaries",
                "visual_strategy": "large metric with compact source-backed explanation",
                "layout_pattern": "metric left with supporting bullet stack right",
                "chart": "bar chart",
                "visual_hint": "abstract product dashboard image",
                "speaker_notes": "Emphasize the source-backed metric.",
                "items": [{"type": "metric", "primary": "Revenue grew 42%"}],
            },
            {
                "index": 2,
                "layout": "bullet-list",
                "title": "Canonical Auxiliaries",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "chart_type": "line chart",
                "chart_hint": "ignored chart fallback",
                "image_hint": "canonical image hint",
                "image": "ignored image fallback",
                "notes": "Canonical notes win.",
                "speaker_note": "ignored speaker note fallback",
                "items": [{"type": "text", "primary": "Canonical auxiliary details"}],
            },
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source\nRevenue grew 42%.\n\nCanonical auxiliary details.",
            ContentConfig(max_slides=5),
            project_path=project,
            api_key="sk-test",
        )

    assert (plans[0].chart_type, plans[0].image_hint, plans[0].notes) == (
        "bar chart",
        "abstract product dashboard image",
        "Emphasize the source-backed metric.",
    )
    assert (plans[1].chart_type, plans[1].image_hint, plans[1].notes) == (
        "line chart",
        "canonical image hint",
        "Canonical notes win.",
    )
    persisted = json.loads((project / "qa" / "ai-planner" / "plan.json").read_text(encoding="utf-8"))
    assert persisted[0]["chart_type"] == "bar chart"
    assert persisted[0]["image_hint"] == "abstract product dashboard image"
    assert persisted[0]["notes"] == "Emphasize the source-backed metric."
    brief = (project / "qa" / "ai-planner" / "executor-brief.md").read_text(encoding="utf-8")
    assert "- Chart type: bar chart" in brief
    assert "- Image hint: abstract product dashboard image" in brief
    assert "- Notes: Emphasize the source-backed metric." in brief
    assert "ignored chart fallback" not in brief
    assert "ignored image fallback" not in brief
    assert "ignored speaker note fallback" not in brief


def test_ai_planner_retries_when_too_many_slides(tmp_path):
    layouts = ["bullet-list", "two-column", "metric-highlight", "quote"]
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "index": i + 1,
                "layout": layouts[i % len(layouts)],
                "title": f"Topic {chr(65 + i)}",
                "visual_strategy": f"section-specific visual hierarchy for topic {chr(65 + i)}",
                "layout_pattern": f"content card stack variant {chr(65 + i)}",
                "items": [],
            }
            for i in range(10)
        ]
    }
    valid_payload = {
        "slides": [
            {
                "index": i + 1,
                "layout": layouts[i % len(layouts)],
                "title": f"Topic {chr(65 + i)}",
                "visual_strategy": f"section-specific visual hierarchy for topic {chr(65 + i)}",
                "layout_pattern": f"content card stack variant {chr(65 + i)}",
                "items": [],
            }
            for i in range(3)
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_response(invalid_payload),
        _fake_response(valid_payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(max_slides=3),
            project_path=project,
            api_key="sk-test",
        )

    assert len(plans) == 3
    assert [plan.index for plan in plans] == [1, 2, 3]
    assert mock_client.chat.completions.create.call_count == 2
    second_prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "max_slides is 3" in second_prompt
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert "returned 10 slides" in first_attempt["error"]


def test_ai_planner_accepts_truncates_too_many_items(tmp_path):
    # Over-max item count is non-blocking: the planner auto-truncates and
    # feeds the overage back as a soft warning, rather than failing the deck.
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "index": 1,
                "layout": "bullet-list",
                "title": "Too Many Items",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "items": [
                    {"type": "bullet", "primary": text}
                    for text in ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [_fake_response(invalid_payload)]
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(max_items_per_slide=3),
            project_path=project,
            api_key="sk-test",
    )

    # Accepted on the first attempt, items truncated to the per-slide max.
    assert len(plans[0].items) == 3
    assert plans[0].items[0].primary == "Alpha"
    assert mock_client.chat.completions.create.call_count == 1
    attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert attempt["status"] == "passed"


def test_ai_planner_retries_malformed_item_entries(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "index": 1,
                "layout": "bullet-list",
                "title": "Malformed Items",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "items": [123, {"type": "bullet", "primary": "Bravo"}],
            }
        ]
    }
    valid_payload = {
        "slides": [
            {
                "index": 1,
                "layout": "bullet-list",
                "title": "Recovered Items",
                "visual_strategy": "stacked bullets with compact visual grouping",
                "layout_pattern": "single column card list with accent markers",
                "items": [
                    {"type": "bullet", "primary": "Alpha"},
                    {"type": "bullet", "primary": "Bravo"},
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_response(invalid_payload),
        _fake_response(valid_payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert [item.primary for item in plans[0].items] == ["Alpha", "Bravo"]
    assert mock_client.chat.completions.create.call_count == 2
    second_prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "item 1 must be an object" in second_prompt
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert "item 1 must be an object" in first_attempt["error"]


def test_ai_planner_retries_invalid_indexes_density_and_rhythm(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "index": 7,
                "layout": "cover",
                "title": "Bad Fields",
                "density": "crowded",
                "rhythm": "flashy",
                "visual_strategy": "generic",
                "layout_pattern": "specific arrangement",
                "items": [{"type": "text", "primary": "Valid item"}],
            }
        ]
    }
    valid_payload = {
        "slides": [
            {
                "index": 1,
                "layout": "cover",
                "title": "Recovered",
                "density": "sparse",
                "rhythm": "anchor",
                "visual_strategy": "hero title with clear accent geometry",
                "layout_pattern": "center title with lower supporting card",
                "items": [{"type": "text", "primary": "Valid item"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_response(invalid_payload),
        _fake_response(valid_payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].title == "Recovered"
    assert plans[0].density == "sparse"
    assert plans[0].rhythm == "anchor"
    assert mock_client.chat.completions.create.call_count == 2
    second_prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "invalid density" in second_prompt
    assert "invalid rhythm" in second_prompt
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    # Density/rhythm typos and out-of-order indexes are self-healed (non-blocking),
    # so the retry is driven by the genuinely-blocking non-actionable design contract.
    assert "invalid density" in first_attempt["error"]
    assert "invalid rhythm" in first_attempt["error"]
    assert "concrete visual_strategy" in first_attempt["error"]


def test_ai_planner_retries_with_feedback_after_invalid_json(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Recovered",
                "visual_strategy": "hero title with clear accent geometry",
                "layout_pattern": "center title with lower supporting card",
                "items": [{"type": "text", "primary": "Valid item"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_text_response("not json"),
        _fake_response(payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].title == "Recovered"
    assert mock_client.chat.completions.create.call_count == 2
    second_prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Planner Feedback From Previous Attempt" in second_prompt
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    second_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_02.json").read_text(encoding="utf-8"))
    assert first_attempt["status"] == "failed"
    assert second_attempt["status"] == "passed"


def test_ai_planner_accepts_markdown_fenced_json_with_protocol_warning(tmp_path):
    """REDESIGN_v5 production scenario: fenced valid JSON is a recoverable
    protocol deviation — plans on the first attempt, no retry, warning in trace."""
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "cover",
                "title": "Recovered",
                "visual_strategy": "hero title with clear accent geometry",
                "layout_pattern": "center title with lower supporting card",
                "items": [{"type": "text", "primary": "Valid item"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_text_response(
        "```json\n" + json.dumps(payload) + "\n```"
    )
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].title == "Recovered"
    assert mock_client.chat.completions.create.call_count == 1
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert first_attempt["status"] == "passed"
    events = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    planner_events = [event for event in events if event["stage"] == "planner"]
    assert planner_events[-1]["status"] == "passed"
    warnings = planner_events[-1]["metadata"]["protocol_warnings"]
    assert any("markdown fences" in warning for warning in warnings)


def test_ai_planner_accepts_prose_wrapped_json_with_protocol_warning(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "index": 1,
                "layout": "cover",
                "title": "Recovered",
                "visual_strategy": "hero title with clear accent geometry",
                "layout_pattern": "center title with lower supporting card",
                "items": [{"type": "text", "primary": "Valid item"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_text_response(
        "Here is the plan:\n" + json.dumps(payload) + "\nDone."
    )
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].title == "Recovered"
    assert mock_client.chat.completions.create.call_count == 1
    events = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    planner_events = [event for event in events if event["stage"] == "planner"]
    assert planner_events[-1]["status"] == "passed"
    warnings = planner_events[-1]["metadata"]["protocol_warnings"]
    assert any("prose outside JSON" in warning for warning in warnings)


def test_ai_planner_retries_generic_design_contract(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Too Generic",
                "visual_strategy": "standard",
                "layout_pattern": "specific arrangement",
                "items": [{"type": "text", "primary": "Point"}],
            }
        ]
    }
    valid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Recovered",
                "visual_strategy": "hero statement with diagonal accent rail",
                "layout_pattern": "large title left with compact proof card right",
                "items": [{"type": "text", "primary": "Point"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_response(invalid_payload),
        _fake_response(valid_payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].visual_strategy == "hero statement with diagonal accent rail"
    assert mock_client.chat.completions.create.call_count == 2
    second_prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "executor-ready" in second_prompt
    assert "visual_strategy" in second_prompt
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert "concrete visual_strategy" in first_attempt["error"]


def test_ai_planner_retries_abstract_design_contract_without_layout_terms(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Abstract Design",
                "visual_strategy": "important message with confident tone",
                "layout_pattern": "strong memorable presentation",
                "items": [{"type": "text", "primary": "Point"}],
            }
        ]
    }
    valid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Concrete Design",
                "visual_strategy": "hero message with diagonal accent rail",
                "layout_pattern": "large title left with compact proof card right",
                "items": [{"type": "text", "primary": "Point"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_response(invalid_payload),
        _fake_response(valid_payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].visual_strategy == "hero message with diagonal accent rail"
    second_prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "specific visual device" in second_prompt
    assert "actual placement or structure" in second_prompt
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert "specific visual device" in first_attempt["error"]
    assert "actual placement or structure" in first_attempt["error"]


def test_ai_planner_retries_missing_source_coverage(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "spec_lock.md").write_text("# Spec\n\nUse the locked theme.", encoding="utf-8")
    invalid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Product Launch",
                "visual_strategy": "hero launch statement with diagonal accent rail",
                "layout_pattern": "large title left with compact proof card right",
                "items": [{"type": "text", "primary": "Revenue grew 42%"}],
            }
        ]
    }
    valid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Product Launch",
                "visual_strategy": "hero launch statement with diagonal accent rail",
                "layout_pattern": "large title left with compact proof card right",
                "items": [
                    {"type": "metric", "primary": "Revenue grew 42%"},
                    {"type": "bullet", "primary": "Customers requested offline mode"},
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_response(invalid_payload),
        _fake_response(valid_payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    source = "# Product Launch\n\n- Revenue grew 42%\n- Customers requested offline mode\n"
    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            source,
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].items[1].primary == "Customers requested offline mode"
    assert mock_client.chat.completions.create.call_count == 2
    first_prompt = mock_client.chat.completions.create.call_args_list[0].kwargs["messages"][1]["content"]
    second_prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Required Source Coverage Anchors" in first_prompt
    assert "Short section headings still count as required source content" in first_prompt
    assert first_prompt.index("## Required Source Coverage Anchors") < first_prompt.index("## Project Context")
    assert "Customers requested offline mode" in first_prompt
    assert "source coverage missing required anchor" in second_prompt
    anchors = json.loads((project / "qa" / "ai-planner" / "coverage-anchors.json").read_text(encoding="utf-8"))
    assert "Customers requested offline mode" in anchors["anchors"]
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert "source coverage missing required anchor" in first_attempt["error"]


def test_ai_planner_retries_source_coverage_hidden_in_notes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Product Launch",
                "visual_strategy": "hero launch statement with diagonal accent rail",
                "layout_pattern": "large title left with compact proof card right",
                "notes": "Mention that Customers requested offline mode.",
                "items": [{"type": "metric", "primary": "Revenue grew 42%"}],
            }
        ]
    }
    valid_payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Product Launch",
                "visual_strategy": "hero launch statement with diagonal accent rail",
                "layout_pattern": "large title left with compact proof card right",
                "items": [
                    {"type": "metric", "primary": "Revenue grew 42%"},
                    {"type": "bullet", "primary": "Customers requested offline mode"},
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _fake_response(invalid_payload),
        _fake_response(valid_payload),
    ]
    mock_openai = MagicMock(return_value=mock_client)

    source = "# Product Launch\n\n- Revenue grew 42%\n- Customers requested offline mode\n"
    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            source,
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].items[1].primary == "Customers requested offline mode"
    assert mock_client.chat.completions.create.call_count == 2
    first_prompt = mock_client.chat.completions.create.call_args_list[0].kwargs["messages"][1]["content"]
    assert "Do not hide source coverage in notes" in first_prompt
    first_attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert "source coverage missing required anchor" in first_attempt["error"]


def test_ai_planner_flags_hallucinated_numeric_value_non_blocking(tmp_path):
    # Fabricated numbers are non-blocking: flagged for review but the plan is
    # accepted (the model retried without dropping them, so blocking would only
    # fail the whole deck). The fabricated value is recorded in the attempt log.
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "layout": "metric-highlight",
                "title": "Retention",
                "visual_strategy": "large metric with compact source-backed explanation",
                "layout_pattern": "metric left with supporting bullet stack right",
                "items": [
                    {"type": "metric", "primary": "Retention improved 42%"},
                    {"type": "metric", "primary": "Forecast conversion reached 64%"},
                    {"type": "bullet", "primary": "Customers requested offline mode"},
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [_fake_response(invalid_payload)]
    mock_openai = MagicMock(return_value=mock_client)

    source = "# Retention\n\n- Retention improved 42%\n- Customers requested offline mode\n"
    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            source,
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert len(plans) == 1
    # Accepted on first attempt (non-blocking).
    assert mock_client.chat.completions.create.call_count == 1
    first_prompt = mock_client.chat.completions.create.call_args_list[0].kwargs["messages"][1]["content"]
    assert "Allowed Source Numeric Values" in first_prompt
    assert "42%" in first_prompt
    attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert attempt["status"] == "passed"
    # The fabricated number is still recorded for review.
    assert "64%" in attempt["warnings"]


def test_ai_planner_flags_hallucinated_numeric_value_in_title(tmp_path):
    # A fabricated number in the title is non-blocking: the plan is accepted
    # and the number is recorded for review.
    project = tmp_path / "project"
    project.mkdir()
    invalid_payload = {
        "slides": [
            {
                "layout": "metric-highlight",
                "title": "64% Conversion Growth",
                "visual_strategy": "large metric with compact source-backed explanation",
                "layout_pattern": "metric left with supporting bullet stack right",
                "items": [
                    {"type": "metric", "primary": "Retention improved 42%"},
                    {"type": "bullet", "primary": "Customers requested offline mode"},
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [_fake_response(invalid_payload)]
    mock_openai = MagicMock(return_value=mock_client)

    source = "# Retention\n\n- Retention improved 42%\n- Customers requested offline mode\n"
    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            source,
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    # Accepted on first attempt; the fabricated "64%" is flagged for review.
    assert plans[0].title == "64% Conversion Growth"
    assert mock_client.chat.completions.create.call_count == 1
    attempt = json.loads((project / "qa" / "ai-planner" / "attempt_01.json").read_text(encoding="utf-8"))
    assert attempt["status"] == "passed"
    assert "64%" in attempt["warnings"]


def test_ai_planner_allows_design_numbers_in_notes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Retention",
                "visual_strategy": "hero title with accent rail and proof card",
                "layout_pattern": "title left with proof card right",
                "notes": "Use color #3B82F6 and a 32px footer from the design guide.",
                "items": [
                    {"type": "metric", "primary": "Retention improved 42%"},
                    {"type": "bullet", "primary": "Customers requested offline mode"},
                ],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    source = "# Retention\n\n- Retention improved 42%\n- Customers requested offline mode\n"
    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            source,
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].notes.startswith("Use color")
    assert mock_client.chat.completions.create.call_count == 1
    trace = [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert trace[-1]["status"] == "passed"


def test_ai_planner_accepts_hyphenated_design_terms(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "layout": "two-column",
                "title": "Python 入门速览",
                "visual_strategy": "left-accent-rail + right-title-card-grid",
                "layout_pattern": "left title column + right card grid",
                "items": [{"type": "text", "primary": "变量与类型"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Python 入门速览\n\n- 变量与类型",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].visual_strategy == "left-accent-rail + right-title-card-grid"


def test_ai_planner_accepts_chinese_design_terms(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "slides": [
            {
                "layout": "two-column",
                "title": "Python 入门速览",
                "visual_strategy": "左侧标题 + 右侧要点卡片",
                "layout_pattern": "左侧标题 + 右侧要点卡片",
                "items": [{"type": "text", "primary": "变量与类型"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Python 入门速览\n\n- 变量与类型",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].layout_pattern == "左侧标题 + 右侧要点卡片"


def test_ai_planner_failure_clears_stale_success_artifacts(tmp_path):
    project = tmp_path / "project"
    out_dir = project / "qa" / "ai-planner"
    out_dir.mkdir(parents=True)
    (out_dir / "plan.json").write_text("[{\"title\":\"old\"}]\n", encoding="utf-8")
    (out_dir / "executor-brief.md").write_text("# old brief\n", encoding="utf-8")
    (out_dir / "raw-response.txt").write_text("old raw\n", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_text_response("not json")
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        try:
            plan_slides_with_ai(
                "# Source",
                ContentConfig(),
                project_path=project,
                api_key="sk-test",
                retries=1,
            )
        except ValueError as exc:
            assert "AI planner failed after 2 attempts" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    assert not (out_dir / "plan.json").exists()
    assert not (out_dir / "executor-brief.md").exists()
    assert not (out_dir / "raw-response.txt").exists()
    failure = json.loads((out_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed"
    assert failure["attempts"] == 2
    assert failure["error"] == "AI planner did not return JSON"
    assert json.loads((out_dir / "attempt_01.json").read_text(encoding="utf-8"))["status"] == "failed"
    assert json.loads((out_dir / "attempt_02.json").read_text(encoding="utf-8"))["status"] == "failed"


def test_ai_planner_provider_error_writes_trace_and_failure(tmp_path):
    from slide_skill.ai_trace import read_ai_trace

    project = tmp_path / "project"
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("401 unauthorized")
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        try:
            plan_slides_with_ai(
                "# Source\n\n- Required point",
                ContentConfig(),
                project_path=project,
                api_key="sk-test",
                retries=1,
                model="planner-provider-test",
            )
        except RuntimeError as exc:
            assert "AI planner provider call failed after 2 attempts" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")

    out_dir = project / "qa" / "ai-planner"
    failure = json.loads((out_dir / "failure.json").read_text(encoding="utf-8"))
    trace = read_ai_trace(project)

    assert failure["attempts"] == 2
    assert "provider call failed: RuntimeError: 401 unauthorized" in failure["error"]
    assert len(trace) == 2
    assert trace[-1]["stage"] == "planner"
    assert trace[-1]["status"] == "failed"
    assert trace[-1]["model"] == "planner-provider-test"
    assert trace[-1]["metadata"]["provider_error"] is True
    assert "401 unauthorized" in trace[-1]["metadata"]["error"]
    assert trace[-1]["request_path"].endswith(".request.json")
    assert trace[-1]["prompt_path"].endswith(".prompt.txt")


def test_ai_planner_success_clears_stale_failure_artifact(tmp_path):
    project = tmp_path / "project"
    out_dir = project / "qa" / "ai-planner"
    out_dir.mkdir(parents=True)
    (out_dir / "failure.json").write_text(json.dumps({
        "status": "failed",
        "attempts": 2,
        "error": "old failure",
    }), encoding="utf-8")
    payload = {
        "slides": [
            {
                "layout": "cover",
                "title": "Recovered",
                "visual_strategy": "hero title with clear accent geometry",
                "layout_pattern": "center title with lower supporting card",
                "items": [{"type": "text", "primary": "Valid item"}],
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_response(payload)
    mock_openai = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            api_key="sk-test",
        )

    assert plans[0].title == "Recovered"
    assert not (out_dir / "failure.json").exists()
    assert (out_dir / "plan.json").exists()
    assert (out_dir / "executor-brief.md").exists()


def test_plan_command_uses_ai_planner(monkeypatch, tmp_path):
    from slide_skill.cli import main

    source = tmp_path / "source.md"
    source.write_text("# Topic\n- Point", encoding="utf-8")
    seen = {}

    def fake_ai_plan(source_text, config, project_path=None, **kwargs):
        from slide_skill.content_planner import ContentItem, SlidePlan
        seen.update(kwargs)
        return [SlidePlan(index=1, layout="cover", title="AI Planned", items=[ContentItem(type="text", primary="Point")])]

    monkeypatch.setattr("slide_skill.ai_planner.plan_slides_with_ai", fake_ai_plan)

    result = main([
        "plan",
        str(source),
        "--planner",
        "ai",
        "--model",
        "global-model",
        "--planner-model",
        "planner-model",
        "--planner-retries",
        "4",
        "--ai-base-url",
        "http://127.0.0.1:11434/v1",
    ])

    assert result == 0
    assert seen["model"] == "planner-model"
    assert seen["retries"] == 4


def test_planner_auto_routes_by_generation_mode():
    from argparse import Namespace
    from slide_skill.cli import _resolve_planner_mode

    assert _resolve_planner_mode(Namespace(planner="auto", mode="ai")) == "ai"
    assert _resolve_planner_mode(Namespace(planner="auto", mode="template-smoke")) == "deterministic"
    assert _resolve_planner_mode(Namespace(planner="deterministic", mode="ai")) == "deterministic"
