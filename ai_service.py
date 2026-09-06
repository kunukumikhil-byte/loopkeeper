"""Task review service for LoopKeeper.

The app always performs a local, explainable review so task submission works without
an external API. If a Gemini API key and google-genai are installed, Gemini is used
as an optional second-level reviewer. A failed optional integration never breaks a
worker's submission.
"""
import json
import os
import re
from typing import Any


STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "with", "on", "in",
    "task", "work", "please", "by", "before", "after", "from", "into",
}


def _clean_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    return text


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9_-]*", (value or "").lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


def _local_review(*, title: str, submission: str, filename: str | None) -> dict[str, Any]:
    """Explainable fallback reviewer that needs no API or extra package."""
    text = (submission or "").strip()
    task_tokens = _tokens(title)
    evidence_tokens = _tokens(text)
    overlap = task_tokens & evidence_tokens
    has_file = bool(filename)

    if not text and not has_file:
        return {
            "available": True,
            "engine": "LoopKeeper Local Review",
            "decision": "REJECT",
            "reason": "No written evidence or work file was submitted.",
            "corrected_submission": "",
            "confidence": 0.98,
        }

    # A file can be useful evidence, but a filename alone cannot prove completion.
    if not text and has_file:
        return {
            "available": True,
            "engine": "LoopKeeper Local Review",
            "decision": "NEEDS_MANUAL_REVIEW",
            "reason": "A file was submitted, but no explanation was provided. The reviewer should inspect the file.",
            "corrected_submission": "",
            "confidence": 0.72,
        }

    if len(text) < 8:
        return {
            "available": True,
            "engine": "LoopKeeper Local Review",
            "decision": "REJECT",
            "reason": "The written evidence is too short to verify what was completed.",
            "corrected_submission": text,
            "confidence": 0.93,
        }

    completion_words = {
        "completed", "complete", "finished", "implemented", "created", "built",
        "designed", "fixed", "tested", "deployed", "submitted", "delivered",
        "updated", "prepared", "done",
    }
    negative_phrases = (
        "not completed", "not finished", "not done", "still working",
        "not started", "will complete", "going to complete", "plan to",
    )
    low = text.lower()
    if any(phrase in low for phrase in negative_phrases):
        return {
            "available": True,
            "engine": "LoopKeeper Local Review",
            "decision": "REJECT",
            "reason": "The submission itself indicates that the assigned work is not yet complete.",
            "corrected_submission": text,
            "confidence": 0.90,
        }

    overlap_ratio = len(overlap) / max(1, len(task_tokens))
    has_completion = bool(completion_words & evidence_tokens)

    if len(task_tokens) <= 2 and (has_completion or has_file) and len(text) >= 20:
        decision = "PASS"
        reason = "The submission gives concrete completion evidence for this task."
        confidence = 0.80
    elif overlap_ratio >= 0.60 and (has_completion or len(text) >= 40):
        decision = "PASS"
        reason = "The submission covers most of the task-specific terms and provides completion evidence."
        confidence = min(0.94, 0.68 + overlap_ratio * 0.25 + (0.05 if has_file else 0))
    elif overlap_ratio >= 0.25 or has_file:
        decision = "NEEDS_MANUAL_REVIEW"
        reason = "The submission is related to the task, but the available evidence is not strong enough for automatic approval."
        confidence = 0.55 + min(overlap_ratio, 0.3)
    else:
        decision = "REJECT"
        reason = "The written evidence does not clearly demonstrate the assigned task was completed."
        confidence = 0.82

    return {
        "available": True,
        "engine": "LoopKeeper Local Review",
        "decision": decision,
        "reason": reason,
        "corrected_submission": text,
        "confidence": round(float(confidence), 2),
    }


def _gemini_review(*, title: str, deadline: str, submission: str, filename: str | None) -> dict[str, Any] | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
    except Exception:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip() or "gemini-2.5-flash-lite"
    prompt = f"""
You are LoopKeeper's strict task-verification assistant.
Judge whether a worker's submitted evidence supports the assigned task.
Do not invent evidence. A filename alone is not proof.

Assigned task: {title}
Deadline text: {deadline or 'No deadline'}
Attached file name: {filename or 'None'}
Worker submission:
{submission or '[No textual submission provided]'}

Return ONLY JSON:
{{
  "decision": "PASS" | "REJECT" | "NEEDS_MANUAL_REVIEW",
  "reason": "short concrete reason",
  "corrected_submission": "optional clearer wording preserving meaning",
  "confidence": 0.0
}}

Never mark a task Completed; the task giver makes the final decision.
""".strip()
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string"},
                        "reason": {"type": "string"},
                        "corrected_submission": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["decision", "reason", "corrected_submission", "confidence"],
                },
            ),
        )
        data = json.loads(_clean_json(getattr(response, "text", "") or ""))
    except Exception:
        return None

    decision = str(data.get("decision", "NEEDS_MANUAL_REVIEW")).upper()
    if decision not in {"PASS", "REJECT", "NEEDS_MANUAL_REVIEW"}:
        decision = "NEEDS_MANUAL_REVIEW"
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except Exception:
        confidence = 0.0
    return {
        "available": True,
        "engine": "Gemini",
        "decision": decision,
        "reason": str(data.get("reason") or "No reason provided.")[:2000],
        "corrected_submission": str(data.get("corrected_submission") or submission or "")[:10000],
        "confidence": confidence,
    }


def verify_task_with_gemini(*, title: str, deadline: str, submission: str, filename: str | None = None) -> dict[str, Any]:
    """Review work with optional Gemini and a reliable local fallback."""
    gemini = _gemini_review(
        title=title, deadline=deadline, submission=submission, filename=filename
    )
    if gemini:
        return gemini
    return _local_review(title=title, submission=submission, filename=filename)
