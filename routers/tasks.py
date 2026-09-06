<<<<<<< HEAD
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
import os
import re
from ai_service import verify_task_with_gemini
=======
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import os
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c

from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Task, Meeting, MeetingParticipant, User

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])
BASE_DIR = Path(__file__).resolve().parent.parent
_configured_upload_dir = os.getenv("LOOPKEEPER_UPLOAD_DIR", "uploads").strip()
UPLOAD_DIR = Path(_configured_upload_dir)
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR
MAX_UPLOAD_BYTES = int(os.getenv("LOOPKEEPER_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))


def current_user(x_user_id: int = Header(...), db: Session = Depends(get_db)):
    user = db.get(User, x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user


def serialize_task(task):
    return {
        "id": task.id,
        "title": task.title,
        "deadline": task.deadline,
<<<<<<< HEAD
        "deadline_at": task.deadline_at.isoformat() if task.deadline_at else None,
        "deadline_status": task.deadline_status,
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
        "status": task.status,
        "submission": task.submission,
        "submission_filename": task.submission_filename,
        "has_file": bool(task.submission_stored_name),
        "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
        "approval_note": task.approval_note,
<<<<<<< HEAD
        "ai_review_status": task.ai_review_status,
        "ai_review_reason": task.ai_review_reason,
        "ai_corrected_submission": task.ai_corrected_submission,
        "ai_reviewed_at": task.ai_reviewed_at.isoformat() if task.ai_reviewed_at else None,
        "ai_confidence": task.ai_confidence,
        "completion_declared_at": task.completion_declared_at.isoformat() if task.completion_declared_at else None,
        "completion_statement": task.completion_statement,
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
        "approved_at": task.approved_at.isoformat() if task.approved_at else None,
        "meeting_id": task.meeting_id,
        "meeting_title": task.meeting.title if task.meeting else "",
        "assigned_to": {"id": task.assigned_to.id, "name": task.assigned_to.name},
        "assigned_by": {"id": task.assigned_by.id, "name": task.assigned_by.name},
        "created_at": task.created_at.isoformat(),
    }


<<<<<<< HEAD
def _parse_deadline(value: str):
    raw = (value or "").strip()
    if not raw:
        return None
    now = datetime.utcnow()
    low = raw.lower().strip()
    if low == "today":
        return now.replace(hour=23, minute=59, second=59, microsecond=0)
    if low == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).replace(hour=23, minute=59, second=59)
        except Exception:
            pass
    return None


def _refresh_deadline(task):
    if task.status == "Completed":
        task.deadline_status = "Completed"
        return
    if task.deadline_at and datetime.utcnow() > task.deadline_at:
        task.deadline_status = "Overdue"
    elif task.deadline_status != "Completed":
        task.deadline_status = "OnTrack"


def _apply_ai_review(task, result):
    task.ai_review_status = result["decision"]
    task.ai_review_reason = result["reason"]
    task.ai_corrected_submission = result.get("corrected_submission") or task.submission
    task.ai_confidence = f"{result.get('confidence', 0.0):.2f}"
    task.ai_reviewed_at = datetime.utcnow() if result.get("available") else None
    if result["decision"] == "REJECT":
        task.status = "Pending"
        task.approval_note = "AI rejected the submission: " + result["reason"]
    else:
        task.status = "Submitted"
        task.approval_note = "AI review: " + result["reason"]


def refresh_all_deadlines(db: Session):
    tasks = db.query(Task).filter(Task.status != "Completed").all()
    changed = False
    for task in tasks:
        before = task.deadline_status
        _refresh_deadline(task)
        changed = changed or before != task.deadline_status
    if changed:
        db.commit()


=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
@router.post("/")
def create_task(title: str, assigned_to_id: int, deadline: str = "", meeting_id: int = 0,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title is required")
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    giver = db.query(MeetingParticipant).filter_by(meeting_id=meeting_id, user_id=user.id).first()
    receiver = db.query(MeetingParticipant).filter_by(meeting_id=meeting_id, user_id=assigned_to_id).first()
    if not giver or not receiver:
        raise HTTPException(status_code=400, detail="Both users must be participants in this meeting")
<<<<<<< HEAD
    normalized_title = " ".join(title.lower().split())
    normalized_deadline = " ".join((deadline or "").lower().split())
    # Prevent accidental duplicate creation from repeated transcript detection/clicks.
    existing = db.query(Task).filter(
        Task.meeting_id == meeting_id,
        Task.assigned_to_id == assigned_to_id,
        Task.status.in_(["Pending", "Submitted"])
    ).all()
    for candidate in existing:
        if " ".join((candidate.title or "").lower().split()) == normalized_title and \
           " ".join((candidate.deadline or "").lower().split()) == normalized_deadline:
            return {"message": "Matching task already exists", "task": serialize_task(candidate), "duplicate": True}
    task = Task(title=title[:255], assigned_to_id=assigned_to_id, assigned_by_id=user.id,
                deadline=(deadline or "").strip()[:100], deadline_at=_parse_deadline(deadline), deadline_status="OnTrack", meeting_id=meeting_id, status="Pending")
    db.add(task); db.commit(); db.refresh(task)
    return {"message": "Task assigned successfully", "task": serialize_task(task), "duplicate": False}
=======
    task = Task(title=title[:255], assigned_to_id=assigned_to_id, assigned_by_id=user.id,
                deadline=(deadline or "").strip()[:100], meeting_id=meeting_id, status="Pending")
    db.add(task); db.commit(); db.refresh(task)
    return {"message": "Task assigned successfully", "task": serialize_task(task)}
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c


@router.get("/mine")
def get_my_tasks(user: User = Depends(current_user), db: Session = Depends(get_db)):
<<<<<<< HEAD
    refresh_all_deadlines(db)
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
    tasks = db.query(Task).filter(Task.assigned_to_id == user.id).order_by(Task.created_at.desc()).all()
    return [serialize_task(task) for task in tasks]


@router.get("/assigned")
def get_tasks_i_assigned(user: User = Depends(current_user), db: Session = Depends(get_db)):
<<<<<<< HEAD
    refresh_all_deadlines(db)
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
    tasks = db.query(Task).filter(Task.assigned_by_id == user.id).order_by(Task.created_at.desc()).all()
    return [serialize_task(task) for task in tasks]


@router.get("/stats")
def get_stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
<<<<<<< HEAD
    refresh_all_deadlines(db)
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
    tasks = db.query(Task).filter(Task.assigned_to_id == user.id).all()
    return {
        "total": len(tasks),
        "completed": sum(t.status == "Completed" for t in tasks),
        "pending": sum(t.status in {"Pending"} for t in tasks),
        "submitted": sum(t.status == "Submitted" for t in tasks),
    }


async def _save_upload(upload: UploadFile | None):
    if not upload or not upload.filename:
        return None
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(upload.filename).name[:200]
    stored_name = f"{uuid4().hex}_{safe_name}"
    target = UPLOAD_DIR / stored_name
    total = 0
    try:
        with target.open("wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"File is too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return safe_name, stored_name, upload.content_type or "application/octet-stream"


@router.post("/{task_id}/submit")
async def submit_work(task_id: int, submission: str = Form(""), file: UploadFile | None = File(None),
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assigned_to_id != user.id:
        raise HTTPException(status_code=403, detail="Only the assigned person can submit this task")
    if task.status == "Completed":
        raise HTTPException(status_code=400, detail="Completed tasks cannot be resubmitted")
    if not (submission or "").strip() and not (file and file.filename):
<<<<<<< HEAD
        raise HTTPException(status_code=400, detail="Add a note describing the completed work or attach a work file")
=======
        raise HTTPException(status_code=400, detail="Add a note or attach a work file before submitting")
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c

    saved = await _save_upload(file)
    if saved:
        if task.submission_stored_name:
            (UPLOAD_DIR / task.submission_stored_name).unlink(missing_ok=True)
        task.submission_filename, task.submission_stored_name, task.submission_content_type = saved
<<<<<<< HEAD
    task.submission = (submission or "").strip() or task.submission
    task.submitted_at = datetime.utcnow()
    task.completion_declared_at = task.completion_declared_at or datetime.utcnow()

    result = verify_task_with_gemini(
        title=task.title, deadline=task.deadline or "", submission=task.submission or "", filename=task.submission_filename
    )
    _apply_ai_review(task, result)
    _refresh_deadline(task)
    db.commit(); db.refresh(task)
    if result["decision"] == "REJECT":
        message = "AI found issues. The task was returned to you for correction."
    elif result["decision"] == "PASS":
        message = "AI verification passed. The task was forwarded to the boss for final review."
    elif result["decision"] == "NOT_CONFIGURED":
        message = "Gemini is not configured, so the task was forwarded for manual boss review."
    else:
        message = "AI could not verify everything automatically. The task was forwarded to the boss for review."
    return {"message": message, "task": serialize_task(task), "ai": result}
=======
    task.submission = (submission or "").strip() or None
    task.submitted_at = datetime.utcnow()
    task.status = "Submitted"
    task.approval_note = None
    db.commit(); db.refresh(task)
    return {"message": "Work submitted. Waiting for approval.", "task": serialize_task(task)}
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c


@router.get("/{task_id}/download")
def download_submission(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.id not in {task.assigned_to_id, task.assigned_by_id}:
        raise HTTPException(status_code=403, detail="You cannot access this submission")
    if not task.submission_stored_name:
        raise HTTPException(status_code=404, detail="No file was submitted")
    path = UPLOAD_DIR / task.submission_stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Submission file is no longer available")
    return FileResponse(path, media_type=task.submission_content_type or "application/octet-stream",
                        filename=task.submission_filename or "submission")


@router.post("/{task_id}/approve")
def approve_task(task_id: int, note: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assigned_by_id != user.id:
        raise HTTPException(status_code=403, detail="Only the task giver can approve this task")
    if task.status != "Submitted":
        raise HTTPException(status_code=400, detail="Only submitted tasks can be approved")
<<<<<<< HEAD
    if task.ai_review_status == "REJECT":
        raise HTTPException(status_code=400, detail="AI rejected this submission; the worker must correct and resubmit it")
    task.status = "Completed"; task.deadline_status = "Completed"; task.approval_note = (note or "").strip() or "Approved"; task.approved_at = datetime.utcnow()
=======
    task.status = "Completed"; task.approval_note = (note or "").strip() or "Approved"; task.approved_at = datetime.utcnow()
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
    db.commit(); db.refresh(task)
    return {"message": "Task approved and completed", "task": serialize_task(task)}


@router.post("/{task_id}/reject")
def reject_task(task_id: int, reason: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assigned_by_id != user.id:
        raise HTTPException(status_code=403, detail="Only the task giver can reject this task")
    if task.status != "Submitted":
        raise HTTPException(status_code=400, detail="Only submitted tasks can be rejected")
<<<<<<< HEAD
    task.status = "Pending"; task.ai_review_status = "NotReviewed"; task.ai_review_reason = None; task.ai_corrected_submission = None; task.ai_reviewed_at = None; task.ai_confidence = None; task.approval_note = (reason or "").strip() or "Please improve and submit again."; task.approved_at = None
=======
    task.status = "Pending"; task.approval_note = (reason or "").strip() or "Please improve and submit again."; task.approved_at = None
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
    db.commit(); db.refresh(task)
    return {"message": "Task rejected and returned for resubmission", "task": serialize_task(task)}
