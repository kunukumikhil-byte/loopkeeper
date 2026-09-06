# LoopKeeper — PythonAnywhere Deployment

This version is prepared for PythonAnywhere ASGI deployment. Paths are resolved from `main.py`, so the app does not depend on the web worker's current working directory.

## 1. Clone
```bash
cd ~
rm -rf ~/loopkeeper
rm -rf ~/loopkeeper_venv
git clone https://github.com/kunukumikhil-byte/loopkeeper.git ~/loopkeeper
```

## 2. Python 3.11 environment
```bash
python3.11 -m venv ~/loopkeeper_venv
source ~/loopkeeper_venv/bin/activate
cd ~/loopkeeper
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "from main import app; print('LOOPKEEPER BACKEND OK')"
```

## 3. Environment variables
Create `~/loopkeeper/.env` and set your real Google OAuth values and a long random session secret if/when those features are enabled. Never commit `.env`.

## 4. ASGI website
Install the PythonAnywhere CLI in the virtual environment if needed:
```bash
python -m pip install --upgrade pythonanywhere
```

Create the ASGI website:
```bash
pa website create --domain mikhilkunuku1.pythonanywhere.com --command '/home/mikhilkunuku1/loopkeeper_venv/bin/uvicorn --app-dir /home/mikhilkunuku1/loopkeeper --uds ${DOMAIN_SOCKET} main:app'
```

Reload:
```bash
pa website reload --domain mikhilkunuku1.pythonanywhere.com
```

## 5. If the website already exists
Use the PythonAnywhere web dashboard to reload/reconfigure it, or delete and recreate it with the command above.

## 6. Notes
- No AI/ML model is required by this project.
- Do not run `train_model.py`; it is not part of this version.
- SQLite and uploads are stored relative to the project directory, so the app works even when PythonAnywhere starts Uvicorn from a different working directory.
- WebRTC media is browser-to-browser; the ASGI app provides signaling.
