from typing import List, Dict
SEMANTIC_MERGE_SYSTEM = """You are a memory consolidation engine. Given overlapping episodic memories(session summaries), extract stable factual knowledge.

Output format (STRICT JSON ONLY):
{
  "facts": [
    {
      "fact": "Concise factual statement",
      "confidence": 0.0
    }
  ]
}

Rules:
- Output ONLY valid JSON. No extra text, no explanations, no markdown.
- "confidence" must be a number between 0.0 and 1.0
- If uncertain or conflicting, lower the confidence score
- Extract only facts that appear in 2 + episodes or are highly confident
- Confidence reflects how well-supported the fact is across episodes
- Combine overlapping information into single concise facts
- Skip ephemeral details(specific error messages, temporary states)"""


def build_semantic_merge_prompt(
    episodes: List[Dict[str, object]]
) -> str:
    items = "\n\n".join(
        f"[Episode {i + 1}]\n"
        f"Title: {e['title']}\n"
        f"Narrative: {e['narrative']}\n"
        f"Concepts: {', '.join(e['concepts'])}"
        for i, e in enumerate(episodes)
    )

    return f"Consolidate these episodic memories into stable facts:\n\n{items}"


PROCEDURAL_EXTRACTION_SYSTEM = """You are a procedural memory extractor. Given recurring behaviour patterns from an AI coding agent, extract reusable step-by-step procedures.

Output format (STRICT JSON ONLY):
{
  "procedures": [
    {
      "name": "Short procedure name",
      "trigger": "When this procedure should be used",
      "steps": ["First step", "Second step"]
    }
  ]
}

Rules:
- Output ONLY valid JSON. No extra text, no explanations, no markdown.
- Each procedure must have a clear, concise name and a trigger condition.
- Steps must be concrete and actionable.
- Extract only procedures that appear in multiple patterns.
- Combine overlapping patterns into a single procedure."""


def build_procedural_extraction_prompt(
    patterns: List[Dict[str, object]]
) -> str:
    items = "\n\n".join(
        f"[Pattern {i + 1}] (seen {p['frequency']} times)\n{p['content']}"
        for i, p in enumerate(patterns)
    )

    return f"Extract reusable procedures from these recurring patterns:\n\n{items}"
