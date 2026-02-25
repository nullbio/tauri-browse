"""Tests for the tauri-dogfood skill file structure and content consistency."""

import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).parent.parent / "skills" / "tauri-dogfood"
SKILL_MD = SKILL_DIR / "SKILL.md"
TAXONOMY_MD = SKILL_DIR / "references" / "issue-taxonomy.md"
TEMPLATE_MD = SKILL_DIR / "templates" / "dogfood-report-template.md"


def read_skill_file(path: Path) -> str:
    return path.read_text()


def parse_frontmatter(content: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).split("\n"):
        colon = line.find(":")
        if colon > 0:
            fields[line[:colon].strip()] = line[colon + 1 :].strip()
    return fields


class TestFileStructure:
    def test_skill_md_exists(self):
        assert SKILL_MD.exists()

    def test_taxonomy_exists(self):
        assert TAXONOMY_MD.exists()

    def test_template_exists(self):
        assert TEMPLATE_MD.exists()


class TestSkillFrontmatter:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = read_skill_file(SKILL_MD)
        self.fm = parse_frontmatter(self.content)

    def test_has_name(self):
        assert self.fm.get("name") == "tauri-dogfood"

    def test_has_description(self):
        assert self.fm.get("description")
        assert len(self.fm["description"]) > 50

    def test_has_allowed_tools(self):
        assert self.fm.get("allowed-tools")
        assert "tauri-browse" in self.fm["allowed-tools"]


class TestSkillBodyReferences:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = read_skill_file(SKILL_MD)

    def test_references_taxonomy(self):
        assert "references/issue-taxonomy.md" in self.content

    def test_references_template(self):
        assert "templates/dogfood-report-template.md" in self.content

    def test_referenced_files_exist(self):
        refs = re.findall(
            r"\[.*?\]\((references/.*?\.md|templates/.*?\.md)\)", self.content
        )
        assert len(refs) > 0
        for ref in refs:
            full_path = SKILL_DIR / ref
            assert full_path.exists(), f"Missing: {ref}"


class TestReportTemplate:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.template = read_skill_file(TEMPLATE_MD)

    def test_has_issue_prefix(self):
        assert "ISSUE-" in self.template

    def test_has_severity_field(self):
        assert "**Severity**" in self.template

    def test_has_category_field(self):
        assert "**Category**" in self.template

    def test_has_url_field(self):
        assert "**URL**" in self.template

    def test_has_repro_steps(self):
        assert "**Repro Steps**" in self.template

    def test_has_screenshot_refs(self):
        assert re.search(r"!\[.*?\]\(screenshots/", self.template)

    def test_lists_all_severity_values(self):
        assert re.search(r"critical\s*/\s*high\s*/\s*medium\s*/\s*low", self.template)

    def test_lists_all_category_values(self):
        category_line = next(
            (l for l in self.template.split("\n") if "**Category**" in l), None
        )
        assert category_line
        for cat in [
            "visual",
            "functional",
            "ux",
            "content",
            "performance",
            "console",
            "accessibility",
        ]:
            assert cat in category_line.lower()

    def test_has_summary_table(self):
        assert "## Summary" in self.template
        for sev in ["Critical", "High", "Medium", "Low", "Total"]:
            assert sev in self.template


class TestIssueTaxonomy:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.taxonomy = read_skill_file(TAXONOMY_MD)

    def test_has_severity_definitions(self):
        assert "## Severity Levels" in self.taxonomy
        for sev in ["critical", "high", "medium", "low"]:
            assert f"**{sev}**" in self.taxonomy.lower()

    def test_has_all_category_sections(self):
        expected = [
            "Visual",
            "Functional",
            "UX",
            "Content",
            "Performance",
            "Console",
            "Accessibility",
        ]
        for cat in expected:
            assert re.search(rf"###\s+.*{cat}", self.taxonomy, re.IGNORECASE)

    def test_has_exploration_checklist(self):
        assert "## Exploration Checklist" in self.taxonomy

    def test_checklist_has_numbered_items(self):
        checklist = self.taxonomy.split("## Exploration Checklist")[1]
        numbered = re.findall(r"^\d+\.", checklist, re.MULTILINE)
        assert len(numbered) >= 5


class TestCrossConsistency:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.template = read_skill_file(TEMPLATE_MD)
        self.taxonomy = read_skill_file(TAXONOMY_MD)

    def test_every_template_category_in_taxonomy(self):
        category_line = next(
            (l for l in self.template.split("\n") if "**Category**" in l), None
        )
        assert category_line
        categories = [
            c.strip().lower()
            for c in category_line.split("|")[-1].split("/")
            if c.strip()
        ]
        for cat in categories:
            assert re.search(
                rf"###\s+.*{cat}", self.taxonomy, re.IGNORECASE
            ), f'Category "{cat}" from template not found in taxonomy'

    def test_every_template_severity_in_taxonomy(self):
        for sev in ["critical", "high", "medium", "low"]:
            assert f"**{sev}**" in self.taxonomy.lower()
