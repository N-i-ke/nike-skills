"""Tests for scripts/nike.py.

Pure functions are unit-tested by direct import. Subcommands are
integration-tested by invoking nike.py as a subprocess against a
temporary working directory, since nike.py uses Path.cwd() at module
load to determine the project root.

Run from the repository root:
    python3 -m unittest discover -s scripts/tests -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).parent.parent
NIKE_PY = SCRIPTS_DIR / "nike.py"

sys.path.insert(0, str(SCRIPTS_DIR))
import nike  # type: ignore  # noqa: E402


def run_nike(*args: str, cwd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(NIKE_PY), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestParseRequirements(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(nike.parse_requirements_md(""), [])

    def test_no_fr_section(self) -> None:
        text = "# Title\n\nSome content but no functional requirements section."
        self.assertEqual(nike.parse_requirements_md(text), [])

    def test_single_fr_single_ac(self) -> None:
        text = (
            "## 4. 機能要件\n"
            "### FR-01: ログイン\n"
            "**説明**: メールでログイン\n"
            "\n"
            "**受け入れ基準**:\n"
            "- Given 登録済みユーザー, When 正しい資格情報入力, Then 成功\n"
            "\n"
        )
        result = nike.parse_requirements_md(text)
        self.assertEqual(len(result), 1)
        fr = result[0]
        self.assertEqual(fr["id"], "FR-01")
        self.assertEqual(fr["name"], "ログイン")
        self.assertEqual(fr["description"], "メールでログイン")
        self.assertEqual(len(fr["acceptance_criteria"]), 1)
        ac = fr["acceptance_criteria"][0]
        self.assertEqual(ac["id"], "FR-01-AC1")
        self.assertEqual(ac["given"], "登録済みユーザー")
        self.assertEqual(ac["when"], "正しい資格情報入力")
        self.assertEqual(ac["then"], "成功")

    def test_multiple_fr_multiple_ac(self) -> None:
        text = (
            "## 4. 機能要件\n"
            "### FR-01: ログイン\n"
            "**説明**: ログイン\n"
            "\n"
            "**受け入れ基準**:\n"
            "- Given A, When B, Then C\n"
            "- Given D, When E, Then F\n"
            "\n"
            "### FR-02: ログアウト\n"
            "**説明**: ログアウト\n"
            "\n"
            "**受け入れ基準**:\n"
            "- Given G, When H, Then I\n"
            "\n"
        )
        result = nike.parse_requirements_md(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]["acceptance_criteria"]), 2)
        self.assertEqual(result[0]["acceptance_criteria"][1]["id"], "FR-01-AC2")
        self.assertEqual(len(result[1]["acceptance_criteria"]), 1)
        self.assertEqual(result[1]["id"], "FR-02")

    def test_japanese_full_width_commas(self) -> None:
        text = (
            "## 4. 機能要件\n"
            "### FR-01: テスト\n"
            "**説明**: テスト\n"
            "\n"
            "**受け入れ基準**:\n"
            "- Given 状態，When 操作，Then 結果\n"
            "- Given 状態、When 操作、Then 結果\n"
            "\n"
        )
        result = nike.parse_requirements_md(text)
        self.assertEqual(len(result[0]["acceptance_criteria"]), 2)

    def test_strips_trailing_period(self) -> None:
        text = (
            "## 4. 機能要件\n"
            "### FR-01: テスト\n"
            "**説明**: テスト\n"
            "\n"
            "**受け入れ基準**:\n"
            "- Given X, When Y, Then Z.\n"
            "\n"
        )
        result = nike.parse_requirements_md(text)
        self.assertEqual(result[0]["acceptance_criteria"][0]["then"], "Z")


class TestRenderTemplate(unittest.TestCase):
    def test_substitutes_vars(self) -> None:
        result = nike.render_template(
            "requirements.md", FEATURE_NAME="テスト機能", DATE="2026-01-01"
        )
        self.assertIn("テスト機能", result)
        self.assertIn("2026-01-01", result)
        # Placeholders should not remain
        self.assertNotIn("{{FEATURE_NAME}}", result)
        self.assertNotIn("{{DATE}}", result)


# ---------------------------------------------------------------------------
# Subcommand integration tests
# ---------------------------------------------------------------------------


class TestNikeInit(unittest.TestCase):
    def test_creates_three_templates(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike("init", "user-auth", "--name", "ユーザー認証", cwd=td)
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["slug"], "user-auth")
            self.assertEqual(data["name"], "ユーザー認証")
            for fname in ("requirements.md", "basic-design.md", "detailed-design.md"):
                p = Path(td, "docs", "design", "user-auth", fname)
                self.assertTrue(p.exists(), f"{p} should exist")

    def test_skip_existing_without_force(self) -> None:
        with TemporaryDirectory() as td:
            run_nike("init", "x", cwd=td)
            r = run_nike("init", "x", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["files"]["requirements.md"], "skipped")

    def test_force_overwrites(self) -> None:
        with TemporaryDirectory() as td:
            run_nike("init", "x", cwd=td)
            # Modify file to detect overwrite
            req = Path(td, "docs/design/x/requirements.md")
            req.write_text("MODIFIED", encoding="utf-8")
            r = run_nike("init", "x", "--force", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["files"]["requirements.md"], "created")
            self.assertNotEqual(req.read_text(encoding="utf-8"), "MODIFIED")


class TestNikeStatus(unittest.TestCase):
    def test_no_design_dir(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike("status", cwd=td)
            data = json.loads(r.stdout)
            self.assertFalse(data["exists"])
            self.assertEqual(data["features"], [])

    def test_lists_features(self) -> None:
        with TemporaryDirectory() as td:
            run_nike("init", "feat-a", cwd=td)
            r = run_nike("status", cwd=td)
            data = json.loads(r.stdout)
            self.assertTrue(data["exists"])
            self.assertEqual(len(data["features"]), 1)
            f = data["features"][0]
            self.assertEqual(f["slug"], "feat-a")
            self.assertEqual(f["phases"]["design"], "complete")
            self.assertEqual(f["phases"]["implementation"], "none")
            self.assertEqual(f["phases"]["verification"], "none")


class TestNikeImplInit(unittest.TestCase):
    def test_seeds_tasks_from_requirements(self) -> None:
        with TemporaryDirectory() as td:
            run_nike("init", "feat-a", cwd=td)
            Path(td, "docs/design/feat-a/requirements.md").write_text(
                "# 要件定義: feat-a\n"
                "\n"
                "## 4. 機能要件\n"
                "### FR-01: A\n"
                "**説明**: A\n"
                "\n"
                "**受け入れ基準**:\n"
                "- Given X, When Y, Then Z\n"
                "\n"
                "### FR-02: B\n"
                "**説明**: B\n"
                "\n"
                "**受け入れ基準**:\n"
                "- Given P, When Q, Then R\n"
                "\n",
                encoding="utf-8",
            )
            r = run_nike("impl-init", "feat-a", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "created")
            self.assertEqual(data["tasks_seeded"], 2)
            log = Path(td, "docs/design/feat-a/implementation-log.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("- [ ] FR-01: A", log)
            self.assertIn("- [ ] FR-02: B", log)

    def test_errors_when_feature_missing(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike("impl-init", "ghost", cwd=td)
            self.assertEqual(r.returncode, 1)
            data = json.loads(r.stdout)
            self.assertIn("error", data)


class TestNikeVerifyInit(unittest.TestCase):
    def test_seeds_ac_table(self) -> None:
        with TemporaryDirectory() as td:
            run_nike("init", "feat-a", cwd=td)
            Path(td, "docs/design/feat-a/requirements.md").write_text(
                "# 要件定義: feat-a\n"
                "\n"
                "## 4. 機能要件\n"
                "### FR-01: A\n"
                "**説明**: A\n"
                "\n"
                "**受け入れ基準**:\n"
                "- Given X, When Y, Then Z\n"
                "- Given P, When Q, Then R\n"
                "\n",
                encoding="utf-8",
            )
            r = run_nike("verify-init", "feat-a", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["acceptance_criteria_seeded"], 2)
            report = Path(
                td, "docs/design/feat-a/verification-report.md"
            ).read_text(encoding="utf-8")
            self.assertIn("FR-01-AC1", report)
            self.assertIn("FR-01-AC2", report)
            self.assertIn("NOT_VERIFIED", report)


class TestNikeInvestigateInit(unittest.TestCase):
    def test_creates_bug_report(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike(
                "investigate-init",
                "bug-1",
                "--type",
                "bug",
                "--title",
                "テストバグ",
                cwd=td,
            )
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "created")
            self.assertEqual(data["type"], "bug")
            report = Path(td, "docs/investigations/bug-1/report.md")
            self.assertTrue(report.exists())
            self.assertIn("テストバグ", report.read_text(encoding="utf-8"))

    def test_creates_security_report(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike(
                "investigate-init", "vuln-1", "--type", "security", cwd=td
            )
            data = json.loads(r.stdout)
            self.assertEqual(data["type"], "security")
            self.assertIn(
                "種別: security",
                Path(td, "docs/investigations/vuln-1/report.md").read_text(
                    encoding="utf-8"
                ),
            )


class TestNikeDetect(unittest.TestCase):
    def test_no_project(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike("detect", cwd=td)
            data = json.loads(r.stdout)
            self.assertIsNone(data["language"])
            self.assertEqual(data["commands"], {})

    def test_node_project_with_pnpm(self) -> None:
        with TemporaryDirectory() as td:
            Path(td, "package.json").write_text(
                json.dumps(
                    {
                        "name": "x",
                        "scripts": {
                            "test": "vitest",
                            "lint": "eslint .",
                            "typecheck": "tsc --noEmit",
                        },
                    }
                ),
                encoding="utf-8",
            )
            Path(td, "pnpm-lock.yaml").write_text("", encoding="utf-8")
            r = run_nike("detect", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["language"], "javascript")
            self.assertEqual(data["package_manager"], "pnpm")
            self.assertEqual(data["commands"]["test"], "pnpm run test")
            self.assertEqual(data["commands"]["lint"], "pnpm run lint")
            self.assertEqual(data["commands"]["typecheck"], "pnpm run typecheck")

    def test_rust_project(self) -> None:
        with TemporaryDirectory() as td:
            Path(td, "Cargo.toml").write_text(
                "[package]\nname = \"x\"\n", encoding="utf-8"
            )
            r = run_nike("detect", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["language"], "rust")
            self.assertEqual(data["commands"]["test"], "cargo test")

    def test_go_project(self) -> None:
        with TemporaryDirectory() as td:
            Path(td, "go.mod").write_text("module x\n", encoding="utf-8")
            r = run_nike("detect", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["language"], "go")
            self.assertEqual(data["commands"]["test"], "go test ./...")


class TestNikeScan(unittest.TestCase):
    def test_no_scanners_returns_status(self) -> None:
        # In a clean tempdir with no project markers, no scanners should match.
        # (npm/semgrep etc. may be on PATH but require project markers.)
        with TemporaryDirectory() as td:
            r = run_nike("scan", cwd=td)
            data = json.loads(r.stdout)
            # Either no_scanners (most cases) or ok with scanners that don't
            # require project markers (e.g., semgrep, bandit). Both are valid.
            self.assertIn(data["status"], ("no_scanners", "ok"))


class TestValidateRequirementsText(unittest.TestCase):
    """Unit tests for the pure validation function."""

    VALID = (
        "# 要件定義: テスト機能\n"
        "\n"
        "## 4. 機能要件\n"
        "### FR-01: A\n"
        "**説明**: A の説明\n"
        "\n"
        "**受け入れ基準**:\n"
        "- Given X, When Y, Then Z\n"
        "\n"
    )

    def test_valid_passes(self) -> None:
        errors, warnings = nike.validate_requirements_text(self.VALID)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_top_heading(self) -> None:
        text = self.VALID.replace("# 要件定義: テスト機能", "# Some other title")
        errors, _ = nike.validate_requirements_text(text)
        rules = {e["rule"] for e in errors}
        self.assertIn("E002", rules)

    def test_missing_fr_section(self) -> None:
        text = "# 要件定義: x\n\n## 1. 背景\n"
        errors, _ = nike.validate_requirements_text(text)
        rules = {e["rule"] for e in errors}
        self.assertIn("E004", rules)

    def test_no_fr_entries(self) -> None:
        text = "# 要件定義: x\n\n## 4. 機能要件\n\n(まだ未記入)\n"
        errors, _ = nike.validate_requirements_text(text)
        rules = {e["rule"] for e in errors}
        self.assertIn("E005", rules)

    def test_duplicate_fr_ids(self) -> None:
        text = (
            "# 要件定義: x\n\n## 4. 機能要件\n"
            "### FR-01: A\n**説明**: A\n\n**受け入れ基準**:\n"
            "- Given a, When b, Then c\n\n"
            "### FR-01: B\n**説明**: B\n\n**受け入れ基準**:\n"
            "- Given d, When e, Then f\n\n"
        )
        errors, _ = nike.validate_requirements_text(text)
        rules = {e["rule"] for e in errors}
        self.assertIn("E006", rules)

    def test_fr_with_no_ac(self) -> None:
        text = (
            "# 要件定義: x\n\n## 4. 機能要件\n"
            "### FR-01: A\n**説明**: A\n\n**受け入れ基準**:\n"
            "- this is not a Given/When/Then line\n\n"
        )
        errors, _ = nike.validate_requirements_text(text)
        rules = {e["rule"] for e in errors}
        # Could fire E007 (no AC parsed) or E010 (malformed AC). Either is correct.
        self.assertTrue("E007" in rules or "E010" in rules)

    def test_empty_description_warns(self) -> None:
        text = (
            "# 要件定義: x\n\n## 4. 機能要件\n"
            "### FR-01: A\n**説明**: \n\n**受け入れ基準**:\n"
            "- Given a, When b, Then c\n\n"
        )
        _, warnings = nike.validate_requirements_text(text)
        rules = {w["rule"] for w in warnings}
        self.assertIn("W008", rules)


class TestNikeValidate(unittest.TestCase):
    def _seed_requirements(self, td: str, slug: str, body: str) -> None:
        run_nike("init", slug, cwd=td)
        Path(td, f"docs/design/{slug}/requirements.md").write_text(body, encoding="utf-8")

    def test_clean_returns_ok(self) -> None:
        with TemporaryDirectory() as td:
            self._seed_requirements(
                td,
                "clean",
                "# 要件定義: clean\n\n## 4. 機能要件\n"
                "### FR-01: A\n**説明**: A\n\n**受け入れ基準**:\n"
                "- Given X, When Y, Then Z\n\n",
            )
            r = run_nike("validate", "clean", cwd=td)
            self.assertEqual(r.returncode, 0)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["summary"]["errors"], 0)

    def test_errors_exit_code_1(self) -> None:
        with TemporaryDirectory() as td:
            self._seed_requirements(
                td,
                "broken",
                "# Wrong heading\n\n## Random\n",
            )
            r = run_nike("validate", "broken", cwd=td)
            self.assertEqual(r.returncode, 1)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "errors")
            self.assertGreater(data["summary"]["errors"], 0)

    def test_strict_treats_warnings_as_failure(self) -> None:
        with TemporaryDirectory() as td:
            # Create a requirements doc with warning-only condition (empty 説明)
            self._seed_requirements(
                td,
                "warn",
                "# 要件定義: warn\n\n## 4. 機能要件\n"
                "### FR-01: A\n**説明**: \n\n**受け入れ基準**:\n"
                "- Given X, When Y, Then Z\n\n",
            )
            r_loose = run_nike("validate", "warn", cwd=td)
            self.assertEqual(r_loose.returncode, 0)
            r_strict = run_nike("validate", "warn", "--strict", cwd=td)
            self.assertEqual(r_strict.returncode, 1)

    def test_cross_ref_unknown_fr_in_log(self) -> None:
        with TemporaryDirectory() as td:
            self._seed_requirements(
                td,
                "xref",
                "# 要件定義: xref\n\n## 4. 機能要件\n"
                "### FR-01: A\n**説明**: A\n\n**受け入れ基準**:\n"
                "- Given X, When Y, Then Z\n\n",
            )
            # Add a log that references FR-99 (doesn't exist)
            Path(td, "docs/design/xref/implementation-log.md").write_text(
                "# 実装ログ\n\n- [ ] FR-99: ghost\n",
                encoding="utf-8",
            )
            r = run_nike("validate", "xref", cwd=td)
            data = json.loads(r.stdout)
            warning_rules = {w["rule"] for w in data["warnings"]}
            self.assertIn("W301", warning_rules)

    def test_missing_feature_dir(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike("validate", "ghost", cwd=td)
            self.assertEqual(r.returncode, 1)
            data = json.loads(r.stdout)
            self.assertIn("error", data)


class TestNormalizePR(unittest.TestCase):
    def test_plain_number(self) -> None:
        self.assertEqual(nike.normalize_pr("42"), "42")

    def test_hash_prefixed(self) -> None:
        self.assertEqual(nike.normalize_pr("#42"), "42")

    def test_url(self) -> None:
        self.assertEqual(
            nike.normalize_pr("https://github.com/owner/repo/pull/42"),
            "42",
        )

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            nike.normalize_pr("not-a-pr")


class TestParseNumstat(unittest.TestCase):
    def test_basic(self) -> None:
        text = "30\t5\tscripts/nike.py\n10\t0\tREADME.md\n"
        files = nike.parse_numstat(text)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["path"], "scripts/nike.py")
        self.assertEqual(files[0]["added"], 30)
        self.assertEqual(files[0]["deleted"], 5)

    def test_binary_file_uses_zero(self) -> None:
        text = "-\t-\timg/logo.png\n"
        files = nike.parse_numstat(text)
        self.assertEqual(files[0]["added"], 0)
        self.assertEqual(files[0]["deleted"], 0)


class TestParseNameStatus(unittest.TestCase):
    def test_added_modified_deleted(self) -> None:
        text = "A\tnew.py\nM\texisting.py\nD\told.py\n"
        result = nike.parse_name_status(text)
        self.assertEqual(result["new.py"], "A")
        self.assertEqual(result["existing.py"], "M")
        self.assertEqual(result["old.py"], "D")

    def test_rename(self) -> None:
        text = "R100\told.py\tnew.py\n"
        result = nike.parse_name_status(text)
        self.assertEqual(result["new.py"], "R")


class TestMatchFeaturesFromPaths(unittest.TestCase):
    def test_direct_design_dir_edit(self) -> None:
        td = TemporaryDirectory()
        self.addCleanup(td.cleanup)
        td_path = Path(td.name)
        (td_path / "docs" / "design" / "user-auth").mkdir(parents=True)

        original = nike.DESIGN_ROOT
        nike.DESIGN_ROOT = td_path / "docs" / "design"
        try:
            result = nike.match_features_from_paths(
                ["docs/design/user-auth/requirements.md"]
            )
        finally:
            nike.DESIGN_ROOT = original
        self.assertIn("user-auth", result)

    def test_no_design_dir_returns_empty(self) -> None:
        td = TemporaryDirectory()
        self.addCleanup(td.cleanup)
        original = nike.DESIGN_ROOT
        nike.DESIGN_ROOT = Path(td.name) / "nonexistent"
        try:
            self.assertEqual(nike.match_features_from_paths(["a.py"]), [])
        finally:
            nike.DESIGN_ROOT = original

    def test_no_match_returns_empty(self) -> None:
        td = TemporaryDirectory()
        self.addCleanup(td.cleanup)
        td_path = Path(td.name)
        (td_path / "docs" / "design" / "user-auth").mkdir(parents=True)
        original = nike.DESIGN_ROOT
        nike.DESIGN_ROOT = td_path / "docs" / "design"
        try:
            result = nike.match_features_from_paths(
                ["scripts/unrelated.py", "README.md"]
            )
        finally:
            nike.DESIGN_ROOT = original
        self.assertEqual(result, [])


class TestNikeReviewInit(unittest.TestCase):
    def test_creates_report(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike("review-init", "pr-42", cwd=td)
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["slug"], "pr-42")
            report = Path(td, "docs/reviews/pr-42/report.md")
            self.assertTrue(report.exists())
            text = report.read_text(encoding="utf-8")
            self.assertIn("PR Review レポート: pr-42", text)
            # Placeholders should all be substituted
            self.assertNotIn("{{NAME}}", text)
            self.assertNotIn("{{DATE}}", text)
            self.assertNotIn("{{MODE}}", text)

    def test_existing_without_force_errors(self) -> None:
        with TemporaryDirectory() as td:
            run_nike("review-init", "x", cwd=td)
            r = run_nike("review-init", "x", cwd=td)
            self.assertEqual(r.returncode, 1)
            data = json.loads(r.stdout)
            self.assertIn("error", data)

    def test_force_overwrites(self) -> None:
        with TemporaryDirectory() as td:
            run_nike("review-init", "x", cwd=td)
            target = Path(td, "docs/reviews/x/report.md")
            target.write_text("MODIFIED", encoding="utf-8")
            r = run_nike("review-init", "x", "--force", cwd=td)
            self.assertEqual(r.returncode, 0)
            self.assertNotEqual(target.read_text(encoding="utf-8"), "MODIFIED")


def _git(td: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=td, check=True, capture_output=True)


def _git_init_with_commit(td: str) -> None:
    """Initialize a git repo with a base commit on `main`."""
    _git(td, "init", "-q", "-b", "main")
    _git(td, "config", "user.email", "test@example.com")
    _git(td, "config", "user.name", "Test")
    _git(td, "config", "commit.gpgsign", "false")
    Path(td, "README.md").write_text("# initial\n", encoding="utf-8")
    _git(td, "add", "README.md")
    _git(td, "commit", "-q", "-m", "initial")


@unittest.skipIf(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    "git not available",
)
class TestNikeReviewContextLocal(unittest.TestCase):
    def test_returns_local_mode_with_diff(self) -> None:
        with TemporaryDirectory() as td:
            _git_init_with_commit(td)
            _git(td, "checkout", "-q", "-b", "feat/x")
            Path(td, "src.py").write_text("print('hi')\n", encoding="utf-8")
            _git(td, "add", "src.py")
            _git(td, "commit", "-q", "-m", "add src")

            r = run_nike("review-context", "--base", "main", cwd=td)
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            data = json.loads(r.stdout)
            self.assertEqual(data["mode"], "local")
            self.assertEqual(data["base"]["ref"], "main")
            self.assertEqual(data["head"]["ref"], "feat/x")
            self.assertIsNone(data["pr"])
            self.assertEqual(data["stats"]["files_changed"], 1)
            self.assertEqual(data["files"][0]["path"], "src.py")
            self.assertEqual(data["files"][0]["status"], "A")
            self.assertEqual(len(data["commits"]), 1)
            self.assertIn("add src", data["commits"][0]["subject"])

    def test_no_diff_returns_empty_files(self) -> None:
        with TemporaryDirectory() as td:
            _git_init_with_commit(td)
            r = run_nike("review-context", "--base", "main", cwd=td)
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            data = json.loads(r.stdout)
            self.assertEqual(data["files"], [])
            self.assertEqual(data["stats"]["files_changed"], 0)

    def test_design_features_detected(self) -> None:
        with TemporaryDirectory() as td:
            _git_init_with_commit(td)
            (Path(td) / "docs/design/user-auth").mkdir(parents=True)
            _git(td, "checkout", "-q", "-b", "feat/y")
            Path(td, "docs/design/user-auth/requirements.md").write_text(
                "# 要件定義: user-auth\n", encoding="utf-8"
            )
            _git(td, "add", "docs/design/user-auth/requirements.md")
            _git(td, "commit", "-q", "-m", "add design")
            r = run_nike("review-context", "--base", "main", cwd=td)
            data = json.loads(r.stdout)
            self.assertIn("user-auth", data["design_features"])

    def test_claude_md_detected(self) -> None:
        with TemporaryDirectory() as td:
            _git_init_with_commit(td)
            Path(td, "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
            r = run_nike("review-context", "--base", "main", cwd=td)
            data = json.loads(r.stdout)
            self.assertEqual(data["claude_md"], "CLAUDE.md")

    def test_not_a_git_repo_errors(self) -> None:
        with TemporaryDirectory() as td:
            r = run_nike("review-context", cwd=td)
            self.assertEqual(r.returncode, 1)
            data = json.loads(r.stdout)
            self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
