# Cross-Meeting Completion + Submission Gate Fix

## New workflow

### 1. Employee says in any later meeting: “I have completed my work”
LoopKeeper matches the statement to the employee's unfinished task across meetings.

### 2. Submission check happens first
- **No submission/file exists:** task stays **Pending**. LoopKeeper records the declaration and creates a manager-facing report saying the employee declared completion without submitting evidence. SMTP email is sent when configured.
- **Submission/file exists:** LoopKeeper keeps the actual submission intact and sends that evidence to the AI reviewer. The spoken meeting sentence is stored separately as a completion declaration.

### 3. AI result
- **PASS:** task becomes **Submitted** and is clearly marked as **waiting for the manager's final response/approval**. It is not silently marked final Completed.
- **NEEDS_MANUAL_REVIEW / REJECT:** task is placed in the manager review flow with the AI reason and report.

### 4. Final completion
Only the manager/task giver's approval endpoint changes the task to **Completed**.

## Important safety fixes
- A meeting sentence no longer overwrites a previously submitted work description.
- Existing submitted tasks can be detected when the employee declares completion in a later meeting.
- Generic “I completed my work” is only linked automatically when there is exactly one unfinished task; multiple possible tasks remain ambiguous.
- SMTP failures never crash the meeting or task flow.
