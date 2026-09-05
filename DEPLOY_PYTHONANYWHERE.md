# LoopKeeper — Fresh PythonAnywhere Deployment

This package is prepared for **FastAPI + WebSockets on PythonAnywhere ASGI**.

## 1. Push to GitHub

From the extracted project folder on Windows:

```powershell
git init
git branch -M main
git remote remove origin 2>$null
git remote add origin https://github.com/kunukumikhil-byte/loopkeeper.git
git add .
git commit -m "LoopKeeper PythonAnywhere ready release"
git push origin main --force
```

Never commit `.env`, `loopkeeper.db`, `uploads/`, or a virtual environment.

## 2. Fresh PythonAnywhere install

Open a new Bash console:

```bash
cd ~
rm -rf ~/loopkeeper
rm -rf ~/loopkeeper_venv

git clone https://github.com/kunukumikhil-byte/loopkeeper.git ~/loopkeeper

python3.11 -m venv ~/loopkeeper_venv
source ~/loopkeeper_venv/bin/activate

cd ~/loopkeeper
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -c "from main import app; print('LOOPKEEPER BACKEND OK', app.version)"
```

## 3. Configure production environment

```bash
nano ~/loopkeeper/.env
```

Use:

```env
ENVIRONMENT=production
SESSION_SECRET=PUT_A_LONG_RANDOM_VALUE_HERE
GOOGLE_CLIENT_ID=YOUR_GOOGLE_WEB_CLIENT_ID
```

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not paste secrets into GitHub or chat.

## 4. Google OAuth

For the production domain:

**Authorized JavaScript origin**

```text
https://mikhilkunuku1.pythonanywhere.com
```

**Authorized redirect URI**

```text
https://mikhilkunuku1.pythonanywhere.com/auth/google/callback
```

The Google client must be an OAuth **Web application** client.

## 5. Create the ASGI website

If an old website exists and you want a completely fresh configuration:

```bash
source ~/loopkeeper_venv/bin/activate
pa website delete --domain mikhilkunuku1.pythonanywhere.com
```

Then create it:

```bash
pa website create --domain mikhilkunuku1.pythonanywhere.com --command '/home/mikhilkunuku1/loopkeeper_venv/bin/uvicorn --app-dir /home/mikhilkunuku1/loopkeeper --uds ${DOMAIN_SOCKET} main:app'
```

Reload:

```bash
pa website reload --domain mikhilkunuku1.pythonanywhere.com
```

## 6. Test

Open:

```text
https://mikhilkunuku1.pythonanywhere.com/health
https://mikhilkunuku1.pythonanywhere.com/login
https://mikhilkunuku1.pythonanywhere.com/meetings
```

For WebRTC, test with two different browsers/devices and two different accounts.

## 7. Future updates

After pushing a new version to GitHub:

```bash
cd ~/loopkeeper
git pull origin main
source ~/loopkeeper_venv/bin/activate
python -m pip install -r requirements.txt
pa website reload --domain mikhilkunuku1.pythonanywhere.com
```

### WebRTC note

The meeting media is peer-to-peer WebRTC and the FastAPI WebSocket is only used for signaling. This is appropriate for a hackathon/demo and small rooms. Some networks may require a TURN server for reliable media connectivity.
