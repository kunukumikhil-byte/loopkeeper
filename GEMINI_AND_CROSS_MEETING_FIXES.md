# LoopKeeper — Gemini Verification + Cross-Meeting Completion

## Workflow
1. Boss assigns a task in Meeting 1.
2. The task is stored permanently with the assignee's user ID.
3. In Meeting 2, the same authenticated assignee can say: `I have completed the UI and UX design.`
4. LoopKeeper searches **all Pending tasks for that user across all meetings**. It does not filter by the current meeting ID.
5. A clear match records the completion statement and moves the task to `Submitted` rather than directly `Completed`.
6. The employee submits textual evidence/work. Gemini checks whether the evidence supports the assigned task.
7. `PASS` → forwarded to the boss for final review.
8. `REJECT` → returned to the employee with Gemini's reason/correction guidance.
9. `NEEDS_MANUAL_REVIEW` → forwarded to the boss without a false automatic pass.
10. Only the boss/task giver can press the final completion button.

## Deadline behavior
A deadline passing does **not** mean work was completed. This build marks such tasks `Overdue` automatically when tasks/stats are fetched. This avoids falsely claiming completion. Boss approval is still required to set `Completed`.

## Gemini setup
Add to `.env` locally or PythonAnywhere environment variables:

GEMINI_API_KEY=your_real_key
GEMINI_MODEL=gemini-2.5-flash-lite

Never commit the real key to GitHub.

## Best cross-meeting test
Meeting 1 (task assignment):
`Mikhil, please complete the UI and UX design by tomorrow.`

Review and assign the task to the correct authenticated Mikhil account.

Meeting 2 (same Mikhil account):
`I have completed the UI and UX design.`

The task from Meeting 1 should move to `Submitted` with the completion declaration attached. Submit a short description/proof of the work; Gemini evaluates it; then the boss makes the final `Completed` decision.
