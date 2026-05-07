#!/usr/bin/env python3
"""
nike — CLI helper for the nike-skills workflow.

Mechanizes deterministic parts of the design → implement → verify (→ investigate)
workflow so AI Skills only spend tokens on tasks that genuinely
require judgment. All commands emit JSON on stdout for AI consumption.

Subcommands:
  init <slug> [--name "<human name>"] [--force]
  status [<slug>]
  parse-requirements <slug>
  validate <slug> [--strict]
  impl-init <slug> [--force]
  verify-init <slug> [--force]
  investigate-init <slug> [--type bug|security|both] [--title "<title>"] [--force]
  review-context [<pr>] [--base <ref>]
  review-init <slug> [--force]
  detect
  checks [--lint] [--typecheck] [--test] [--build]
  scan [--timeout N] [--output-limit N]

Exit codes:
  0   ok
  1   recoverable error (file not found, validation findings, etc.)
  2   command failure (one or more checks failed in `checks`)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
DESIGN_ROOT = ROOT / "docs" / "design"
INVESTIGATIONS_ROOT = ROOT / "docs" / "investigations"
REVIEWS_ROOT = ROOT / "docs" / "reviews"
SCRIPT_DIR = Path(__file__).parent.resolve()
TEMPLATE_DIR = SCRIPT_DIR / "templates"

PHASE_FILES = [
    "requirements.md",
    "basic-design.md",
    "detailed-design.md",
    "implementation-log.md",
    "verification-report.md",
]


def emit(data: Any, code: int = 0) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(code)


def render_template(name: str, **vars: Any) -> str:
    template = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    for k, v in vars.items():
        template = template.replace(f"{{{{{k}}}}}", str(v))
    return template


def feature_dir(slug: str) -> Path:
    return DESIGN_ROOT / slug


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def extract_name_from_requirements(req_path: Path, fallback: str) -> str:
    if not req_path.exists():
        return fallback
    first = req_path.read_text(encoding="utf-8").split("\n", 1)[0]
    m = re.match(r"#\s*要件定義[:：]?\s*(.+)", first)
    return m.group(1).strip() if m else fallback


def parse_requirements_md(text: str) -> list[dict]:
    """Extract functional requirements (FR-XX) and acceptance criteria."""
    sec = re.search(r"##\s*\d*\.?\s*機能要件\s*\n(.*?)(?=\n##\s|\Z)", text, re.DOTALL)
    if not sec:
        return []
    body = sec.group(1)
    fr_pattern = re.compile(
        r"###\s*(FR-\d+)[:：]?\s*(.+?)\n(.*?)(?=\n###\s|\Z)",
        re.DOTALL,
    )
    ac_pattern = re.compile(
        r"-\s*Given\s+(.+?)[,，、]\s*When\s+(.+?)[,，、]\s*Then\s+(.+?)(?=\n\s*-\s*Given|\n\n|\n##|\n\*\*|\Z)",
        re.DOTALL,
    )
    desc_pattern = re.compile(
        r"\*\*説明\*\*[:：]?[ \t]*(.*?)(?=\n\s*\*\*受け入れ基準|\Z)",
        re.DOTALL,
    )

    out: list[dict] = []
    for m in fr_pattern.finditer(body):
        fr_id = m.group(1).strip()
        fr_name = m.group(2).strip()
        fr_body = m.group(3)

        d = desc_pattern.search(fr_body)
        description = d.group(1).strip() if d else ""

        acs: list[dict] = []
        for i, am in enumerate(ac_pattern.finditer(fr_body)):
            acs.append(
                {
                    "id": f"{fr_id}-AC{i + 1}",
                    "given": am.group(1).strip(),
                    "when": am.group(2).strip(),
                    "then": am.group(3).strip().rstrip(".。"),
                }
            )

        out.append(
            {
                "id": fr_id,
                "name": fr_name,
                "description": description,
                "acceptance_criteria": acs,
            }
        )
    return out


def detect_project() -> dict:
    detected: dict = {"language": None, "package_manager": None, "commands": {}}

    if (ROOT / "package.json").exists():
        detected["language"] = "javascript"
        try:
            pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        except Exception:
            pkg = {}
        if (ROOT / "pnpm-lock.yaml").exists():
            pm = "pnpm"
        elif (ROOT / "yarn.lock").exists():
            pm = "yarn"
        elif (ROOT / "bun.lockb").exists() or (ROOT / "bun.lock").exists():
            pm = "bun"
        else:
            pm = "npm"
        detected["package_manager"] = pm
        run_prefix = "npm run" if pm == "npm" else f"{pm} run"
        scripts = pkg.get("scripts", {}) or {}
        for key in ("test", "lint", "typecheck", "type-check", "build", "dev", "start", "format"):
            if key in scripts:
                norm = "typecheck" if key == "type-check" else key
                detected["commands"][norm] = f"{run_prefix} {key}"

    elif (ROOT / "pyproject.toml").exists() or (ROOT / "setup.py").exists() or (ROOT / "requirements.txt").exists():
        detected["language"] = "python"
        pyproj_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8") if (ROOT / "pyproject.toml").exists() else ""
        if "[tool.pytest" in pyproj_text or (ROOT / "pytest.ini").exists() or any(ROOT.glob("test_*.py")) or any(ROOT.glob("**/test_*.py")):
            detected["commands"]["test"] = "pytest"
        if "[tool.ruff" in pyproj_text or (ROOT / "ruff.toml").exists():
            detected["commands"]["lint"] = "ruff check ."
            detected["commands"]["format"] = "ruff format ."
        elif (ROOT / ".flake8").exists() or "[tool.flake8" in pyproj_text:
            detected["commands"]["lint"] = "flake8"
        if "[tool.mypy" in pyproj_text or (ROOT / "mypy.ini").exists():
            detected["commands"]["typecheck"] = "mypy ."

    elif (ROOT / "Cargo.toml").exists():
        detected["language"] = "rust"
        detected["package_manager"] = "cargo"
        detected["commands"] = {
            "test": "cargo test",
            "lint": "cargo clippy -- -D warnings",
            "typecheck": "cargo check",
            "build": "cargo build",
        }

    elif (ROOT / "go.mod").exists():
        detected["language"] = "go"
        detected["commands"] = {
            "test": "go test ./...",
            "lint": "go vet ./...",
            "build": "go build ./...",
        }

    return detected


def cmd_init(args: argparse.Namespace) -> None:
    fd = feature_dir(args.slug)
    fd.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    name = args.name or args.slug

    files: dict[str, str] = {}
    for tname in ("requirements.md", "basic-design.md", "detailed-design.md"):
        target = fd / tname
        if target.exists() and not args.force:
            files[tname] = "skipped"
            continue
        target.write_text(
            render_template(tname, FEATURE_NAME=name, DATE=today),
            encoding="utf-8",
        )
        files[tname] = "created"

    emit(
        {
            "status": "ok",
            "slug": args.slug,
            "name": name,
            "feature_dir": rel(fd),
            "files": files,
        }
    )


def cmd_status(args: argparse.Namespace) -> None:
    if not DESIGN_ROOT.exists():
        emit({"design_root": rel(DESIGN_ROOT), "exists": False, "features": []})

    if args.slug:
        targets = [args.slug]
    else:
        targets = sorted(p.name for p in DESIGN_ROOT.iterdir() if p.is_dir())

    features = []
    for slug in targets:
        d = DESIGN_ROOT / slug
        if not d.is_dir():
            continue
        files = {}
        for fname in PHASE_FILES:
            f = d / fname
            files[fname] = {
                "exists": f.exists(),
                "size": f.stat().st_size if f.exists() else 0,
                "modified": (
                    datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")
                    if f.exists()
                    else None
                ),
            }

        if all(files[n]["exists"] for n in ("requirements.md", "basic-design.md", "detailed-design.md")):
            design = "complete"
        elif files["requirements.md"]["exists"]:
            design = "partial"
        else:
            design = "none"

        phases = {
            "design": design,
            "implementation": "exists" if files["implementation-log.md"]["exists"] else "none",
            "verification": "exists" if files["verification-report.md"]["exists"] else "none",
        }
        features.append({"slug": slug, "phases": phases, "files": files})

    emit({"design_root": rel(DESIGN_ROOT), "exists": True, "features": features})


def cmd_parse_requirements(args: argparse.Namespace) -> None:
    f = feature_dir(args.slug) / "requirements.md"
    if not f.exists():
        emit({"error": f"requirements.md not found: {rel(f)}"}, 1)
    requirements = parse_requirements_md(f.read_text(encoding="utf-8"))
    emit(
        {
            "slug": args.slug,
            "source": rel(f),
            "functional_requirements": requirements,
            "summary": {
                "fr_count": len(requirements),
                "ac_count": sum(len(r["acceptance_criteria"]) for r in requirements),
            },
        }
    )


def cmd_impl_init(args: argparse.Namespace) -> None:
    fd = feature_dir(args.slug)
    if not fd.exists():
        emit(
            {
                "error": f"Feature directory not found: {rel(fd)}. Run `nike init {args.slug}` first.",
            },
            1,
        )

    target = fd / "implementation-log.md"
    if target.exists() and not args.force:
        emit({"status": "exists", "path": rel(target)})

    req_path = fd / "requirements.md"
    task_lines: list[str] = []
    if req_path.exists():
        for fr in parse_requirements_md(req_path.read_text(encoding="utf-8")):
            task_lines.append(f"- [ ] {fr['id']}: {fr['name']}")

    name = extract_name_from_requirements(req_path, args.slug)
    target.write_text(
        render_template(
            "implementation-log.md",
            FEATURE_NAME=name,
            DATE=date.today().isoformat(),
            TASK_LIST="\n".join(task_lines) if task_lines else "- [ ] <task>",
        ),
        encoding="utf-8",
    )
    emit(
        {
            "status": "created",
            "path": rel(target),
            "tasks_seeded": len(task_lines),
        }
    )


def cmd_verify_init(args: argparse.Namespace) -> None:
    fd = feature_dir(args.slug)
    if not fd.exists():
        emit({"error": f"Feature directory not found: {rel(fd)}"}, 1)

    target = fd / "verification-report.md"
    if target.exists() and not args.force:
        emit({"status": "exists", "path": rel(target)})

    req_path = fd / "requirements.md"
    rows = ["| ID | 受け入れ基準 | 結果 | 検証手段 | 備考 |", "|----|-------------|------|---------|------|"]
    ac_total = 0
    if req_path.exists():
        for fr in parse_requirements_md(req_path.read_text(encoding="utf-8")):
            for ac in fr["acceptance_criteria"]:
                ac_total += 1
                criterion = f"Given {ac['given']}, When {ac['when']}, Then {ac['then']}"
                if len(criterion) > 90:
                    criterion = criterion[:87] + "..."
                # Escape pipes for table rendering
                criterion = criterion.replace("|", "\\|")
                rows.append(f"| {ac['id']} | {criterion} | NOT_VERIFIED | - | - |")
    if ac_total == 0:
        rows.append("| - | <受け入れ基準が requirements.md に未記載> | - | - | - |")

    name = extract_name_from_requirements(req_path, args.slug)
    commit = "unknown"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        pass

    target.write_text(
        render_template(
            "verification-report.md",
            FEATURE_NAME=name,
            DATETIME=datetime.now().isoformat(timespec="minutes"),
            COMMIT=commit,
            AC_TOTAL=ac_total,
            AC_TABLE="\n".join(rows),
        ),
        encoding="utf-8",
    )
    emit(
        {
            "status": "created",
            "path": rel(target),
            "acceptance_criteria_seeded": ac_total,
            "commit": commit,
        }
    )


def validate_requirements_text(text: str) -> tuple[list[dict], list[dict]]:
    """Return (errors, warnings) for a requirements.md document body."""
    errors: list[dict] = []
    warnings: list[dict] = []

    if not re.match(r"^#\s*要件定義[:：]?", text):
        errors.append(
            {"rule": "E002", "message": "Missing top-level '# 要件定義: <name>' heading"}
        )

    if not re.search(r"##\s*\d*\.?\s*機能要件", text):
        errors.append(
            {"rule": "E004", "message": "Missing '## ... 機能要件' section"}
        )
        # Without the section, no point checking FR-level rules
        return errors, warnings

    requirements = parse_requirements_md(text)
    if not requirements:
        errors.append(
            {
                "rule": "E005",
                "message": "機能要件 section has no parseable FR-XX entries",
            }
        )

    seen_ids: set[str] = set()
    for fr in requirements:
        fr_id = fr["id"]
        if fr_id in seen_ids:
            errors.append({"rule": "E006", "message": f"Duplicate FR ID: {fr_id}"})
        seen_ids.add(fr_id)

        if not fr["acceptance_criteria"]:
            errors.append(
                {"rule": "E007", "message": f"{fr_id} has no acceptance criteria"}
            )

        if not fr["description"].strip():
            warnings.append(
                {"rule": "W008", "message": f"{fr_id} has empty 説明"}
            )

    # E009: AC list items present but none match Given/When/Then
    ac_section = re.compile(
        r"\*\*受け入れ基準\*\*[:：]?\s*\n((?:\s*-\s*.+\n?)+)"
    )
    gwt = re.compile(r"-\s*Given\s+.+[,，、]\s*When\s+.+[,，、]\s*Then\s+.+")
    for m in ac_section.finditer(text):
        items = [
            line
            for line in m.group(1).splitlines()
            if line.strip().startswith("-")
        ]
        for item in items:
            if not gwt.match(item.strip()):
                snippet = item.strip()[:80]
                errors.append(
                    {
                        "rule": "E010",
                        "message": (
                            f"AC item doesn't match 'Given ..., When ..., Then ...': "
                            f"{snippet}"
                        ),
                    }
                )

    return errors, warnings


def cmd_validate(args: argparse.Namespace) -> None:
    fd = feature_dir(args.slug)
    if not fd.exists():
        emit({"error": f"Feature directory not found: {rel(fd)}"}, 1)

    findings_errors: list[dict] = []
    findings_warnings: list[dict] = []

    def add_error(file: str, rule: str, message: str) -> None:
        findings_errors.append({"file": file, "rule": rule, "message": message})

    def add_warning(file: str, rule: str, message: str) -> None:
        findings_warnings.append({"file": file, "rule": rule, "message": message})

    # requirements.md
    req_path = fd / "requirements.md"
    requirements_data: list[dict] = []
    if not req_path.exists():
        add_error("requirements.md", "E001", "requirements.md not found")
    else:
        text = req_path.read_text(encoding="utf-8")
        errors, warnings = validate_requirements_text(text)
        for e in errors:
            add_error("requirements.md", e["rule"], e["message"])
        for w in warnings:
            add_warning("requirements.md", w["rule"], w["message"])
        requirements_data = parse_requirements_md(text)

    fr_ids = {fr["id"] for fr in requirements_data}
    ac_ids = {ac["id"] for fr in requirements_data for ac in fr["acceptance_criteria"]}

    # basic-design.md
    bd_path = fd / "basic-design.md"
    if not bd_path.exists():
        add_error("basic-design.md", "E101", "basic-design.md not found")

    # detailed-design.md
    dd_path = fd / "detailed-design.md"
    if not dd_path.exists():
        add_error("detailed-design.md", "E201", "detailed-design.md not found")

    # implementation-log.md (cross-reference only; absence is not an error since
    # implementation may not have started yet)
    log_path = fd / "implementation-log.md"
    if log_path.exists() and fr_ids:
        log_text = log_path.read_text(encoding="utf-8")
        for m in re.finditer(r"-\s*\[[ xX]\]\s*(FR-\d+)", log_text):
            ref = m.group(1)
            if ref not in fr_ids:
                add_warning(
                    "implementation-log.md",
                    "W301",
                    f"References {ref} which does not exist in requirements.md",
                )

    # verification-report.md (cross-reference)
    vr_path = fd / "verification-report.md"
    if vr_path.exists() and ac_ids:
        vr_text = vr_path.read_text(encoding="utf-8")
        for m in re.finditer(r"\|\s*(FR-\d+-AC\d+)\s*\|", vr_text):
            ref = m.group(1)
            if ref not in ac_ids:
                add_warning(
                    "verification-report.md",
                    "W401",
                    f"References {ref} which does not exist in requirements.md",
                )

    error_count = len(findings_errors)
    warning_count = len(findings_warnings)

    if error_count:
        status = "errors"
    elif warning_count:
        status = "warnings"
    else:
        status = "ok"

    fail = error_count > 0 or (args.strict and warning_count > 0)
    emit(
        {
            "slug": args.slug,
            "status": status,
            "summary": {"errors": error_count, "warnings": warning_count},
            "errors": findings_errors,
            "warnings": findings_warnings,
        },
        code=1 if fail else 0,
    )


def cmd_investigate_init(args: argparse.Namespace) -> None:
    inv_dir = INVESTIGATIONS_ROOT / args.slug
    inv_dir.mkdir(parents=True, exist_ok=True)

    target = inv_dir / "report.md"
    if target.exists() and not args.force:
        emit({"status": "exists", "path": rel(target)})

    title = args.title or args.slug
    commit = "unknown"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        pass

    target.write_text(
        render_template(
            "investigation-report.md",
            TITLE=title,
            DATETIME=datetime.now().isoformat(timespec="minutes"),
            TYPE=args.type,
            COMMIT=commit,
        ),
        encoding="utf-8",
    )
    emit(
        {
            "status": "created",
            "path": rel(target),
            "type": args.type,
            "commit": commit,
        }
    )


SCANNER_REGISTRY = [
    # (name, availability_check, command)
    # availability_check is (binary_name, project_marker_path | None)
    ("npm-audit", ("npm", "package.json"), "npm audit --json"),
    ("pip-audit", ("pip-audit", None), "pip-audit --format=json"),
    ("safety", ("safety", None), "safety check --json"),
    ("cargo-audit", ("cargo-audit", "Cargo.toml"), "cargo audit --json"),
    ("gosec", ("gosec", "go.mod"), "gosec -fmt json -quiet ./..."),
    ("govulncheck", ("govulncheck", "go.mod"), "govulncheck -json ./..."),
    ("semgrep", ("semgrep", None), "semgrep scan --json --config=auto --quiet"),
    ("bandit", ("bandit", None), "bandit -r . -f json -q"),
]


def _scanner_available(binary: str, marker: str | None) -> bool:
    if shutil.which(binary) is None:
        return False
    if marker and not (ROOT / marker).exists():
        return False
    return True


def cmd_scan(args: argparse.Namespace) -> None:
    available = []
    for name, (binary, marker), cmd in SCANNER_REGISTRY:
        if _scanner_available(binary, marker):
            available.append((name, cmd))

    if not available:
        emit(
            {
                "status": "no_scanners",
                "message": (
                    "No security scanners detected on PATH. "
                    "Consider installing one of: semgrep, npm (audit), pip-audit, "
                    "safety, cargo-audit, gosec, govulncheck, bandit."
                ),
                "results": [],
            }
        )

    results: list[dict] = []
    for name, cmd in available:
        result: dict = {"name": name, "command": cmd}
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=args.timeout,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            limit = args.output_limit
            result["exit_code"] = proc.returncode
            # Many scanners use exit code 1 to mean "findings present" — that's not a tool failure.
            # We surface the raw exit code; AI interprets meaning per scanner.
            stripped = stdout.strip()
            parsed = None
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(stdout)
                except Exception:
                    parsed = None
            result["json"] = parsed
            result["stdout_tail"] = stdout[-limit:] if len(stdout) > limit else stdout
            result["stderr_tail"] = stderr[-limit:] if len(stderr) > limit else stderr
            result["truncated"] = len(stdout) > limit or len(stderr) > limit
        except subprocess.TimeoutExpired:
            result.update({"exit_code": -1, "error": "timeout"})
        except Exception as e:
            result.update({"exit_code": -1, "error": str(e)})
        results.append(result)

    emit({"status": "ok", "scanners_run": len(results), "results": results})


PR_URL_RE = re.compile(r"https?://github\.com/[^/]+/[^/]+/pull/(\d+)")


def normalize_pr(value: str) -> str:
    """Normalize a PR reference (`#42`, `42`, or full URL) to a number string."""
    v = value.strip()
    m = PR_URL_RE.match(v)
    if m:
        return m.group(1)
    if v.startswith("#"):
        v = v[1:]
    if not v.isdigit():
        raise ValueError(f"invalid PR reference: {value!r}")
    return v


def run_git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_gh(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["gh", *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def detect_default_branch() -> str:
    code, out, _ = run_git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if code == 0 and out.strip():
        return out.strip().split("/", 1)[1] if "/" in out.strip() else out.strip()
    code, out, _ = run_git("rev-parse", "--abbrev-ref", "origin/HEAD")
    if code == 0 and out.strip() and not out.strip().startswith("HEAD"):
        ref = out.strip()
        return ref.split("/", 1)[1] if ref.startswith("origin/") else ref
    return "main"


def parse_numstat(text: str) -> list[dict]:
    """Parse `git diff --numstat` output. Binary files report '-' for counts."""
    files: list[dict] = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts[0], parts[1], parts[2]
        try:
            added = int(added_s)
        except ValueError:
            added = 0
        try:
            deleted = int(deleted_s)
        except ValueError:
            deleted = 0
        files.append({"path": path, "status": "M", "added": added, "deleted": deleted})
    return files


def parse_name_status(text: str) -> dict[str, str]:
    """Parse `git diff --name-status` output. Returns path → status code (A/M/D/R...)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0][:1]  # for renames: 'R100' → 'R'
        if status == "R" and len(parts) >= 3:
            out[parts[2]] = "R"
        elif len(parts) >= 2:
            out[parts[1]] = status
    return out


