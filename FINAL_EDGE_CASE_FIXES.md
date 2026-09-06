# Final Edge-Case Hardening

This build adds conservative protections for the second-evaluation workflow.

## Transcript
- Full meeting transcript persists in SQLite and reloads after refresh/rejoin.
- Entries are tagged with authenticated speaker identity and timestamp.
- Interim speech is never persisted.
- Frontend serializes final utterances through a queue, so fast consecutive sentences are not dropped.
- Immediate duplicate finals are ignored on the client and duplicate persisted entries are prevented on the server.
- Empty and oversized entries are handled safely.

## Automatic completion across meetings
- Only the assigned authenticated speaker is considered.
- Only Pending tasks can be auto-completed; Submitted and Completed tasks are not changed.
- Explicit negative statements (for example, "I have not completed it") and future statements (for example, "I will complete it") are rejected.
- Generic completion language without task keywords does not complete a task.
- Similar pending tasks require a clear winner; near-ties are treated as ambiguous and are left unchanged.
- Completion records include the triggering meeting statement in the approval note.

## Task creation
- Repeated clicks or repeated detection cannot create an identical active task with the same meeting, assignee, title and deadline.

## Remaining platform limitations
Browser speech recognition is not server-side speaker diarization. Each participant's browser recognizes its own microphone and the authenticated user ID is used as the speaker identity. TURN infrastructure and production-grade speech diarization are separate deployment features.
