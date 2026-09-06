# Transcript Detection Fix

The Detect Task Suggestions button now handles two different types of natural meeting statements:

1. New task assignments, such as `Mikhil complete the UI and UX design by tomorrow`.
2. Completion declarations, such as `I have completed the UI and UX work`.

Previously, a valid completion declaration could be sent to the assignment-only extractor and the UI would incorrectly show `No clear task assignments detected`.

Now the backend first checks whether the current authenticated participant is declaring completion of one of their pending tasks. If there is a strong unambiguous task-name match, the task moves to `Submitted` and the UI shows the completion result. It does not directly mark the task `Completed`; AI evidence review and the task giver's final approval remain intact.