def parse_log(text: str) -> list[dict]:
    """Parse `git log --pretty=format:%H|%s|%an <%ae>` output."""
    commits: list[dict] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        commits.append({"sha": parts[0], "subject": parts[1], "author": parts[2]})
    return commits


def match_features_from_paths(paths: list[str]) -> list[str]:
    """Heuristically match diff paths to existing docs/design/<slug>/ features."""
    if not DESIGN_ROOT.exists():
        return []
    slugs = sorted(p.name for p in DESIGN_ROOT.iterdir() if p.is_dir())
    if not slugs:
        return []

    matched: set[str] = set()
    design_prefix = "docs/design/"
    for slug in slugs:
        slug_tokens = {t for t in re.split(r"[-_]", slug) if t}
        for path in paths:
            norm = path.replace("\\", "/")
            if norm.startswith(f"{design_prefix}{slug}/"):
                matched.add(slug)
                break
            path_tokens = {
                t.lower()
                for t in re.split(r"[\\/_\-.]", norm)
                if t
            }
            if not slug_tokens or not path_tokens:
                continue
            overlap = slug_tokens & path_tokens
            # Require at least half of slug tokens to appear in the path.
            if overlap and len(overlap) >= max(1, (len(slug_tokens) + 1) // 2):
                matched.add(slug)
                break
    return sorted(matched)


def cmd_review_context(args: argparse.Namespace) -> None:
    if shutil.which("git") is None:
        emit({"error": "git not found"}, 1)

    if args.pr is None:
        # local mode
        code, _, stderr = run_git("rev-parse", "--git-dir")
        if code != 0:
            emit({"error": "not a git repository", "detail": stderr.strip()}, 1)

        base_ref = args.base or detect_default_branch()
        code, head_ref_out, _ = run_git("rev-parse", "--abbrev-ref", "HEAD")
        head_ref = head_ref_out.strip() if code == 0 else "HEAD"

        code, base_sha_out, stderr = run_git("merge-base", base_ref, "HEAD")
        if code != 0:
            # Fall back to the base ref directly so the diff is still meaningful.
            code2, base_sha_out, _ = run_git("rev-parse", base_ref)
            if code2 != 0:
                emit(
                    {
                        "error": f"failed to resolve base ref: {base_ref}",
                        "detail": stderr.strip(),
                    },
                    1,
                )
        base_sha = base_sha_out.strip()

        _, head_sha_out, _ = run_git("rev-parse", "HEAD")
        head_sha = head_sha_out.strip()
        pr_meta = None
    else:
        # PR mode
        if shutil.which("gh") is None:
            emit({"error": "gh required for PR mode"}, 1)

        try:
            pr_num = normalize_pr(args.pr)
        except ValueError as e:
            emit({"error": str(e)}, 1)

        code, view_out, stderr = run_gh(
            "pr",
            "view",
            pr_num,
            "--json",
            "number,title,url,author,labels,baseRefName,headRefName,baseRefOid,headRefOid",
        )
        if code != 0:
            emit({"error": "pr not found or gh failure", "detail": stderr.strip()}, 1)

        try:
            meta = json.loads(view_out)
        except json.JSONDecodeError as e:
            emit({"error": "failed to parse gh output", "detail": str(e)}, 1)

        author = ""
        if isinstance(meta.get("author"), dict):
            author = meta["author"].get("login", "")
        labels = [
            lbl.get("name", "") for lbl in (meta.get("labels") or []) if isinstance(lbl, dict)
        ]
        pr_meta = {
            "number": meta.get("number"),
            "title": meta.get("title", ""),
            "url": meta.get("url", ""),
            "author": author,
            "labels": labels,
            "base_ref": meta.get("baseRefName", ""),
            "head_ref": meta.get("headRefName", ""),
        }
        base_ref = args.base or pr_meta["base_ref"]
        head_ref = pr_meta["head_ref"]
        base_sha = meta.get("baseRefOid", "")
        head_sha = meta.get("headRefOid", "")

    diff_range = f"{base_sha}...{head_sha}" if base_sha and head_sha else f"{base_ref}...HEAD"

    _, numstat_out, _ = run_git("diff", "--numstat", diff_range)
    files = parse_numstat(numstat_out)
    _, name_status_out, _ = run_git("diff", "--name-status", diff_range)
    status_map = parse_name_status(name_status_out)
    for f in files:
        if f["path"] in status_map:
            f["status"] = status_map[f["path"]]

    _, log_out, _ = run_git(
        "log", f"{base_sha}..{head_sha}" if base_sha and head_sha else f"{base_ref}..HEAD",
        "--pretty=format:%H|%s|%an <%ae>",
    )
    commits = parse_log(log_out)

    stats = {
        "files_changed": len(files),
        "added": sum(f["added"] for f in files),
        "deleted": sum(f["deleted"] for f in files),
    }

    design_features = match_features_from_paths([f["path"] for f in files])
    claude_md = "CLAUDE.md" if (ROOT / "CLAUDE.md").exists() else None

    emit(
        {
            "mode": "pr" if pr_meta else "local",
            "base": {"ref": base_ref, "sha": base_sha},
            "head": {"ref": head_ref, "sha": head_sha},
            "pr": pr_meta,
            "files": files,
            "stats": stats,
            "commits": commits,
            "design_features": design_features,
            "claude_md": claude_md,
        }
    )


def cmd_review_init(args: argparse.Namespace) -> None:
    rd = REVIEWS_ROOT / args.slug
    rd.mkdir(parents=True, exist_ok=True)

    target = rd / "report.md"
    if target.exists() and not args.force:
        emit({"error": "report exists", "path": rel(target)}, 1)

    target.write_text(
        render_template(
            "review-report.md",
            NAME=args.slug,
            DATE=date.today().isoformat(),
            MODE="local",
            PR_LINE="",
            BASE_REF="-",
            BASE_SHA_SHORT="-",
            HEAD_REF="-",
            HEAD_SHA_SHORT="-",
            FILES_CHANGED="-",
            ADDED="-",
            DELETED="-",
        ),
        encoding="utf-8",
    )
    emit(
        {
            "status": "ok",
            "slug": args.slug,
            "report_path": rel(target),
        }
    )


def cmd_detect(args: argparse.Namespace) -> None:
    emit(detect_project())


def cmd_checks(args: argparse.Namespace) -> None:
    detected = detect_project()
    cmds = detected.get("commands", {})

    explicit = [k for k in ("lint", "typecheck", "test", "build") if getattr(args, k)]
    keys = explicit if explicit else [k for k in ("lint", "typecheck", "test", "build") if k in cmds]

    results: list[dict] = []
    for key in keys:
        if key not in cmds:
            results.append(
                {
                    "name": key,
                    "command": None,
                    "skipped": True,
                    "reason": "command not detected",
                }
            )
            continue
        cmd = cmds[key]
        result: dict = {"name": key, "command": cmd}
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=ROOT,
                timeout=args.timeout,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            limit = args.output_limit
            result.update(
                {
                    "exit_code": proc.returncode,
                    "passed": proc.returncode == 0,
                    "stdout_tail": stdout[-limit:] if len(stdout) > limit else stdout,
                    "stderr_tail": stderr[-limit:] if len(stderr) > limit else stderr,
                    "truncated": len(stdout) > limit or len(stderr) > limit,
                }
            )
        except subprocess.TimeoutExpired:
            result.update({"exit_code": -1, "passed": False, "error": "timeout"})
        except Exception as e:
            result.update({"exit_code": -1, "passed": False, "error": str(e)})
        results.append(result)

    summary = {
        "language": detected.get("language"),
        "checks_run": len([r for r in results if not r.get("skipped")]),
        "checks_passed": sum(1 for r in results if r.get("passed")),
        "checks_failed": sum(1 for r in results if r.get("passed") is False),
        "results": results,
    }
    code = 0 if summary["checks_failed"] == 0 else 2
    emit(summary, code=code)


def main() -> None:
    parser = argparse.ArgumentParser(prog="nike", description="nike-skills CLI helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Create design directory + 3 templates")
    p.add_argument("slug", help="kebab-case feature slug")
    p.add_argument("--name", help="human-readable name (defaults to slug)")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="Show feature workflow status")
    p.add_argument("slug", nargs="?", help="optional: filter to one feature")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("parse-requirements", help="Parse requirements.md to JSON")
    p.add_argument("slug")
    p.set_defaults(func=cmd_parse_requirements)

    p = sub.add_parser(
        "validate",
        help="Lint design docs (FR/AC format, cross-doc references)",
    )
    p.add_argument("slug")
    p.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as errors (exit code 1 even with no errors)",
    )
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("impl-init", help="Create implementation-log.md from requirements")
    p.add_argument("slug")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_impl_init)

    p = sub.add_parser("verify-init", help="Create verification-report.md from requirements")
    p.add_argument("slug")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_verify_init)

    p = sub.add_parser(
        "investigate-init",
        help="Create docs/investigations/<slug>/report.md from template",
    )
    p.add_argument("slug")
    p.add_argument("--type", choices=["bug", "security", "both"], default="bug")
    p.add_argument("--title", help="human-readable title (defaults to slug)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_investigate_init)

    p = sub.add_parser(
        "review-context",
        help="Collect diff/PR metadata for review (local diff or GitHub PR)",
    )
    p.add_argument("pr", nargs="?", help="optional PR number/URL; omit for local mode")
    p.add_argument("--base", help="override base ref (e.g. origin/main)")
    p.set_defaults(func=cmd_review_context)

    p = sub.add_parser(
        "review-init",
        help="Create docs/reviews/<slug>/report.md from template",
    )
    p.add_argument("slug")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_review_init)

    p = sub.add_parser("detect", help="Detect project type and infer commands")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("checks", help="Run lint/typecheck/test/build")
    p.add_argument("--lint", action="store_true")
    p.add_argument("--typecheck", action="store_true")
    p.add_argument("--test", action="store_true")
    p.add_argument("--build", action="store_true")
    p.add_argument("--timeout", type=int, default=600, help="per-command timeout in seconds")
    p.add_argument("--output-limit", type=int, default=4000, help="bytes of stdout/stderr to keep")
    p.set_defaults(func=cmd_checks)

    p = sub.add_parser("scan", help="Run available security/vulnerability scanners")
    p.add_argument("--timeout", type=int, default=600, help="per-scanner timeout in seconds")
    p.add_argument("--output-limit", type=int, default=8000, help="bytes of stdout/stderr to keep")
    p.set_defaults(func=cmd_scan)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
