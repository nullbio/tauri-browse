"""Tests for the tauri-browse skill file structure and content consistency."""

import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).parent.parent / "skills" / "tauri-browse"
SKILL_MD = SKILL_DIR / "SKILL.md"
COMMANDS_MD = SKILL_DIR / "references" / "commands.md"
SNAPSHOT_REFS_MD = SKILL_DIR / "references" / "snapshot-refs.md"
SESSION_MD = SKILL_DIR / "references" / "session-management.md"
AUTH_MD = SKILL_DIR / "references" / "authentication.md"


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

    def test_commands_reference_exists(self):
        assert COMMANDS_MD.exists()

    def test_snapshot_refs_reference_exists(self):
        assert SNAPSHOT_REFS_MD.exists()

    def test_session_management_reference_exists(self):
        assert SESSION_MD.exists()

    def test_authentication_reference_exists(self):
        assert AUTH_MD.exists()

    def test_templates_exist(self):
        templates = SKILL_DIR / "templates"
        assert (templates / "form-automation.sh").exists()
        assert (templates / "authenticated-session.sh").exists()
        assert (templates / "capture-workflow.sh").exists()


class TestSkillFrontmatter:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = read_skill_file(SKILL_MD)
        self.fm = parse_frontmatter(self.content)

    def test_has_name(self):
        assert self.fm.get("name") == "tauri-browse"

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

    def test_references_commands(self):
        assert "references/commands.md" in self.content

    def test_references_snapshot_refs(self):
        assert "references/snapshot-refs.md" in self.content

    def test_references_session_management(self):
        assert "references/session-management.md" in self.content

    def test_references_authentication(self):
        assert "references/authentication.md" in self.content

    def test_referenced_files_exist(self):
        refs = re.findall(
            r"\[.*?\]\((references/.*?\.md|templates/.*?\.(?:md|sh))\)", self.content
        )
        assert len(refs) > 0
        for ref in refs:
            full_path = SKILL_DIR / ref
            assert full_path.exists(), f"Missing: {ref}"

    def test_no_agent_browser_references(self):
        assert "agent-browser" not in self.content


class TestCommandsReference:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = read_skill_file(COMMANDS_MD)

    def test_has_navigation_section(self):
        assert "## Navigation" in self.content

    def test_has_snapshot_section(self):
        assert "## Snapshot" in self.content

    def test_has_interactions_section(self):
        assert "## Interactions" in self.content

    def test_has_screenshot_section(self):
        assert "## Screenshots" in self.content

    def test_has_wait_section(self):
        assert "## Wait" in self.content

    def test_uses_tauri_browse_command(self):
        assert "tauri-browse" in self.content

    def test_no_agent_browser_references(self):
        assert "agent-browser" not in self.content

    def test_documents_launch_command(self):
        assert "tauri-browse launch" in self.content

    def test_documents_environment_variables(self):
        assert "TAURI_BROWSE_" in self.content


class TestSnapshotRefsReference:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = read_skill_file(SNAPSHOT_REFS_MD)

    def test_has_ref_lifecycle(self):
        assert "## Ref Lifecycle" in self.content

    def test_has_best_practices(self):
        assert "## Best Practices" in self.content

    def test_no_agent_browser_references(self):
        assert "agent-browser" not in self.content


class TestSessionManagementReference:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = read_skill_file(SESSION_MD)

    def test_has_named_sessions(self):
        assert "## Named Sessions" in self.content

    def test_has_state_persistence(self):
        assert "## Session State Persistence" in self.content

    def test_no_agent_browser_references(self):
        assert "agent-browser" not in self.content


class TestAuthenticationReference:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.content = read_skill_file(AUTH_MD)

    def test_has_basic_login(self):
        assert "## Basic Login Flow" in self.content

    def test_has_state_saving(self):
        assert "## Saving Authentication State" in self.content

    def test_no_agent_browser_references(self):
        assert "agent-browser" not in self.content


class TestNoVideoReferences:
    """Verify video recording content was removed from all skills."""

    def test_tauri_browse_skill_no_video(self):
        content = read_skill_file(SKILL_MD)
        assert "record start" not in content
        assert "record stop" not in content
        assert ".webm" not in content

    def test_commands_no_video(self):
        content = read_skill_file(COMMANDS_MD)
        assert "## Video Recording" not in content
        assert "record start" not in content

    def test_dogfood_skill_no_video(self):
        dogfood_skill = (
            Path(__file__).parent.parent / "skills" / "tauri-dogfood" / "SKILL.md"
        )
        content = read_skill_file(dogfood_skill)
        assert "record start" not in content
        assert "record stop" not in content
        assert ".webm" not in content
        assert "Repro Video" not in content
