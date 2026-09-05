# Pre-GitHub checklist

- [ ] `.env` is not present
- [ ] `loopkeeper.db` is not present
- [ ] `uploads/` is not committed
- [ ] Python 3.11 is used for deployment
- [ ] `requirements.txt` is installed
- [ ] `python -c "from main import app; print(app.version)"` passes
- [ ] `/health` returns status `ok`
- [ ] Google OAuth Web Client ID is configured only in `.env`
