"""Phase 23 - Skill Registry checks."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

REQUIRED_SKILLS = [
    "aureum-project-context",
    "aureum-editorial-style",
    "aureum-news-engine",
    "aureum-chart-store",
    "aureum-technical-decision",
    "aureum-data-preflight",
    "aureum-gold-macro",
    "aureum-geopolitical-oil",
    "aureum-risk-manager",
    "aureum-scenario-orchestrator",
    "aureum-trade-quality-gate",
    "aureum-replay-shadow-terminal",
    "aureum-elliott-wave",
]

REQUIRED_SECTIONS = [
    "### Role",
    "### Inputs",
    "### Outputs",
    "### Methodologie",
    "### Limites",
    "### Bons exemples",
    "### Mauvais exemples",
]


class SkillRegistryTests(unittest.TestCase):
    def test_required_phase_23_skills_exist(self) -> None:
        for skill_name in REQUIRED_SKILLS:
            path = SKILLS_DIR / skill_name / "SKILL.md"
            self.assertTrue(path.exists(), f"Missing skill file: {path}")

    def test_required_phase_23_skills_have_contract_sections(self) -> None:
        for skill_name in REQUIRED_SKILLS:
            path = SKILLS_DIR / skill_name / "SKILL.md"
            text = path.read_text(encoding="utf-8")
            self.assertIn("name:", text, skill_name)
            self.assertIn("description:", text, skill_name)
            self.assertIn("## Phase 23 Contract", text, skill_name)
            for section in REQUIRED_SECTIONS:
                self.assertIn(section, text, f"{skill_name} missing {section}")


if __name__ == "__main__":
    unittest.main()
