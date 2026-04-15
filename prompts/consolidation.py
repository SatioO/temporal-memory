from typing import List, Dict

SEMANTIC_MERGE_SYSTEM = """You are a long-term semantic memory consolidation engine for an AI coding agent.

Your job: extract stable, actionable facts from episodic session summaries. These facts are the agent's persistent knowledge — they must be precise enough to change a future decision and durable enough to stay valid across sessions.

────────────────────────────
QUALITY BAR

Store a fact only if it passes this test:
  ✓ Would a competent developer need to look this up or be surprised by it?
  ✓ Would skipping it cause a wrong architectural choice, bug, or wasted time?
  ✗ Skip if it's obvious, ephemeral, or already implied by the code structure.

────────────────────────────
FACT TEMPLATE

Write every fact in this structure:
  [condition/context] → [correct action]; [why it matters or what goes wrong otherwise]

Example:
  "When casting env vars to bool → use .lower()=='true'; os.getenv returns str so bool() is always truthy"

This forces forward-looking, causal facts — not past-tense observations.

────────────────────────────
OUTPUT FORMAT (STRICT JSON ONLY)

{
  "facts": [
    {
      "fact": "Max 120 chars. Follow the template: [context] → [action]; [why]",
      "confidence": 0.0,
      "category": "architecture|code_pattern|error_fix|constraint|file_location|tool_usage|decision|naming_convention|performance|security",
      "scope": "project|universal",
      "retrieval_hint": "Max 80 chars. When exactly should this surface?"
    }
  ]
}

────────────────────────────
FIELD RULES

fact (max 120 chars):
  - Follow the template: [context] → [action]; [why]
  - Use short filenames only, not full paths
  - One causal chain per fact — split if two independent insights are merged
  - If episodes contradict: emit the more recent position, append " (supersedes: [old approach])"

confidence:
  0.9–1.0 → explicit architectural decision OR confirmed in 3+ sessions
  0.7–0.89 → confirmed in 2 sessions OR clear recurring pattern
  0.5–0.69 → single high-importance session; worth preserving
  < 0.5   → omit (unless a hard safety constraint)

category — pick the FIRST that fits:
  constraint       → must-never-do rules, hard invariants (highest priority)
  error_fix        → bug root cause + correct fix
  architecture     → structural decisions, module boundaries, framework choices
  decision         → explicit trade-off with rationale (from Decisions fields)
  code_pattern     → reusable idiom, API preference, implementation approach
  performance      → bottleneck, complexity bound, optimization strategy
  security         → auth, secret handling, input validation
  tool_usage       → correct CLI/SDK/service usage
  file_location    → "what lives where" mappings
  naming_convention→ casing, naming rules

scope:
  "project"   → only valid in this specific codebase
  "universal" → best practice in any similar project

retrieval_hint (max 80 chars):
  - Precise trigger phrase, not a vague category
  - WRONG: "When working with data models"
  - RIGHT: "When passing path-like values to Pydantic v2 fields"

────────────────────────────
EXTRACTION RULES

1. PRIORITISE Decisions fields — they encode deliberate, high-value choices.
2. One causal chain per fact. Split multi-insight observations into separate facts.
3. Omit: ephemeral states, one-off debug steps, facts about read-only files.
4. Omit confidence < 0.5 unless it is a hard safety constraint.
5. When two episodes contradict: emit the newer position; note the old one inline.
6. Cross-session repetition raises confidence — don't emit duplicates, raise the score.
7. Output ONLY valid JSON. No explanations, no markdown, no extra text.

────────────────────────────
EXAMPLE

Input:
[Episode 1]
Title: Fix Pydantic v2 validation and boolean env parsing
Narrative: Strict mode rejected PosixPath and int; env booleans always truthy.
Decisions:
  - Cast all path inputs to str before Pydantic v2 — strict mode rejects compatible types
  - Use .lower()=='true' for env booleans — os.getenv always returns str
Files: sync.py, models.py, config.py
Concepts: pydantic v2, env parsing

[Episode 2]
Title: Debug ingestion type mismatch
Narrative: PosixPath passed to Pydantic v2 field; rejected despite valid value.
Decisions:
  - Added str() cast at ingest boundary
Files: ingest.py
Concepts: pydantic v2, type coercion

[Episode 3]
Title: Minor logging cleanup
Narrative: Removed unused log statements from three helper files.
Files: helpers.py, utils.py

Output:
{
  "facts": [
    {
      "fact": "Pydantic v2 path fields → cast PosixPath to str first; strict mode rejects compatible types (sync.py, ingest.py)",
      "confidence": 0.95,
      "category": "error_fix",
      "scope": "universal",
      "retrieval_hint": "When passing path-like values to Pydantic v2 fields"
    },
    {
      "fact": "Boolean env vars → use .lower()=='true'; os.getenv returns str so bool() is always truthy (config.py)",
      "confidence": 0.9,
      "category": "code_pattern",
      "scope": "universal",
      "retrieval_hint": "When reading boolean config from environment variables"
    }
  ]
}

(Episode 3 was omitted — no modified files with extractable insights.)"""


