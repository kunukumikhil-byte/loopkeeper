import random
import re
import string

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from database import get_db
from models import Meeting, MeetingParticipant, User

router = APIRouter(prefix="/api/meetings", tags=["Meetings"])


def current_user(
    x_user_id: int = Header(...),
    db: Session = Depends(get_db)
):
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
    participant = db.query(MeetingParticipant).filter(
        MeetingParticipant.meeting_id == meeting_id,
        MeetingParticipant.user_id == user_id
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Join this meeting first")


@router.post("/")
def create_meeting(
    title: str,
    notes: str = "",
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    title = (title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Meeting title is required")

    meeting = Meeting(
        title=title,
        notes=(notes or "").strip(),
        code=make_code(db),
        creator_id=user.id
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # The creator automatically joins the meeting.
    db.add(MeetingParticipant(meeting_id=meeting.id, user_id=user.id))
    db.commit()

    return {"message": "Meeting created", "meeting": serialize_meeting(meeting, db)}


@router.post("/join")
def join_meeting(
    code: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(
        Meeting.code == (code or "").strip().upper()
    ).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting code not found")

    already_joined = db.query(MeetingParticipant).filter(
        MeetingParticipant.meeting_id == meeting.id,
        MeetingParticipant.user_id == user.id
    ).first()

    if not already_joined:
        db.add(MeetingParticipant(meeting_id=meeting.id, user_id=user.id))
        db.commit()

    return {"message": "Joined meeting successfully", "meeting": serialize_meeting(meeting, db)}


@router.get("/")
def get_my_meetings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    meeting_ids = [row.meeting_id for row in db.query(MeetingParticipant).filter(
        MeetingParticipant.user_id == user.id
    ).all()]

    if not meeting_ids:
        return []

    meetings = db.query(Meeting).filter(Meeting.id.in_(meeting_ids)).order_by(
        Meeting.created_at.desc()
    ).all()
    return [serialize_meeting(meeting, db) for meeting in meetings]


@router.get("/{meeting_id}")
def get_meeting(
    meeting_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    _require_participant(meeting_id, user.id, db)
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return serialize_meeting(meeting, db)


@router.put("/{meeting_id}/transcript")
def save_transcript(
    meeting_id: int,
    transcript: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    _require_participant(meeting_id, user.id, db)
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting.notes = (transcript or "").strip()
    db.commit()
    return {"message": "Transcript saved"}


@router.post("/{meeting_id}/extract-tasks")
def extract_tasks(
    meeting_id: int,
    transcript: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    _require_participant(meeting_id, user.id, db)
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    people = []
    for row in db.query(MeetingParticipant).filter(
        MeetingParticipant.meeting_id == meeting_id
    ).all():
        person = db.get(User, row.user_id)
        if person:
            people.append({"id": person.id, "name": person.name, "email": person.email})

    candidates = extract_task_candidates(transcript, people)
    return {
        "tasks": candidates,
        "note": "Every suggestion is editable. Review the task, person and deadline before assigning it."
    }


def extract_task_candidates(transcript, people):
    """Find task assignments in noisy browser speech-recognition transcripts.

    Browser speech recognition often returns one long line without punctuation and can
    repeat interim words. Therefore this detector does not require a sentence to start
    with a person's name. It searches around every meeting participant's name and stops
    when the next assignment starts.
    """
    if not transcript or not people:
        return []

    text = re.sub(r"\s+", " ", transcript).strip()
    if not text:
        return []

    action_words = (
        "complete|finish|prepare|create|build|send|review|update|fix|implement|"
        "design|write|make|test|deploy|submit|share|deliver|organize|analyze|"
        "research|check|call|contact|plan|work on|do"
    )
    modal = r"(?:will|should|need to|needs to|have to|has to|must|can|please)"

    # Sort longest first so names such as "John Smith" are checked before "John".
    people_sorted = sorted(people, key=lambda p: len(p["name"]), reverse=True)
    found = []

    for person in people_sorted:
        name = person["name"].strip()
        if not name:
            continue
        name_pattern = re.escape(name)

        # Examples supported:
        # "Vivek will complete the UI design by Friday"
        # "Vivek, you complete the UI design by Friday"
        # "Please Vivek finish the dashboard before Monday"
        patterns = [
            rf"\b{name_pattern}\b\s*,?\s*(?:you\s+)?{modal}\s+(?P<task>.+)",
            rf"\b{name_pattern}\b\s*,?\s*(?:you\s+)?(?P<task>(?:{action_words})\b.+)",
            rf"\bplease\s+{name_pattern}\b\s+(?:to\s+)?(?P<task>(?:{action_words})\b.+)",
            rf"\b{name_pattern}\b\s+(?:is|will be)\s+responsible for\s+(?P<task>.+)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                raw_task = match.group("task").strip()
                if not raw_task:
                    continue

                # Stop at the next participant-name assignment. This is important when
                # speech recognition returns the whole meeting as a single paragraph.
                next_start = None
                tail_start = match.start("task")
                for other in people_sorted:
                    other_name = other["name"].strip()
                    if not other_name:
                        continue
                    boundary = rf"\b{re.escape(other_name)}\b\s*,?\s*(?:you\s+)?(?:{modal}|(?:{action_words})\b)"
                    next_match = re.search(boundary, text[tail_start + 1:], flags=re.I)
                    if next_match:
                        pos = tail_start + 1 + next_match.start()
                        if next_start is None or pos < next_start:
                            next_start = pos
                if next_start is not None:
                    raw_task = text[tail_start:next_start].strip(" ,.;:-")

                # Prefer the first sentence/clause when punctuation is available.
                raw_task = re.split(r"[.!?;\n]", raw_task, maxsplit=1)[0].strip()
                raw_task = re.sub(r"\s+", " ", raw_task)

                title, deadline = split_deadline(raw_task)
                title = clean_task_title(title)
                if len(title) < 3:
                    continue

                found.append({
                    "title": title[:255],
                    "assigned_to_id": person["id"],
                    "assigned_to_name": name,
                    "assigned_to_email": person.get("email", ""),
                    "deadline": deadline[:100],
                    "source": match.group(0)[:500]
                })

    # Remove duplicates. SpeechRecognition may repeat a phrase many times.
    result = []
    seen = set()
    for item in found:
        key = (
            item["assigned_to_id"],
            re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip(),
            item["deadline"].lower().strip()
        )
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def split_deadline(task):
    """Separate common spoken deadline phrases from the task title."""
    task = task.strip(" ,.;:-")
    deadline = ""

    # by Friday / before Monday / on 2026-09-10 / tomorrow / next week
    match = re.search(
        r"\b(by|before|on)\s+(today|tomorrow|tonight|"
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"next\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
        r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+)\b",
        task,
        flags=re.I
    )
    if match:
        deadline = match.group(2).strip()
        task = task[:match.start()].strip(" ,.;:-")
    else:
        # "Vivek will do the task tomorrow" is also common in speech.
        match = re.search(r"\b(today|tomorrow|tonight|next week|next month)\b", task, flags=re.I)
        if match:
            deadline = match.group(1).strip()
            task = task[:match.start()].strip(" ,.;:-")

    return task, deadline


def clean_task_title(title):
    title = re.sub(r"^(?:to\s+)?", "", title.strip(), flags=re.I)
    # Remove common speech filler at the beginning.
    title = re.sub(r"^(?:the task is to|task is to)\s+", "", title, flags=re.I)
    return title.strip(" ,.;:-")


def serialize_meeting(meeting, db):
    participants = db.query(MeetingParticipant).filter(
        MeetingParticipant.meeting_id == meeting.id
    ).all()

    users = []
    for participant in participants:
        user = db.get(User, participant.user_id)
        if user:
            users.append({"id": user.id, "name": user.name, "email": user.email})

    creator = db.get(User, meeting.creator_id)
    return {
        "id": meeting.id,
        "title": meeting.title,
        "code": meeting.code,
        "notes": meeting.notes or "",
        "creator": creator.name if creator else "Unknown",
        "creator_id": meeting.creator_id,
        "participants": users,
        "created_at": meeting.created_at.isoformat()
    }
