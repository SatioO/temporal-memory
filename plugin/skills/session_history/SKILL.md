---
name: session-history
description: Show recent session history for this project. Use when user asks about past sessions, prior work, or "what did we do last time".
user-invocable: true
---

Fetch recent session history from graphmind:

Use the Bash tool to run: `curl -sS -H "Authorization: Bearer ${GRAPHMIND_SECRET:-}" "http://${GRAPHMIND_URL:-localhost:3111}/graphmind/sessions" 2>/dev/null || echo '{"sessions":[]}'`

Task:
- Parse the returned JSON.
- If no sessions exist, respond: "No session history found."

Output format (strict):

Timeline (most recent first)

For each session:
- [Session {id_short}] {project} — {start_time} — {status}
- Observations Count: {count}

Rules:
- Sort sessions in reverse chronological order (latest first)
- Use only data returned from the API — do not hallucinate or infer missing values
- If fields are missing, omit them (do not print placeholders)
- Do not include raw JSON in output
- Do not add explanations outside the timeline

Notes:
- {id_short} = first 8 characters of session ID