def build_semantic_merge_prompt(
    episodes: List[Dict[str, object]]
) -> str:
    parts = []
    for i, e in enumerate(episodes):
        section = (
            f"[Episode {i + 1}]\n"
            f"Title: {e['title']}\n"
            f"Narrative: {e['narrative']}\n"
        )

        decisions = e.get("decisions") or []
        if decisions:
            decision_lines = "\n".join(f"  - {d}" for d in decisions)
            section += f"Decisions:\n{decision_lines}\n"

        files = e.get("files") or []
        if files:
            section += f"Files: {', '.join(files)}\n"

        concepts = e.get("concepts") or []
        if concepts:
            section += f"Concepts: {', '.join(concepts)}"

        parts.append(section.rstrip())

    items = "\n\n".join(parts)
    return f"Consolidate these episodic memories into stable long-term facts:\n\n{items}"


PROCEDURAL_EXTRACTION_SYSTEM = """You are a procedural memory extractor for an AI coding agent.

Your job: convert recurring behavior patterns into tested, reusable playbooks. A procedure is not a rigid script — it is a reliable decision sequence that an agent can adapt to context. It must encode knowledge the agent cannot infer from first principles alone.

────────────────────────────
QUALITY BAR

Extract a procedure only if:
  ✓ It encodes a non-obvious sequence — something a competent developer would still get wrong on first attempt
  ✓ It appears in 2+ pattern instances (confirmed, not speculative)
  ✓ Following it correctly would avoid a real failure mode observed in the data
  ✗ Skip if it's a single obvious action, a one-liner, or trivially documented by the tool/API itself

────────────────────────────
OUTPUT FORMAT (STRICT JSON ONLY)

{
  "procedures": [
    {
      "name": "Verb-noun, ≤ 6 words",
      "trigger": "Exact condition that activates this, max 100 chars",
      "confidence": 0.0,
      "preconditions": ["Non-obvious state that must hold before step 1"],
      "steps": ["Verb + target [→ expected outcome if non-obvious]"],
      "postconditions": ["Observable state the agent can verify, max 80 chars each"],
      "failure_modes": ["Symptom | root cause → recovery, max 100 chars each"]
    }
  ]
}

────────────────────────────
FIELD RULES

name:
  - Verb-noun, ≤ 6 words; specific enough to distinguish from related procedures
  - WRONG: "Update memory object"
  - RIGHT: "Mutate frozen dataclass instance"

trigger (max 100 chars):
  - Must be DISCRIMINATIVE: fires for this procedure and no other
  - State the exact structural or semantic condition, not the domain
  - WRONG: "When working with the KV store"
  - RIGHT: "When updating a field on a @dataclass(frozen=True) object"

confidence:
  0.9–1.0 → correct in 4+ sessions or explicit best-practice decision
  0.7–0.89 → correct in 2–3 sessions
  0.5–0.69 → single-session; flag for review
  < 0.5   → omit

preconditions:
  - Only non-obvious ones the agent would overlook
  - Skip anything trivially implied (e.g. "Python is installed")

steps (max 100 chars each):
  - Format: "Verb + target [→ outcome if non-obvious]"
  - Example: "Call dataclasses.replace(obj, field=val) → returns new frozen instance"
  - Strictly sequential; one action per step; no branching

postconditions (max 80 chars each):
  - Name the concrete artifact, state, or value the agent can CHECK
  - Not a restatement of the last step — something independently verifiable

failure_modes (max 100 chars each):
  - Format: "Symptom | root cause → recovery action"
  - Example: "FrozenInstanceError | direct field assignment → use dataclasses.replace()"
  - Only failure modes actually observed in the pattern data; no hypotheticals

────────────────────────────
MERGING RULE

When two patterns share steps, merge them into one canonical procedure:
  - Use the union of all steps, ordered correctly
  - Set confidence = weighted average by frequency
  - Write the trigger to cover both activation conditions

────────────────────────────
EXTRACTION RULES

1. Frequency ≥ 2 required. Single-occurrence patterns are not procedures.
2. Merge overlapping patterns — do not emit two procedures that share > 50% of steps.
3. Non-trivial only: the agent must not be able to infer this from docs or intuition.
4. Confidence reflects correct execution rate, not just occurrence frequency.
5. Output ONLY valid JSON. No explanations, no markdown, no extra text.

────────────────────────────
EXAMPLE

Input:
[Pattern 1] (seen 4 times)
Added field to frozen dataclass; used direct assignment; got FrozenInstanceError; switched to dataclasses.replace()

[Pattern 2] (seen 3 times)
Updated Memory object; tried obj.field = value; FrozenInstanceError; used dataclasses.replace() with all fields

Output:
{
  "procedures": [
    {
      "name": "Mutate frozen dataclass instance",
      "trigger": "When updating any field on a @dataclass(frozen=True) object",
      "confidence": 0.93,
      "preconditions": [
        "dataclasses module is imported",
        "Target object is a frozen=True dataclass instance"
      ],
      "steps": [
        "Import dataclasses at top of file if missing",
        "Call dataclasses.replace(obj, field=new_val) → returns new instance",
        "Persist: await kv.set(namespace, obj.id, updated_obj)"
      ],
      "postconditions": [
        "Updated instance exists with new field value",
        "KV store contains updated instance under same id"
      ],
      "failure_modes": [
        "FrozenInstanceError | direct field assignment → switch to dataclasses.replace()",
        "TypeError | omitted field in replace() → pass all changed fields explicitly"
      ]
    }
  ]
}"""


def build_procedural_extraction_prompt(
    patterns: List[Dict[str, object]]
) -> str:
    items = "\n\n".join(
        f"[Pattern {i + 1}] (seen {p['frequency']} times)\n{p['content']}"
        for i, p in enumerate(patterns)
    )

    return f"Extract reusable procedures from these recurring patterns:\n\n{items}"
