from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from database import Base, engine, migrate_sqlite
import models  # noqa: F401 - register tables
from routers.auth import router as auth_router
from routers.meetings import router as meetings_router
from routers.tasks import router as tasks_router

Base.metadata.create_all(bind=engine)
migrate_sqlite()

app = FastAPI(title="LoopKeeper", description="The Meeting Accountability Engine")
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOADS_DIR = BASE_DIR / "uploads"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(auth_router)
app.include_router(meetings_router)
app.include_router(tasks_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "LoopKeeper"}


def page(request: Request, template: str, **context):
    return templates.TemplateResponse(template, {"request": request, **context})


@app.get("/")
def home():
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login")
def login_page(request: Request):
    return page(request, "login.html", title="Login")


@app.get("/dashboard")
def dashboard(request: Request):
    return page(request, "dashboard.html", title="Dashboard")


@app.get("/meetings")
def meetings_page(request: Request):
    return page(request, "meetings.html", title="Meetings")


@app.get("/meeting-room")
def meeting_room(request: Request, meeting_id: int | None = None):
    return page(request, "meeting_room.html", title="Meeting Room", meeting_id=meeting_id)


@app.get("/my-tasks")
def my_tasks_page(request: Request):
    return page(request, "my_tasks.html", title="My Tasks")


@app.get("/assigned-tasks")
def assigned_tasks_page(request: Request):
    return page(request, "assigned_tasks.html", title="Assigned Tasks")


# ---------------------------------------------------------------------------
# Lightweight WebRTC signaling server
# ---------------------------------------------------------------------------
# The browser sends the actual audio/video directly between participants.
# This server only relays WebRTC offers, answers and ICE candidates.
class MeetingSignalManager:
    def __init__(self):
        self.rooms: dict[str, dict[str, dict]] = {}

    async def connect(self, room_id: str, websocket: WebSocket, client_id: str, name: str):
        await websocket.accept()
        room = self.rooms.setdefault(room_id, {})
        existing = [
            {"client_id": cid, "name": data["name"]}
            for cid, data in room.items()
        ]
        room[client_id] = {"websocket": websocket, "name": name}
        await websocket.send_json({"type": "peers", "peers": existing})
        for cid, data in list(room.items()):
            if cid != client_id:
                try:
                    await data["websocket"].send_json({
                        "type": "peer-joined",
                        "peer": {"client_id": client_id, "name": name}
                    })
                except Exception:
                    pass

    async def relay(self, room_id: str, sender_id: str, payload: dict):
        target = str(payload.get("to") or "")
        room = self.rooms.get(room_id, {})
        target_data = room.get(target)
        if not target_data:
            return
        message = dict(payload)
        message["from"] = sender_id
        try:
            await target_data["websocket"].send_json(message)
        except Exception:
            pass

    async def disconnect(self, room_id: str, client_id: str):
        room = self.rooms.get(room_id, {})
        room.pop(client_id, None)
        for data in list(room.values()):
            try:
                await data["websocket"].send_json({"type": "peer-left", "client_id": client_id})
            except Exception:
                pass
        if not room:
            self.rooms.pop(room_id, None)


signal_manager = MeetingSignalManager()


@app.websocket("/ws/meeting/{meeting_id}")
async def meeting_signaling(websocket: WebSocket, meeting_id: int):
    """WebRTC signaling endpoint for any number of browser participants."""
    client_id = None
    room_id = str(meeting_id)
    try:
        # First message identifies the browser tab/user.
        await websocket.accept()
        first = await websocket.receive_json()
        if first.get("type") != "join":
            await websocket.close(code=1008)
            return
        client_id = str(first.get("client_id") or "")
        name = str(first.get("name") or "Participant")[:100]
        if not client_id:
            await websocket.close(code=1008)
            return

        # We already accepted above, so perform the same room registration inline.
        room = signal_manager.rooms.setdefault(room_id, {})
        existing = [{"client_id": cid, "name": data["name"]} for cid, data in room.items()]
        room[client_id] = {"websocket": websocket, "name": name}
        await websocket.send_json({"type": "peers", "peers": existing})
        for cid, data in list(room.items()):
            if cid != client_id:
                try:
                    await data["websocket"].send_json({"type": "peer-joined", "peer": {"client_id": client_id, "name": name}})
                except Exception:
                    pass

        while True:
            payload = await websocket.receive_json()
            if payload.get("type") in {"offer", "answer", "ice"}:
                await signal_manager.relay(room_id, client_id, payload)
<<<<<<< HEAD
            elif payload.get("type") == "transcript-entry":
                # Transcript entries are persisted through the REST API; the socket
                # only broadcasts the already-created entry to all live participants.
                message = {"type": "transcript-entry", "entry": payload.get("entry")}
                for cid, data in list(signal_manager.rooms.get(room_id, {}).items()):
                    if cid == client_id:
                        continue
                    try:
                        await data["websocket"].send_json(message)
                    except Exception:
                        pass
            elif payload.get("type") == "task-completed":
                message = {"type": "task-completed", "completion": payload.get("completion")}
                for cid, data in list(signal_manager.rooms.get(room_id, {}).items()):
                    if cid == client_id:
                        continue
                    try:
                        await data["websocket"].send_json(message)
                    except Exception:
                        pass
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
            elif payload.get("type") == "leave":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if client_id:
            await signal_manager.disconnect(room_id, client_id)
