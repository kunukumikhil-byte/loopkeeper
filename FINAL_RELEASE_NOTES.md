# LoopKeeper Final Release

This package was syntax-checked with `python -m compileall` and imported with `from main import app`.

## AI review behavior
- A Gemini API key is optional for the app to run.
- If Gemini is configured, task submissions are reviewed and returned as PASS, REJECT, or NEEDS_MANUAL_REVIEW.
- If the API is unavailable, invalid, rate-limited, or the model request fails, the submission is preserved and safely routed to manual review instead of crashing the task submission endpoint.
- Final completion remains under the task giver's approval workflow.

## Before deployment
Copy `.env.example` to `.env` and configure Google/Gemini/email settings that you actually intend to use. Do not commit secrets.
