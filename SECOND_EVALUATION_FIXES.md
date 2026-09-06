# Second Evaluation Fixes

## 1. Whole-meeting shared transcript
- Each participant runs browser speech recognition for their own microphone.
- Final utterances are saved as individual transcript entries with meeting ID, user ID, speaker name and timestamp.
- Entries are broadcast to connected participants through the existing meeting WebSocket.
- The transcript is loaded from the database when a participant opens the meeting, so it is not lost when someone refreshes or joins later.
- Interim speech is never saved, preventing repeated partial text.

## 2. Cross-meeting automatic task completion
- Every final utterance is checked for explicit completion language.
- The backend searches the speaker's pending/submitted tasks from all meetings.
- The spoken task keywords are matched against existing task titles.
- A task is automatically completed only when there is an explicit completion phrase and a meaningful task-name match, reducing false positives.
- The completion event is broadcast to participants currently in the meeting.

## Edge cases handled
- Duplicate interim speech is not persisted.
- Empty and oversized transcript entries are rejected/truncated safely.
- Generic statements like `I am done` do not complete a task without a task match.
- Completed tasks are not selected again for automatic completion.
- Refresh/rejoin loads the full persisted meeting transcript.
- Transcript broadcast is separate from WebRTC media signaling.
