"""Single provider response adapter with a completion-status gate.

Every AI role (planner, executor, visual critic) consumes provider output
through :func:`parse_provider_response` so that truncated or incomplete
responses are stopped BEFORE JSON repair, SVG extraction, QA, or publish.

REDESIGN_v5 verified provider behavior this module encodes:

- ``finish_reason="length"`` responses may carry empty ``message.content``
  because reasoning consumed the completion budget; such responses must
  never reach any parser.
- Reasoning text is never merged into content and never used as an empty
  content fallback; only its LENGTH is recorded for trace telemetry.
- ``length`` retries raise the role budget instead of feeding generic
  repair feedback prompts.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ai_trace import _response_finish_reason, _scalar_attr, _scalar_usage, _value

#: Hard ceiling for length-escalation retries (tokens).
MAX_TOKENS_CAP = 32768

#: Per-role completion budgets used when neither CLI flags nor environment
#: variables configure a budget. The executor budget is larger because
#: REDESIGN_v5 measured 7.7-7.9K-token SVG completions plus a reasoning
#: share on the shared 4096/8192 budgets that previously truncated output.
DEFAULT_ROLE_MAX_TOKENS = {
    "planner": 4096,
    "executor": 16384,
    "vision": 4096,
}


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized view of one OpenAI-compatible chat completion response."""

    content: str
    reasoning_chars: int
    finish_reason: str | None
    response_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int | None
    strict_missing_finish: bool = False

    @property
    def is_complete(self) -> bool:
        """True when the provider reported a normal completion.

        A missing ``finish_reason`` counts as complete only in lenient mode;
        strict mode (release gates) refuses to assume ``stop``.
        """
        if self.finish_reason == "stop":
            return True
        if not self.finish_reason:
            return not self.strict_missing_finish
        return False

    @property
    def is_truncated(self) -> bool:
        """True when the completion budget was exhausted mid-response."""
        return self.finish_reason == "length"

    @property
    def blocks_parsing(self) -> bool:
        """True when this response must not reach JSON/SVG parsers.

        Truncated responses always block. In strict mode, any response the
        provider did not positively mark complete blocks as well.
        """
        if self.is_truncated:
            return True
        return self.strict_missing_finish and not self.is_complete

    def trace_metadata(self) -> dict:
        """Provider signals for AI trace events (mirrors ``ai_response_metadata``)."""
        metadata: dict = {}
        if self.response_id:
            metadata["response_id"] = self.response_id
        if self.finish_reason:
            metadata["finish_reason"] = self.finish_reason
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"):
            value = getattr(self, key)
            if value is not None:
                metadata[key] = value
        metadata["reasoning_chars"] = self.reasoning_chars
        return metadata


class TruncatedResponseError(ValueError):
    """Raised when a truncated/incomplete response must not reach parsers."""

    def __init__(self, message: str, response: ProviderResponse):
        super().__init__(message)
        self.response = response


def parse_provider_response(response, *, strict_missing_finish: bool = False) -> ProviderResponse:
    """Normalize a chat completion into a :class:`ProviderResponse`.

    Reads ``response.choices[0].message`` defensively (dict or attribute
    access) and reuses the ai_trace extraction helpers so finish_reason and
    usage semantics stay identical to trace metadata.
    """
    choices = _value(response, "choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Model returned no choices (possible content filter)")
    message = _value(choices[0], "message")
    raw_content = _value(message, "content")
    content = raw_content if isinstance(raw_content, str) else ""
    usage = _scalar_usage(response)
    return ProviderResponse(
        content=content,
        reasoning_chars=_reasoning_chars(message),
        finish_reason=str(_response_finish_reason(response) or "") or None,
        response_id=str(_scalar_attr(response, "id") or "") or None,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        reasoning_tokens=_reasoning_tokens(response),
        total_tokens=usage.get("total_tokens"),
        strict_missing_finish=strict_missing_finish,
    )


def escalate_budget(current: int, cap: int = MAX_TOKENS_CAP) -> int:
    """Return the next completion budget after a truncated attempt.

    Doubles the budget up to ``cap``. Callers must treat an unchanged
    return value (already at cap) as a terminal condition and fail with an
    actionable error instead of retrying forever.
    """
    return min(max(int(current), 1) * 2, cap)


def _reasoning_chars(message) -> int:
    """Length of reasoning text; raw reasoning is never persisted."""
    for attr in ("reasoning", "reasoning_content"):
        value = _value(message, attr)
        if isinstance(value, str) and value:
            return len(value)
    return 0


def _reasoning_tokens(response) -> int | None:
    usage = _value(response, "usage")
    if usage is None:
        return None
    direct = _value(usage, "reasoning_tokens")
    if isinstance(direct, int) and not isinstance(direct, bool):
        return direct
    details = _value(usage, "completion_tokens_details")
    if details is not None:
        nested = _value(details, "reasoning_tokens")
        if isinstance(nested, int) and not isinstance(nested, bool):
            return nested
    return None
