# Decision Trace

The Investigation Desk explains a decision in order:

1. source record and data authority;
2. normalized text and detected language;
3. deterministic negative signals;
4. explicit positive exceptions;
5. landing-page evidence or a clear unavailable state;
6. advertiser-level evidence or a clear unavailable state;
7. source prior and category;
8. score and confidence components with calibration warning;
9. public policy references;
10. evaluated strategy version and authoritative status;
11. recommendation and human-review requirement;
12. optional LLM call status;
13. separately stored reviewer feedback.

The trace never claims a risk score is a probability of violation. Candidate traces remain shadow output and cannot overwrite the current recommendation. Feedback adds an audit event without mutating the original evidence or decision.
