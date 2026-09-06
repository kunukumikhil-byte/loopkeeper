# Optional Integrations

LoopKeeper runs without Google or Gemini packages.

## Google Sign-In
Only if you configure Google Sign-In, install:

    python -m pip install google-auth

Then configure `GOOGLE_CLIENT_ID` in `.env`.

## Gemini
Only if you want external Gemini review in addition to the built-in local reviewer, install:

    python -m pip install google-genai

Then configure `GEMINI_API_KEY` and optionally `GEMINI_MODEL` in `.env`.

If these integrations are absent, the application still runs. Task review uses LoopKeeper's built-in local review engine.
