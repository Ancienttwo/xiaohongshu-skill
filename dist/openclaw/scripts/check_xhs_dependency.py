#!/usr/bin/env python3
"""Check that xiaohongshu-cli is installed, current, and optionally authenticated."""

from __future__ import annotations

import argparse
import subprocess
import sys

from xhs_cli_utils import (
    DEFAULT_XHS_BINARY,
    MIN_XHS_VERSION,
    XhsCliError,
    format_version,
    get_xhs_version,
    is_version_at_least,
    resolve_xhs_binary,
    run_xhs,
)


EXIT_OK = 0
EXIT_MISSING = 10
EXIT_OUTDATED = 11
EXIT_COMMAND_MISSING = 12
EXIT_AUTH_NEEDED = 20
EXIT_VERIFICATION_REQUIRED = 21
EXIT_IP_BLOCKED = 22
EXIT_AUTH_FAILED = 23

READ_ONLY_COMMANDS = [
    "status",
    "whoami",
    "search",
    "read",
    "comments",
    "user",
    "user-posts",
    "my-notes",
    "topics",
    "hot",
]

WRITE_COMMANDS = [
    "post",
]

CORE_COMMANDS = [*READ_ONLY_COMMANDS, *WRITE_COMMANDS]

AUTH_ERROR_EXIT = {
    "not_authenticated": EXIT_AUTH_NEEDED,
    "session_expired": EXIT_AUTH_NEEDED,
    "no_cookie": EXIT_AUTH_NEEDED,
    "missing_cookie": EXIT_AUTH_NEEDED,
    "verification_required": EXIT_VERIFICATION_REQUIRED,
    "need_verify": EXIT_VERIFICATION_REQUIRED,
    "ip_blocked": EXIT_IP_BLOCKED,
}


def print_status(level: str, message: str) -> None:
    print(f"{level}: {message}")


def check_core_commands(binary: str, commands: list[str] | None = None) -> tuple[bool, list[str]]:
    missing = []
    for command in (commands or CORE_COMMANDS):
        try:
            completed = subprocess.run(
                [binary, command, "--help"],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except subprocess.TimeoutExpired:
            missing.append(command)
            continue
        if completed.returncode != 0:
            missing.append(command)
    return not missing, missing


def check_auth(binary: str) -> int:
    try:
        data = run_xhs(["status"], binary=binary, timeout=30)
    except XhsCliError as exc:
        exit_code = AUTH_ERROR_EXIT.get(exc.code, EXIT_AUTH_FAILED)
        if exit_code == EXIT_AUTH_NEEDED:
            print_status("NEEDS_CONTEXT", "xhs 尚未登录。请运行 `xhs login` 或 `xhs login --qrcode` 后重试。")
        elif exit_code == EXIT_VERIFICATION_REQUIRED:
            print_status("NEEDS_CONTEXT", "小红书触发验证码。请在浏览器完成验证后重试。")
        elif exit_code == EXIT_IP_BLOCKED:
            print_status("BLOCKED", "当前网络或 IP 被小红书限制。请切换网络后重试。")
        elif exc.code == "xhs_timeout":
            print_status("BLOCKED", "xhs status --json 超时。请确认网络和小红书登录状态，必要时运行 `xhs login --qrcode` 后重试。")
        else:
            print_status("BLOCKED", f"xhs 登录状态检查失败: {exc.code}: {exc.message}")
        return exit_code

    user = data.get("user", {}) if isinstance(data, dict) else {}
    authenticated = bool(data.get("authenticated")) if isinstance(data, dict) else False
    guest = bool(user.get("guest")) if isinstance(user, dict) else False
    nickname = str(user.get("nickname") or user.get("name") or "") if isinstance(user, dict) else ""
    if not authenticated or guest:
        print_status("NEEDS_CONTEXT", "xhs 返回未登录或访客状态。请运行 `xhs login` 或 `xhs login --qrcode`。")
        return EXIT_AUTH_NEEDED

    print_status("DONE", f"xhs 已登录: {nickname or 'unknown user'}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth", action="store_true", help="Also verify xhs authentication with `xhs status --json`.")
    parser.add_argument("--research", action="store_true", help="Check only read-only research commands; do not require write commands such as post.")
    parser.add_argument("--xhs-binary", default=DEFAULT_XHS_BINARY, help="Path or name of xhs executable.")
    args = parser.parse_args(argv)

    executable = resolve_xhs_binary(args.xhs_binary)
    if not executable:
        print_status("BLOCKED", "未找到 xhs。安装命令: uv tool install xiaohongshu-cli")
        return EXIT_MISSING

    try:
        version = get_xhs_version(executable)
    except XhsCliError as exc:
        print_status("BLOCKED", f"xhs 版本检查失败: {exc.message}")
        return EXIT_MISSING

    if not is_version_at_least(version):
        print_status(
            "BLOCKED",
            f"xhs 版本过旧: {format_version(version)}，需要 >= {format_version(MIN_XHS_VERSION)}。升级: uv tool upgrade xiaohongshu-cli",
        )
        return EXIT_OUTDATED

    required_commands = READ_ONLY_COMMANDS if args.research else CORE_COMMANDS
    commands_ok, missing = check_core_commands(executable, required_commands)
    if not commands_ok:
        mode = "只读研究命令" if args.research else "核心命令"
        print_status("BLOCKED", f"xhs 缺少{mode}: {', '.join(missing)}。请升级: uv tool upgrade xiaohongshu-cli")
        return EXIT_COMMAND_MISSING

    print_status("DONE", f"xhs dependency ok: {format_version(version)} ({executable})")
    if args.auth:
        return check_auth(executable)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
