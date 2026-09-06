# Cross-Meeting AI Auto-Completion

When an employee reports completion in a later meeting, LoopKeeper searches all active tasks assigned to that employee, not only tasks created in the current meeting.

## Flow
1. Detect an explicit completion statement.
2. Reject negative, future, uncertain, and "still working" statements.
3. Match the statement to a pending task.
4. Generic wording such as "I have completed my work" is linked only when the employee has exactly one pending task. Multiple pending tasks remain ambiguous and are not auto-completed.
5. Send the declaration through the same AI/local review engine used for normal task submissions.
6. `PASS` automatically marks the task `Completed`.
7. `REJECT` or `NEEDS_MANUAL_REVIEW` keeps the task in the manager's review queue and stores the AI report.
8. If optional SMTP settings are configured, the task giver/manager is also emailed.

The local fallback cannot inspect external files or work that was never submitted. It therefore does not pretend to know whether a vague statement is correct; uncertain cases are reported for manager review.
