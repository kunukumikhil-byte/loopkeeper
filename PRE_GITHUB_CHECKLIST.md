# Pre-GitHub checklist

1. Create a real Google OAuth 2.0 **Web application** client.
2. Add these Authorized JavaScript origins:
   - http://127.0.0.1:8000
   - http://localhost:8000
   - https://YOUR_USERNAME.pythonanywhere.com (after the PythonAnywhere username is known)
3. Put the real client ID in `.env`. Do not commit `.env`.
4. Restart LoopKeeper completely.
5. Open `/api/auth/google/config` and confirm `enabled` is `true`.
6. Test Google login in a private/incognito window.
7. Run `python -m compileall .` and start the app before committing.
8. Confirm `git status` does not show `.env`, `loopkeeper.db`, `uploads/`, or `venv/`.
