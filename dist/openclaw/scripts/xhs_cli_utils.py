#!/usr/bin/env python3
"""Utilities for invoking the external xhs CLI safely.

This module treats xiaohongshu-cli as a process boundary. It does not import
the upstream package, and it never reads or prints cookies.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MIN_XHS_VERSION = (0, 6, 4)
SCHEMA_VERSION = "1"
DEFAULT_XHS_BINARY = "xhs"


class XhsCliError(RuntimeError):
    """Raised when xhs returns an error or malformed structured output."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        returncode: int = 1,
        details: Any | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.returncode = returncode
        self.details = details
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class XhsCommandResult:
    """Structured result from an xhs command."""

    args: list[str]
    envelope: dict[str, Any]
    stdout: str
    stderr: str
    returncode: int

    @property
    def data(self) -> Any:
        return self.envelope.get("data")


def parse_version_text(version_text: str) -> tuple[int, ...]:
    """Extract a semantic version tuple from `xhs --version` output."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_text)
    if not match:
        return ()
    return tuple(int(part) for part in match.groups())


def format_version(version: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in version) if version else "unknown"


def is_version_at_least(version: tuple[int, ...], minimum: tuple[int, ...] = MIN_XHS_VERSION) -> bool:
    if not version:
        return False
    return version >= minimum


def resolve_xhs_binary(binary: str = DEFAULT_XHS_BINARY) -> str | None:
    if Path(binary).is_absolute() or "/" in binary:
        return binary if Path(binary).exists() else None
    return shutil.which(binary)


def get_xhs_version(binary: str = DEFAULT_XHS_BINARY, timeout: int = 10) -> tuple[int, ...]:
    executable = resolve_xhs_binary(binary)
    if not executable:
        raise XhsCliError(
            "missing_dependency",
            "未找到 xhs 命令。请先运行: uv tool install xiaohongshu-cli",
        )
    try:
        completed = subprocess.run(
            [executable, "--version"],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise XhsCliError(
            "xhs_timeout",
            "xhs --version 执行超时",
            details={"timeout": timeout},
            stdout=(exc.stdout or "").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr or "").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
        ) from exc
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        raise XhsCliError(
            "version_check_failed",
            output or "xhs --version 执行失败",
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    return parse_version_text(output)


def _args_with_json(args: list[str]) -> list[str]:
    if "--json" in args or "--yaml" in args:
        return args
    return [*args, "--json"]


def parse_xhs_envelope(stdout: str, *, args: list[str], returncode: int = 0, stderr: str = "") -> dict[str, Any]:
    """Parse and validate the xiaohongshu-cli structured envelope."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise XhsCliError(
            "non_json_output",
            "xhs 未返回 JSON envelope",
            returncode=returncode,
            details={"position": exc.pos, "args": args},
            stdout=stdout,
            stderr=stderr,
        ) from exc

    if not isinstance(envelope, dict):
        raise XhsCliError(
            "invalid_envelope",
            "xhs JSON 输出不是对象",
            returncode=returncode,
            details={"args": args},
            stdout=stdout,
            stderr=stderr,
        )

    if envelope.get("schema_version") != SCHEMA_VERSION or "ok" not in envelope:
        raise XhsCliError(
            "schema_drift",
            "xhs envelope schema 不符合预期",
            returncode=returncode,
            details={"args": args, "schema_version": envelope.get("schema_version")},
            stdout=stdout,
            stderr=stderr,
        )

    return envelope


def run_xhs_command(
    args: list[str],
    *,
    binary: str = DEFAULT_XHS_BINARY,
    timeout: int = 90,
    cwd: Path | None = None,
    check: bool = True,
) -> XhsCommandResult:
    """Run `xhs` with JSON output and return the validated envelope."""
    executable = resolve_xhs_binary(binary)
    if not executable:
        raise XhsCliError(
            "missing_dependency",
            "未找到 xhs 命令。请先运行: uv tool install xiaohongshu-cli",
        )

    command_args = _args_with_json(args)
    try:
        completed = subprocess.run(
            [executable, *command_args],
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise XhsCliError(
            "xhs_timeout",
            "xhs 命令执行超时",
            details={"args": command_args, "timeout": timeout},
            stdout=(exc.stdout or "").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr or "").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
        ) from exc

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if not stdout:
        raise XhsCliError(
            "empty_output",
            "xhs 未返回结构化输出",
            returncode=completed.returncode,
            details={"args": command_args},
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    envelope = parse_xhs_envelope(stdout, args=command_args, returncode=completed.returncode, stderr=stderr)
    if not envelope.get("ok", False):
        error = envelope.get("error", {})
        if not isinstance(error, dict):
            error = {}
        raise XhsCliError(
            str(error.get("code") or "xhs_error"),
            str(error.get("message") or "xhs 命令失败"),
            returncode=completed.returncode,
            details=error.get("details"),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    if check and completed.returncode != 0:
        raise XhsCliError(
            "xhs_command_failed",
            stderr or "xhs 命令返回非零退出码",
            returncode=completed.returncode,
            details={"args": command_args},
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return XhsCommandResult(
        args=command_args,
        envelope=envelope,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )


def run_xhs(args: list[str], **kwargs: Any) -> Any:
    """Return only the `.data` payload from a successful xhs command."""
    return run_xhs_command(args, **kwargs).data


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
