import locale
import os
import shlex
import subprocess
from pathlib import Path
from time import monotonic


class Result:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def split_commands(command):
    parts = []
    buf = []
    quote = None
    for ch in command:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            continue
        if ch == ";":
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    return parts


def decode(data):
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        encoding = locale.getpreferredencoding(False) or "cp949"
        return data.decode(encoding, errors="replace")


def cat_path(name, cwd):
    raw = Path(name)
    if raw.is_absolute() and raw.is_file():
        return raw
    posix = name.replace("\\", "/")
    if posix.startswith("/"):
        rooted = Path(cwd) / posix.lstrip("/")
        if rooted.is_file():
            return rooted
    return raw if raw.is_absolute() else Path(cwd) / raw


def builtin_cat(files, cwd):
    if not files:
        return Result(1, "", "cat: missing file operand\n")
    chunks = []
    for name in files:
        path = cat_path(name, cwd)
        try:
            chunks.append(path.read_bytes())
        except OSError as error:
            detail = error.strerror or error.__class__.__name__
            return Result(1, "", f"cat: {name}: {detail}\n")
    return Result(0, b"".join(chunks).decode("utf-8", errors="replace"), "")


def ping_argv(args):
    if not args:
        return ["ping"]
    host = args[-1]
    flags = args[:-1]
    count = "2"
    wait = None
    index = 0
    while index < len(flags):
        flag = flags[index]
        if flag == "-c" and index + 1 < len(flags):
            count = flags[index + 1]
            index += 2
            continue
        if flag in ("-W", "-w") and index + 1 < len(flags):
            wait = flags[index + 1]
            index += 2
            continue
        index += 1
    if os.name == "nt":
        return ["ping", "-n", str(count), host]
    argv = ["ping", "-c", str(count)]
    if wait is not None:
        argv.extend(["-W", str(wait)])
    argv.append(host)
    return argv


def run_one(argv, *, cwd, timeout):
    name = argv[0]
    if name == "cat":
        return builtin_cat(argv[1:], cwd)
    if name == "ping":
        argv = ping_argv(argv[1:])
    try:
        proc = subprocess.run(argv, capture_output=True, cwd=cwd, timeout=timeout)
    except FileNotFoundError:
        return Result(127, "", f"{name}: not found\n")
    return Result(proc.returncode, decode(proc.stdout), decode(proc.stderr))


def run(command, *, cwd, timeout):
    texts = []
    errors = []
    code = 0
    deadline = monotonic() + timeout
    for part in split_commands(command):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(
                command,
                timeout,
                output="".join(texts).encode("utf-8"),
                stderr="".join(errors).encode("utf-8"),
            )
        try:
            argv = shlex.split(part, posix=True)
        except ValueError:
            errors.append(f"syntax error: {part}\n")
            code = 2
            continue
        if not argv:
            continue
        result = run_one(argv, cwd=cwd, timeout=max(remaining, 0.1))
        texts.append(result.stdout)
        errors.append(result.stderr)
        code = result.returncode
    return Result(code, "".join(texts), "".join(errors))
