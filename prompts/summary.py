from schema.domain import CompressedObservation


SUMMARY_SYSTEM_PROMPT = """You are a session summarizer for an AI coding agent's memory system. Given all compressed observations from a coding session, produce a concise session summary.

Output EXACTLY this XML format with no additional text:

<summary>
  <title>Short session title (max 100 chars)</title>
  <narrative>3-5 sentence narrative of what was accomplished</narrative>
  <decisions>
    <decision>Key technical decision made</decision>
  </decisions>
  <files>
    <file>path/to/modified/file</file>
  </files>
  <concepts>
    <concept>key concept from session</concept>
  </concepts>
</summary>

Rules:
- Focus on outcomes, not individual tool calls
- Highlight decisions and their rationale
- List all files that were created or modified
- Concepts should be searchable terms for future context retrieval
"""


def build_summary_prompt(observations: list[CompressedObservation]) -> str:
    """
      example:
      Session observations (2 total):
      [1] Bug: Pydantic validation failure
      Validation is failing due to strict typing in Pydantic v2.
      Facts:
        - Path was passed as PosixPath
        - Lines field received integer instead of string
      Files: sync.py, models.py

      ---

      [2] Improvement: Environment variable parsing
      Current implementation may incorrectly enable features.
      Facts:
        - os.getenv returns string
        - Boolean flags need explicit parsing
      Files: config.py
    """
    lines = []

    for i, obs in enumerate(observations):
        facts = "\n".join(f"  - {f}" for f in obs["facts"])

        line = (
            f"[{i + 1}] {obs['type']}: {obs['title']}\n"
            f"{obs['narrative']}\n"
            f"Facts:\n{facts}\n"
            f"Files: {', '.join(obs['files'])}"
        )

        lines.append(line)

    return (
        f"Session observations ({len(observations)} total):\n\n"
        + "\n\n---\n\n".join(lines)
    )
