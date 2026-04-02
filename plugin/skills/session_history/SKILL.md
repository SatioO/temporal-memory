---
name: session-history
description: Show recent session history for this project. Use when user asks about past sessions, prior work, or "what did we do last time".
user-invocable: true
---

Fetch recent session history from agentmemory:

Use the Bash tool to run: `curl -s -H "Authorization: Bearer ${AGENTMEMORY_SECRET:-}" "http://${AGENTMEMORY_URL:-localhost:3111}/agentmemory/sessions" 2>/dev/null || echo '{"sessions":[]}'`

Task:
- Parse the returned JSON.
- If no sessions exist, respond: "No session history found."

Output format (strict):

Timeline (most recent first)

For each session:
- [Session {id_short}] {project} — {start_time} — {status}
- Observations: {count}

If summary exists:
  - Title: {title}
  - Decisions:
    - {decision_1}
    - {decision_2}

If observations exist (no summary or in addition):
  - Highlights:
    - {top 3 most important observations, concise}

Rules:
- Sort sessions in reverse chronological order (latest first)
- Use only data returned from the API — do not hallucinate or infer missing values
- Keep highlights concise (1 line each)
- Limit to top 3 highlights per session
- If fields are missing, omit them (do not print placeholders)
- Do not include raw JSON in output
- Do not add explanations outside the timeline

Notes:
- {id_short} = first 8 characters of session ID
- Importance for highlights should prioritize higher importance observations if available