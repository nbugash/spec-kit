"""Tests for the architecture and design plan-phase artifact templates.

These templates back the Phase 2 artifacts (``architecture.md`` and ``design.md``)
that the plan command produces. Their required section sets are fixed by design, so
they are asserted here to guard against silent drift.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.conftest import requires_bash
from tests.parity_helpers import (
    HAS_POWERSHELL,
    PROJECT_ROOT,
    bash_cmd,
    install_scripts,
    json_stdout,
    make_repo,
    ps_cmd,
    py_cmd,
    run,
    write_feature_json,
)

TEMPLATES_DIR = PROJECT_ROOT / "templates"
COMMANDS_DIR = TEMPLATES_DIR / "commands"

ARCHITECTURE_TEMPLATE = "architecture-template"

# Every section is required on every run. A section that does not apply is filled
# with "N/A - <reason>" rather than deleted, so absence here is a real regression.
ARCHITECTURE_SECTIONS = (
    "Architectural Overview",
    "System Context",
    "Component Architecture",
    "Deployment Topology",
    "Data Flow",
    "Cross-Cutting Concerns",
    "Architectural Decisions",
    "Phase 1 Reconciliation",
)

# Context, component, deployment and data flow each carry a diagram.
ARCHITECTURE_MIN_DIAGRAMS = 4

DESIGN_TEMPLATE = "design-template"

DESIGN_SECTIONS = (
    "Module & File Layout",
    "Class & Interface Model",
    "Interface Contracts",
    "Sequence Diagrams",
    "State Model",
    "Error Handling & Validation",
    "Persistence Mapping",
)

# classDiagram, sequenceDiagram and stateDiagram-v2 each carry a diagram.
DESIGN_MIN_DIAGRAMS = 3


def _template_text(name: str) -> str:
    return (TEMPLATES_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_architecture_template_is_shipped() -> None:
    assert (TEMPLATES_DIR / f"{ARCHITECTURE_TEMPLATE}.md").is_file()


@pytest.mark.parametrize("section", ARCHITECTURE_SECTIONS)
def test_architecture_template_declares_required_section(section: str) -> None:
    assert f"## {section}" in _template_text(ARCHITECTURE_TEMPLATE)


def test_architecture_template_header_carries_provenance_fields() -> None:
    text = _template_text(ARCHITECTURE_TEMPLATE)
    for field in ("**Branch**", "**Date**", "**Input**"):
        assert field in text


def test_architecture_template_states_not_applicable_rule() -> None:
    """The fixed section set is only honest if inapplicable sections say so."""
    assert "N/A" in _template_text(ARCHITECTURE_TEMPLATE)


def test_architecture_template_uses_mermaid_diagrams() -> None:
    text = _template_text(ARCHITECTURE_TEMPLATE)
    assert text.count("```mermaid") >= ARCHITECTURE_MIN_DIAGRAMS


def test_architecture_template_defers_research_rationale() -> None:
    """Decisions are referenced from research.md, never restated here."""
    assert "research.md" in _template_text(ARCHITECTURE_TEMPLATE)


@requires_bash
def test_architecture_template_resolves_in_all_variants(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    install_scripts(repo, "resolve-template")
    templates = repo / ".specify" / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        TEMPLATES_DIR / f"{ARCHITECTURE_TEMPLATE}.md",
        templates / f"{ARCHITECTURE_TEMPLATE}.md",
    )

    commands = [
        bash_cmd(repo, "resolve-template", ARCHITECTURE_TEMPLATE, "--json"),
        py_cmd(repo, "resolve-template", ARCHITECTURE_TEMPLATE, "--json"),
    ]
    if HAS_POWERSHELL:
        commands.append(ps_cmd(repo, "resolve-template", ARCHITECTURE_TEMPLATE, "-Json"))

    for command in commands:
        result = run(command, repo)
        assert result.returncode == 0, result.stderr
        payload = json_stdout(result)
        assert isinstance(payload, dict)
        assert payload["TEMPLATE_NAME"] == ARCHITECTURE_TEMPLATE
        assert "Phase 1 Reconciliation" in payload["TEMPLATE_CONTENT"]


def test_design_template_is_shipped() -> None:
    assert (TEMPLATES_DIR / f"{DESIGN_TEMPLATE}.md").is_file()


@pytest.mark.parametrize("section", DESIGN_SECTIONS)
def test_design_template_declares_required_section(section: str) -> None:
    assert f"## {section}" in _template_text(DESIGN_TEMPLATE)


def test_design_template_header_carries_provenance_fields() -> None:
    text = _template_text(DESIGN_TEMPLATE)
    for field in ("**Branch**", "**Date**", "**Input**"):
        assert field in text


def test_design_template_states_not_applicable_rule() -> None:
    assert "N/A" in _template_text(DESIGN_TEMPLATE)


def test_design_template_uses_mermaid_diagrams() -> None:
    text = _template_text(DESIGN_TEMPLATE)
    assert text.count("```mermaid") >= DESIGN_MIN_DIAGRAMS


@pytest.mark.parametrize(
    "diagram", ("classDiagram", "sequenceDiagram", "stateDiagram-v2")
)
def test_design_template_uses_expected_diagram_kinds(diagram: str) -> None:
    assert diagram in _template_text(DESIGN_TEMPLATE)


def test_design_template_forbids_implementation_bodies() -> None:
    """Interface sections carry signatures only; bodies belong to implementation."""
    text = _template_text(DESIGN_TEMPLATE).lower()
    assert "signature" in text
    assert "no implementation bodies" in text


def test_design_template_links_rather_than_copies_entities() -> None:
    """Persistence Mapping links data-model.md; duplicating fields would drift."""
    assert "data-model.md" in _template_text(DESIGN_TEMPLATE)


@requires_bash
def test_design_template_resolves_in_all_variants(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    install_scripts(repo, "resolve-template")
    templates = repo / ".specify" / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        TEMPLATES_DIR / f"{DESIGN_TEMPLATE}.md", templates / f"{DESIGN_TEMPLATE}.md"
    )

    commands = [
        bash_cmd(repo, "resolve-template", DESIGN_TEMPLATE, "--json"),
        py_cmd(repo, "resolve-template", DESIGN_TEMPLATE, "--json"),
    ]
    if HAS_POWERSHELL:
        commands.append(ps_cmd(repo, "resolve-template", DESIGN_TEMPLATE, "-Json"))

    for command in commands:
        result = run(command, repo)
        assert result.returncode == 0, result.stderr
        payload = json_stdout(result)
        assert isinstance(payload, dict)
        assert payload["TEMPLATE_NAME"] == DESIGN_TEMPLATE
        assert "Persistence Mapping" in payload["TEMPLATE_CONTENT"]


# ---------------------------------------------------------------------------
# Override stack
# ---------------------------------------------------------------------------
#
# This is the feature's one silent failure mode. Reading
# `.specify/templates/<name>.md` directly still loads a template and still
# generates artifacts, while bypassing every project override, preset and
# extension. Only a test that plants an override and looks for it can tell the
# two apart.

_OVERRIDE_MARKER = "# OVERRIDE MARKER — project-specific structure\n"


def _setup_plan_repo(tmp_path: Path, name: str) -> Path:
    repo = make_repo(tmp_path, name)
    install_scripts(repo, "setup-plan")
    write_feature_json(repo)
    (repo / "specs" / "001-my-feature").mkdir(parents=True)
    templates = repo / ".specify" / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")
    for template in (ARCHITECTURE_TEMPLATE, DESIGN_TEMPLATE):
        shutil.copy(TEMPLATES_DIR / f"{template}.md", templates / f"{template}.md")
    return repo


@requires_bash
@pytest.mark.parametrize(
    "template,key",
    [
        (ARCHITECTURE_TEMPLATE, "ARCHITECTURE_TEMPLATE_CONTENT"),
        (DESIGN_TEMPLATE, "DESIGN_TEMPLATE_CONTENT"),
    ],
)
def test_project_override_reaches_the_plan_command(
    tmp_path: Path, template: str, key: str
) -> None:
    """A project override must win over the core template, in every variant."""
    repos = {
        "bash": _setup_plan_repo(tmp_path, f"bash-{template}"),
        "python": _setup_plan_repo(tmp_path, f"python-{template}"),
    }
    if HAS_POWERSHELL:
        repos["powershell"] = _setup_plan_repo(tmp_path, f"ps-{template}")

    for repo in repos.values():
        overrides = repo / ".specify" / "templates" / "overrides"
        overrides.mkdir(parents=True, exist_ok=True)
        (overrides / f"{template}.md").write_text(_OVERRIDE_MARKER, encoding="utf-8")

    commands = {
        "bash": bash_cmd(repos["bash"], "setup-plan", "--json"),
        "python": py_cmd(repos["python"], "setup-plan", "--json"),
    }
    if HAS_POWERSHELL:
        commands["powershell"] = ps_cmd(repos["powershell"], "setup-plan", "-Json")

    for variant, command in commands.items():
        result = run(command, repos[variant])
        assert result.returncode == 0, f"{variant}: {result.stderr}"
        payload = json_stdout(result)
        assert isinstance(payload, dict)
        assert _OVERRIDE_MARKER.strip() in payload[key], (
            f"{variant} bypassed the override stack for {template}"
        )


# ---------------------------------------------------------------------------
# Consumer wiring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ("tasks", "implement"))
@pytest.mark.parametrize("artifact", ("architecture.md", "design.md"))
def test_downstream_commands_consume_design_artifacts(
    command: str, artifact: str
) -> None:
    text = (COMMANDS_DIR / f"{command}.md").read_text(encoding="utf-8")
    assert artifact in text


@pytest.mark.parametrize("artifact", ("architecture.md", "design.md"))
def test_analyze_command_does_not_load_design_artifacts(artifact: str) -> None:
    """FR-014: analyze loads only spec/plan/tasks by design.

    The analyze command states an explicit "progressive disclosure - don't dump
    all content into analysis" rule. Adding these artifacts to its context would
    contradict that, so the exclusion is asserted rather than left to convention.
    """
    text = (COMMANDS_DIR / "analyze.md").read_text(encoding="utf-8")
    assert artifact not in text
