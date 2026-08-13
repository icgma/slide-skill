"""Preflight checks for OpenAI-compatible AI provider access."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"
_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


@dataclass
class AiDoctorResult:
    role: str
    model: str
    base_url: str
    status: str
    error: str = ""
    next_action: str = ""


def check_ai_provider(
    *,
    planner_kwargs: dict,
    executor_kwargs: dict,
    vision_kwargs: dict,
    check_vision: bool = False,
) -> list[AiDoctorResult]:
    """Run minimal provider calls for each configured AI role."""
    results = [
        _check_text_role("planner", planner_kwargs),
        _check_text_role("executor", executor_kwargs),
    ]
    if check_vision:
        results.append(_check_vision_role(vision_kwargs))
    else:
        kwargs = _resolved_kwargs("vision", vision_kwargs)
        results.append(AiDoctorResult(
            role="vision",
            model=kwargs["model"],
            base_url=kwargs["base_url"],
            status="skipped",
            error="pass --check-vision to verify image input",
            next_action="Rerun with --check-vision before relying on visual-critic, ai-smoke --visual-critic, or ai-release-check.",
        ))
    return results


def format_ai_doctor_results(results: list[AiDoctorResult]) -> str:
    lines = ["AI provider doctor"]
    for result in results:
        line = f"- {result.role}: {result.status} | model={result.model} | base_url={result.base_url}"
        if result.error:
            line += f" | {result.error}"
        if result.next_action:
            line += f" | next={result.next_action}"
        lines.append(line)
    return "\n".join(lines)


def _check_text_role(role: str, kwargs: dict) -> AiDoctorResult:
    resolved = _resolved_kwargs(role, kwargs)
    try:
        client = _client(resolved)
        client.chat.completions.create(
            model=resolved["model"],
            messages=[
                {"role": "system", "content": "Return only the word ok."},
                {"role": "user", "content": f"Provider preflight for {role}."},
            ],
            max_tokens=8,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001 - provider SDKs expose heterogeneous errors.
        return AiDoctorResult(
            role,
            resolved["model"],
            resolved["base_url"],
            "failed",
            _provider_error_message(exc),
            _doctor_next_action(role, resolved),
        )
    return AiDoctorResult(role, resolved["model"], resolved["base_url"], "passed")


def _check_vision_role(kwargs: dict) -> AiDoctorResult:
    resolved = _resolved_kwargs("vision", kwargs)
    try:
        client = _client(resolved)
        client.chat.completions.create(
            model=resolved["model"],
            messages=[
                {"role": "system", "content": "Return only the word ok."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Provider preflight for image input."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{_ONE_PIXEL_PNG}"},
                        },
                    ],
                },
            ],
            max_tokens=8,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001 - provider SDKs expose heterogeneous errors.
        return AiDoctorResult(
            "vision",
            resolved["model"],
            resolved["base_url"],
            "failed",
            _provider_error_message(exc),
            _doctor_next_action("vision", resolved),
        )
    return AiDoctorResult("vision", resolved["model"], resolved["base_url"], "passed")


def _client(resolved: dict):
    from openai import OpenAI

    return OpenAI(api_key=resolved["api_key"], base_url=resolved["base_url"])


def _resolved_kwargs(role: str, kwargs: dict) -> dict:
    model_env = {
        "planner": "OPENAI_PLANNER_MODEL",
        "executor": "OPENAI_EXECUTOR_MODEL",
        "vision": "OPENAI_VISION_MODEL",
    }[role]
    return {
        "model": kwargs.get("model") or os.environ.get(model_env) or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        "api_key": kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY", ""),
        "base_url": kwargs.get("base_url") or os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL),
    }


def _doctor_next_action(role: str, resolved: dict) -> str:
    model = resolved.get("model") or DEFAULT_MODEL
    base_url = resolved.get("base_url") or DEFAULT_BASE_URL
    if role == "planner":
        return (
            "Verify OPENAI_PLANNER_MODEL or --planner-model, API key, and base URL "
            f"before running quickstart-ai or ai-smoke. Current model={model}, base_url={base_url}."
        )
    if role == "executor":
        return (
            "Verify OPENAI_EXECUTOR_MODEL or --executor-model, API key, and base URL "
            f"before SVG generation or repair-feedback. Current model={model}, base_url={base_url}."
        )
    if role == "vision":
        return (
            "Use a vision-capable OPENAI_VISION_MODEL or --vision-model with image input support "
            f"before visual-critic or release gates. Current model={model}, base_url={base_url}."
        )
    return f"Verify model access and provider configuration for role={role}."


def _provider_error_message(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    clean = " ".join(text.split())
    if len(clean) > 220:
        clean = clean[:220].rstrip() + "..."
    return f"error={exc.__class__.__name__}: {clean}"
