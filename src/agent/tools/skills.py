"""Skill loader tool - lets the agent retrieve full skill instructions on demand."""

from pathlib import Path

from strands import tool

from common.logger import logger

SKILLS_DIR = Path(__file__).parent.parent / "skills"


@tool
def load_skill(skill_title: str) -> str:
    """
    Load the full content of a specific skill by its title.

    Call this when you have identified the right skill from the system prompt
    summary and need the complete step-by-step instructions to execute it.

    Args:
        skill_title: The title of the skill to load (as shown in the system prompt).

    Returns:
        Full markdown content of the skill, or an error message if not found.
    """
    for skill_file in sorted(SKILLS_DIR.glob("*.md")):
        try:
            body = skill_file.read_text(encoding="utf-8")
            for line in body.strip().split("\n"):
                stripped = line.strip()
                if stripped.startswith("# "):
                    title = stripped[2:].strip()
                    if title.lower() == skill_title.lower():
                        logger.info(f"[Skills] Loaded: title='{title}'")
                        return body
                    break
        except Exception as e:
            logger.error(f"[Skills] Failed to read: file={skill_file.name} error={e}")

    logger.warning(f"[Skills] Not found: title='{skill_title}'")
    return f"Skill '{skill_title}' not found."
