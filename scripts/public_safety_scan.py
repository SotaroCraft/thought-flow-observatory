#!/usr/bin/env python3
"""Lightweight public-safety scan for tracked files and reachable Git history (M1).

Standard-library first. Not enterprise DLP — reproducible evidence for review.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".parquet",
    ".duckdb",
    ".zip",
    ".gz",
    ".whl",
    ".exe",
    ".dll",
    ".so",
    ".bin",
}

# Value-oriented patterns; avoid matching empty placeholder names alone.
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key_assignment", re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}")),
    ("secret_assignment", re.compile(r"(?i)(?:client_)?secret\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*")),
    ("openai_sk", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("pem_private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "tenant_id_assignment",
        re.compile(
            r"(?i)(?:tenant[_-]?id|subscription[_-]?id|project[_-]?id)\s*[:=]\s*['\"]?"
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        ),
    ),
    ("dotenv_secret_line", re.compile(r"(?im)^(?!#)[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)\s*=\s*\S+")),
]


@dataclass(frozen=True)
class Finding:
    scope: str
    path: str
    rule: str
    detail: str


def repo_root_from_cwd() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def git_ls_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    if not result.stdout:
        return []
    return [p.decode("utf-8", errors="replace") for p in result.stdout.split(b"\0") if p]


def git_rev_list(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "rev-list", "--all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_probably_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        return True
    return b"\0" in sample


def scan_text(scope: str, label: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule, pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(
                Finding(scope=scope, path=label, rule=rule, detail=match.group(0)[:120])
            )
    return findings


def scan_tracked_files(root: Path) -> tuple[list[str], list[str], list[Finding]]:
    tracked = git_ls_files(root)
    skipped: list[str] = []
    findings: list[Finding] = []
    for rel in tracked:
        path = root / rel
        if not path.is_file():
            continue
        if is_probably_binary(path):
            skipped.append(rel)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(rel)
            continue
        findings.extend(scan_text("tracked", rel, text))
    return tracked, skipped, findings


def scan_history(root: Path) -> tuple[list[str], list[Finding]]:
    commits = git_rev_list(root)
    findings: list[Finding] = []
    for commit in commits:
        # Name-only listing keeps the scan light; blob text via git grep -a.
        listed = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", commit],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        paths = [line for line in listed.stdout.splitlines() if line]
        for rel in paths:
            if Path(rel).suffix.lower() in BINARY_SUFFIXES:
                continue
            shown = subprocess.run(
                ["git", "show", f"{commit}:{rel}"],
                cwd=root,
                check=False,
                capture_output=True,
            )
            if shown.returncode != 0 or b"\0" in shown.stdout[:8192]:
                continue
            try:
                text = shown.stdout.decode("utf-8")
            except UnicodeDecodeError:
                continue
            findings.extend(scan_text("history", f"{commit[:12]}:{rel}", text))
    return commits, findings


def format_report(
    *,
    tracked: list[str],
    skipped: list[str],
    tracked_findings: list[Finding],
    commits: list[str],
    history_findings: list[Finding],
) -> str:
    lines = [
        "PUBLIC_SAFETY_SCAN",
        f"tracked_files={len(tracked)}",
        f"tracked_skipped_binary_or_undecodable={len(skipped)}",
        f"reachable_commits={len(commits)}",
        f"tracked_findings={len(tracked_findings)}",
        f"history_findings={len(history_findings)}",
    ]
    if skipped:
        lines.append("skipped:")
        lines.extend(f"  - {item}" for item in skipped)
    all_findings = tracked_findings + history_findings
    if all_findings:
        lines.append("findings:")
        for item in all_findings:
            lines.append(f"  - [{item.scope}] {item.path} rule={item.rule} detail={item.detail!r}")
        lines.append("RESULT=FAIL")
    else:
        lines.append("RESULT=CLEAN")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        action="store_true",
        default=True,
        help="Scan reachable Git history (default: on).",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip history scan.",
    )
    args = parser.parse_args(argv)
    root = repo_root_from_cwd()
    tracked, skipped, tracked_findings = scan_tracked_files(root)
    commits: list[str] = []
    history_findings: list[Finding] = []
    if args.history and not args.no_history:
        commits, history_findings = scan_history(root)
    report = format_report(
        tracked=tracked,
        skipped=skipped,
        tracked_findings=tracked_findings,
        commits=commits,
        history_findings=history_findings,
    )
    sys.stdout.write(report)
    return 1 if (tracked_findings or history_findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
