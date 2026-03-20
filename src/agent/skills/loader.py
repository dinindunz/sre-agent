"""Skills loader for the SRE agent.

Provides load_skills_summary() which scans local skill files and returns a
high-level summary (title + description) for injection into the system prompt
at startup. The load_skill tool lives in tools/skills.py.
"""

from pathlib import Path

from common.logger import logger

# Skills are stored as .md files in the skills/ directory
SKILLS_DIR = Path(__file__).parent


def load_skills_summary() -> str:
    """
    Load a high-level summary of all available skills for the system prompt.

    Scans the skills directory for markdown files, extracts titles (first H1)
    and descriptions (first non-heading line after the title), and formats
    them as a bulleted list.

    Returns:
        Formatted skills section string, or empty string if no skills found.
    """
    skill_files = sorted(SKILLS_DIR.glob("*.md"))

    if not skill_files:
        logger.info("[Skills] No skill files found in skills directory")
        return ""

    lines = []
    for skill_file in skill_files:
        try:
            body = skill_file.read_text(encoding="utf-8")

            title = ""
            description = ""
            for line in body.strip().split("\n"):
                stripped = line.strip()
                if stripped.startswith("# ") and not title:
                    title = stripped[2:].strip()
                elif title and stripped and not stripped.startswith("#"):
                    description = stripped
                    break

            if title:
                lines.append(f"- **{title}**: {description}")
                logger.debug(f"[Skills] Loaded summary: title='{title}'")
            else:
                logger.debug(f"[Skills] Skipped (no title): file={skill_file.name}")

        except Exception as e:
            logger.error(f"[Skills] Failed to read: file={skill_file.name} error={e}")

    if not lines:
        logger.info("[Skills] No valid skill definitions found")
        return ""

    logger.info(f"[Skills] Summary built: count={len(lines)}")
    return (
        "\n\n## Available Skills\n"
        "When a user's request matches a skill, use the load_skill tool to retrieve "
        "the full instructions, then follow them.\n\n" + "\n".join(lines)
    )
