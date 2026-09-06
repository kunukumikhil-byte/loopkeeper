import random
import re
import string
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.orm import Session

from database import get_db
from models import Meeting, MeetingParticipant, MeetingTranscript, Task, User
from ai_service import verify_task_with_gemini

router = APIRouter(prefix="/api/meetings", tags=["Meetings"])


def current_user(x_user_id: int = Header(...), db: Session = Depends(get_db)):
    user = db.get(User, x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user


def make_code(db: Session):
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not db.query(Meeting).filter(Meeting.code == code).first():
            return code


def _require_participant(meeting_id: int, user_id: int, db: Session):
    participant = db.query(MeetingParticipant).filter_by(meeting_id=meeting_id, user_id=user_id).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Join this meeting first")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def _notify_manager(task, *, subject: str, body: str) -> bool:
    """Optionally email the task giver/manager; failures never break a meeting."""
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not host or not sender or not password or not task.assigned_by or not task.assigned_by.email:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = task.assigned_by.email
        msg.set_content(body)
        port = int(os.getenv("SMTP_PORT", "587"))
        use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"}
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                server.login(os.getenv("SMTP_USER", sender), password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.ehlo(); server.starttls(); server.ehlo()
                server.login(os.getenv("SMTP_USER", sender), password)
                server.send_message(msg)
        return True
    except Exception:
        return False


def _notify_manager_of_ai_review(task, review, statement: str, *, no_submission: bool = False) -> bool:
    employee = task.assigned_to.name if task.assigned_to else "Unknown"
    if no_submission:
        return _notify_manager(
            task,
            subject=f"LoopKeeper: completion declared but work not submitted — {task.title}",
            body=(
                "An employee declared the task complete during a meeting, but LoopKeeper found no submitted work or file.\n\n"
                f"Task: {task.title}\n"
                f"Employee: {employee}\n"
                f"Meeting statement: {statement[:1500]}\n\n"
                "The task was NOT marked completed. Please ask the employee to submit the work/evidence before approval.\n"
                "Review in LoopKeeper > Assigned Tasks."
            ),
        )
    return _notify_manager(
        task,
        subject=f"LoopKeeper: AI completion review — {task.title}",
        body=(
            "An employee declared a task complete during a meeting and LoopKeeper reviewed the submitted evidence.\n\n"
            f"Task: {task.title}\n"
            f"Employee: {employee}\n"
            f"AI decision: {review.get('decision', 'NEEDS_MANUAL_REVIEW')}\n"
            f"AI reason: {review.get('reason', '')}\n"
            f"Meeting statement: {statement[:1500]}\n\n"
            "The task is waiting for your final review in LoopKeeper > Assigned Tasks."
        ),
    )


def serialize_entry(entry):
    return {
        "id": entry.id, "meeting_id": entry.meeting_id, "user_id": entry.user_id,
        "speaker_name": entry.speaker_name, "text": entry.text,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def serialize_meeting(meeting, db):
    rows = db.query(MeetingParticipant).filter_by(meeting_id=meeting.id).all()
    users = []
    for row in rows:
        user = db.get(User, row.user_id)
        if user:
            users.append({"id": user.id, "name": user.name, "email": user.email})
    creator = db.get(User, meeting.creator_id)
    return {"id": meeting.id, "title": meeting.title, "code": meeting.code,
            "notes": meeting.notes or "", "creator": creator.name if creator else "Unknown",
            "creator_id": meeting.creator_id, "participants": users,
            "created_at": meeting.created_at.isoformat()}


@router.post("/")
def create_meeting(title: str, notes: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Meeting title is required")
    meeting = Meeting(title=title[:255], notes=(notes or "").strip(), code=make_code(db), creator_id=user.id)
    db.add(meeting); db.commit(); db.refresh(meeting)
    db.add(MeetingParticipant(meeting_id=meeting.id, user_id=user.id)); db.commit()
    return {"message": "Meeting created", "meeting": serialize_meeting(meeting, db)}


@router.post("/join")
def join_meeting(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.code == (code or "").strip().upper()).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting code not found")
    if not db.query(MeetingParticipant).filter_by(meeting_id=meeting.id, user_id=user.id).first():
        db.add(MeetingParticipant(meeting_id=meeting.id, user_id=user.id)); db.commit()
    return {"message": "Joined meeting successfully", "meeting": serialize_meeting(meeting, db)}


@router.get("/")
def get_my_meetings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = [r.meeting_id for r in db.query(MeetingParticipant).filter_by(user_id=user.id).all()]
    if not ids: return []
    return [serialize_meeting(m, db) for m in db.query(Meeting).filter(Meeting.id.in_(ids)).order_by(Meeting.created_at.desc()).all()]


@router.get("/{meeting_id}")
def get_meeting(meeting_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_participant(meeting_id, user.id, db)
    meeting = db.get(Meeting, meeting_id)
    if not meeting: raise HTTPException(status_code=404, detail="Meeting not found")
    return serialize_meeting(meeting, db)


@router.get("/{meeting_id}/transcript")
def get_transcript(meeting_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_participant(meeting_id, user.id, db)
    entries = db.query(MeetingTranscript).filter_by(meeting_id=meeting_id).order_by(MeetingTranscript.created_at, MeetingTranscript.id).all()
    return {"entries": [serialize_entry(e) for e in entries]}


@router.post("/{meeting_id}/transcript/entry")
def add_transcript_entry(meeting_id: int, text: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_participant(meeting_id, user.id, db)
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        raise HTTPException(status_code=400, detail="Transcript text is required")
    if len(text) > 2000:
        text = text[:2000].rstrip()

    # Speech engines occasionally emit the same final phrase repeatedly.  Do not
    # persist duplicates from the same speaker when they occur back-to-back.
    norm = _normalize(text)
    recent = db.query(MeetingTranscript).filter_by(meeting_id=meeting_id, user_id=user.id)\
        .order_by(MeetingTranscript.id.desc()).first()
    if recent and _normalize(recent.text) == norm:
        completion = detect_and_complete_task(user, text, db)
        return {"entry": serialize_entry(recent), "completion": completion, "duplicate": True}

    entry = MeetingTranscript(meeting_id=meeting_id, user_id=user.id, speaker_name=user.name[:100], text=text)
    db.add(entry); db.commit(); db.refresh(entry)
    completion = detect_and_complete_task(user, text, db)
    return {"entry": serialize_entry(entry), "completion": completion, "duplicate": False}


@router.put("/{meeting_id}/transcript")
def save_transcript(
    meeting_id: int,
    transcript: str = "",
    payload: dict | None = Body(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # Preserve manually pasted/edited transcript text as meeting notes. Live
    # speech remains stored entry-by-entry in MeetingTranscript.
    _require_participant(meeting_id, user.id, db)
    meeting = db.get(Meeting, meeting_id)
    if not meeting: raise HTTPException(status_code=404, detail="Meeting not found")
    if payload and not transcript:
        transcript = str(payload.get("transcript") or "")
    meeting.notes = re.sub(r"\s+", " ", (transcript or "").strip())[:50000]
    db.commit()
    return {"message": "Transcript saved"}


@router.post("/{meeting_id}/extract-tasks")
def extract_tasks(
    meeting_id: int,
    transcript: str = "",
    payload: dict | None = Body(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _require_participant(meeting_id, user.id, db)
    meeting = db.get(Meeting, meeting_id)
    if not meeting: raise HTTPException(status_code=404, detail="Meeting not found")
    if payload and not transcript:
        transcript = str(payload.get("transcript") or "")
    people=[]
    for row in db.query(MeetingParticipant).filter_by(meeting_id=meeting_id).all():
        person=db.get(User,row.user_id)
        if person: people.append({"id":person.id,"name":person.name})
    if not transcript.strip():
        transcript = " ".join(
            e.text for e in db.query(MeetingTranscript)
            .filter_by(meeting_id=meeting_id)
            .order_by(MeetingTranscript.created_at, MeetingTranscript.id)
            .all()
        )
    if not transcript.strip() and meeting.notes:
        transcript = meeting.notes
    # The same transcript box is used for both new assignments and for an
    # assignee declaring completion in a later meeting.  A completion
    # declaration is therefore checked here as well; otherwise the UI would
    # incorrectly show "No clear task assignments detected" for valid text such
    # as "I have completed the UI and UX work".
    completion = detect_and_complete_task(user, transcript, db)
    tasks = extract_task_candidates(transcript, people)
    return {
        "tasks": tasks,
        "completion": completion,
        "note": (
            "Completion declaration linked for review."
            if completion else
            "Suggestions are editable. Review before assigning."
        ),
    }


def extract_task_candidates(transcript, people):
    """Extract reviewable task suggestions from natural meeting language.

    This intentionally accepts imperfect speech-to-text grammar such as
    "mikhil complete the ui and ux design by tomorrow".
    """
    if not transcript or not people:
        return []

    text = re.sub(r"\s+", " ", transcript).strip()
    action_words = (
        "complete|finish|prepare|create|build|send|review|update|fix|implement|"
        "design|write|make|test|deploy|submit|share|deliver|organize|analyze|"
        "research|check|call|contact|plan|work on|do|develop|refactor|document"
    )
    modal = r"(?:will|should|need to|needs to|have to|has to|must|please|kindly)"
    found = []

    for person in sorted(people, key=lambda p: len((p.get("name") or "")), reverse=True):
        name = (person.get("name") or "").strip()
        if not name:
            continue
        np = re.escape(name)

        # Supports: "Mikhil complete...", "Mikhil, complete...",
        # "Mikhil should complete...", and "please Mikhil complete..."
        patterns = [
            rf"\b{np}\b\s*,?\s*(?:you\s+)?(?:{modal})\s+(?:to\s+)?(?P<task>(?:{action_words})\b.+?)(?=$|[.!?;\n])",
            rf"\b{np}\b\s*,?\s*(?:you\s+)?(?P<task>(?:{action_words})\b.+?)(?=$|[.!?;\n])",
            rf"\b(?:please|kindly)\s+{np}\b\s+(?:to\s+)?(?P<task>(?:{action_words})\b.+?)(?=$|[.!?;\n])",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                raw = match.group("task").strip()
                # Avoid swallowing a second assignment joined by common connectors.
                raw = re.split(r"\s+(?:and\s+then|also\s+please|next)\s+", raw, maxsplit=1, flags=re.I)[0].strip()
                title, deadline = split_deadline(raw)
                title = clean_task_title(title)
                if len(title) >= 3:
                    found.append({
                        "title": title[:255],
                        "assigned_to_id": person["id"],
                        "assigned_to_name": name,
                        "deadline": deadline[:100],
                        "source": match.group(0)[:500],
                    })

    # Fallback for simple imperative speech where punctuation/spacing is poor.
    if not found:
        low = text.lower()
        for person in people:
            name = (person.get("name") or "").strip()
            if not name:
                continue
            m = re.search(
                rf"\b{re.escape(name)}\b\s+(?P<task>(?:{action_words})\b.+)",
                text,
                flags=re.I,
            )
            if m:
                raw = re.split(r"[.!?;\n]", m.group("task"), maxsplit=1)[0].strip()
                title, deadline = split_deadline(raw)
                title = clean_task_title(title)
                if len(title) >= 3:
                    found.append({
                        "title": title[:255],
                        "assigned_to_id": person["id"],
                        "assigned_to_name": name,
                        "deadline": deadline[:100],
                        "source": m.group(0)[:500],
                    })

    result, seen = [], set()
    for item in found:
        key = (
            item["assigned_to_id"],
            _normalize(item["title"]),
            _normalize(item["deadline"]),
        )
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result[:20]


def split_deadline(task):
    task = task.strip(" ,.;:-")
    deadline = ""

    patterns = [
        # by tomorrow, before Friday, on Monday
        r"\b(?:by|before|on)\s+((?:today|tomorrow|tonight|day after tomorrow|"
        r"(?:next|this)\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+)"
        r"(?:\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)\b",
        # due tomorrow / deadline is Friday
        r"\b(?:due|deadline(?:\s+is)?|finish\s+by)\s+"
        r"((?:today|tomorrow|tonight|day after tomorrow|(?:next|this)\s+\w+|\w+day)"
        r"(?:\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, task, flags=re.I)
        if match:
            deadline = match.group(1).strip()
            task = (task[:match.start()] + task[match.end():]).strip(" ,.;:-")
            break
    return task, deadline


def clean_task_title(title):
    title = re.sub(r"^(?:to\s+)?", "", title.strip(), flags=re.I)
    title = re.sub(r"^(?:the task is to|task is to)\s+", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" ,.;:-")
    return title


def detect_and_complete_task(user, spoken_text, db):
    """Detect a completion declaration in any meeting and AI-review it.

    Tasks are matched across meetings because the speaker may report completion in
    a later meeting.  The declaration itself is treated as evidence and is sent
    through the same AI/local reviewer used by normal task submissions.

    PASS  -> automatically Completed.
    REJECT/NEEDS_MANUAL_REVIEW -> Submitted for the task giver/manager, with the
    AI reason stored as a report.  Ambiguous or unsupported statements are never
    attached to a random task.
    """
    raw = (spoken_text or "").strip()
    text = _normalize(raw)
    if not text:
        return None

    blocked = [
        r"\b(?:not|never) (?:yet )?(?:completed|finished|done)\b",
        r"\b(?:have not|havent|did not|didnt|cannot|cant) (?:completed|finished|done)\b",
        r"\b(?:still|currently) working\b",
        r"\b(?:will|shall|plan to|going to|need to|needs to|have to|has to) (?:complete|finish|do)\b",
        r"\b(?:almost|nearly|trying to) (?:complete|finish)\b",
    ]
    if any(re.search(p, text) for p in blocked):
        return None

    completion_patterns = [
        r"\bi (?:have )?(?:completed|finished)\b",
        r"\bi (?:have )?been (?:completed|finished)\b",
        r"\bi completed\b",
        r"\bi finished\b",
        r"\bi(?: am|'m) done with\b",
        r"\bi (?:have )?done\b",
        r"\bmy .*? is (?:completed|finished|done)\b",
    ]
    if not any(re.search(p, text) for p in completion_patterns):
        return None

    # Look across meetings and include pending or already-submitted work. A
    # completion declaration must be able to verify an existing submission.
    tasks = db.query(Task).filter(
        Task.assigned_to_id == user.id,
        Task.status != "Completed"
    ).order_by(Task.created_at.desc()).all()
    if not tasks:
        return None

    stop = {
        "i","have","has","completed","complete","finished","finish","done","with",
        "the","a","an","task","work","is","now","my","it","this","that","been",
        "havebeen","just","already","successfully","finally","all","was"
    }
    spoken_tokens = {t for t in re.findall(r"[a-z0-9]+", text) if len(t) >= 2 and t not in stop}

    def tokens(value):
        return {t for t in re.findall(r"[a-z0-9]+", _normalize(value)) if len(t) >= 2 and t not in stop}

    scored = []
    for task in tasks:
        task_norm = _normalize(task.title)
        task_tokens = tokens(task.title)
        overlap_count = len(spoken_tokens & task_tokens)
        coverage = overlap_count / max(1, len(task_tokens))
        precision = overlap_count / max(1, len(spoken_tokens)) if spoken_tokens else 0.0
        ratio = SequenceMatcher(None, " ".join(sorted(spoken_tokens)), " ".join(sorted(task_tokens))).ratio() if spoken_tokens else 0.0
        exact_phrase = bool(task_norm and task_norm in text)
        score = (0.60 * coverage) + (0.25 * precision) + (0.15 * ratio)
        if exact_phrase:
            score = max(score, 0.99)
        scored.append((score, coverage, precision, overlap_count, task))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_coverage, best_precision, best_overlap, best = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0

    # "I have completed my work" can only be linked safely when the employee has
    # exactly one active task. With multiple tasks it is ambiguous and must not
    # complete the wrong one.
    generic_declaration = not spoken_tokens or not any(item[3] > 0 for item in scored)
    if generic_declaration:
        if len(tasks) != 1:
            return None
        best = tasks[0]
        best_score = 0.50
        match_mode = "single-active-task"
    else:
        if best_overlap == 0 or best_score < 0.52:
            return None
        if len(scored) > 1 and best_score - second_score < 0.10:
            return None
        if best_overlap == 1 and len(tasks) > 1 and best_coverage < 0.60:
            return None
        match_mode = "task-evidence"

    # Record the spoken declaration, but NEVER overwrite the employee's actual
    # submission with speech. First check whether the task was submitted.
    best.completion_declared_at = datetime.utcnow()
    best.completion_statement = raw[:2000]
    has_submission = bool((best.submission or "").strip() or best.submission_stored_name)

    if not has_submission:
        best.status = "Pending"
        best.ai_review_status = "NOT_SUBMITTED"
        best.ai_review_reason = (
            "The employee declared completion in the meeting, but no work, evidence, or file has been submitted yet."
        )
        best.ai_corrected_submission = None
        best.ai_confidence = None
        best.ai_reviewed_at = None
        best.approved_at = None
        best.approval_note = (
            "Manager attention required: the employee declared this task complete in a meeting, "
            "but did not submit the work/evidence. The task remains Pending until submission."
        )
        email_notified = _notify_manager_of_ai_review(
            best,
            {"decision": "NOT_SUBMITTED", "reason": best.ai_review_reason},
            raw,
            no_submission=True,
        )
        outcome = "not_submitted_manager_notified"
        message = (
            "Completion was declared, but no submitted work was found. The task remains Pending and the manager was notified."
        )
        if email_notified:
            message += " An email notification was also sent to the manager."
    else:
        # Review the ACTUAL submitted evidence, not the meeting sentence.
        review = verify_task_with_gemini(
            title=best.title,
            deadline=best.deadline or "",
            submission=best.submission or "",
            filename=best.submission_filename,
        )
        best.ai_review_status = review.get("decision", "NEEDS_MANUAL_REVIEW")
        best.ai_review_reason = review.get("reason", "AI review did not return a reason.")
        best.ai_corrected_submission = review.get("corrected_submission") or best.submission
        best.ai_confidence = f"{float(review.get('confidence', 0.0)):.2f}"
        best.ai_reviewed_at = datetime.utcnow() if review.get("available") else None

        # Even when AI passes, completion by the employee is not final manager
        # approval. Keep the task in Submitted/Waiting for manager response.
        best.status = "Submitted"
        best.approved_at = None
        if best.ai_review_status == "PASS":
            best.approval_note = (
                "AI verified the submitted work after the employee declared completion in a meeting. "
                "Waiting for the manager's final response and approval. " + best.ai_review_reason
            )
            outcome = "ai_pass_waiting_manager"
            message = "AI verified the submitted work. The task is now waiting for the manager's final response."
        else:
            best.approval_note = (
                "Manager attention required after a cross-meeting completion declaration. "
                f"AI result: {best.ai_review_status}. {best.ai_review_reason}"
            )
            outcome = "ai_issue_manager_review"
            message = "AI found an issue or could not fully verify the submitted work. A report was sent to the manager for review."

        email_notified = _notify_manager_of_ai_review(best, review, raw)
        if email_notified:
            message += " An email notification was also sent to the manager."
    db.commit(); db.refresh(best)
    return {
        "task_id": best.id,
        "title": best.title,
        "status": best.status,
        "confidence": round(float(best_score), 2),
        "cross_meeting": True,
        "match_mode": match_mode,
        "outcome": outcome,
        "ai": {
            "decision": best.ai_review_status,
            "reason": best.ai_review_reason,
            "confidence": best.ai_confidence,
            "engine": (review.get("engine", "AI review") if has_submission else "Submission check"),
        },
        "manager_id": best.assigned_by_id,
        "manager_name": best.assigned_by.name if best.assigned_by else "Task manager",
        "manager_email_notified": locals().get("email_notified", False),
        "message": message,
    }

