from argparse import ArgumentParser
from ipaddress import IPv4Address, IPv4Network
import os
import subprocess
import sys
from pathlib import Path
from secrets import token_urlsafe
from time import sleep


def prepare(manage):
    for settings in ("config.settings", "config.patched"):
        subprocess.run(
            [sys.executable, str(manage), "migrate", "--noinput", "--verbosity=0", f"--settings={settings}"],
            check=True,
        )
    subprocess.run(
        [sys.executable, str(manage), "seed_lab", "--keep-password", "--verbosity=0", "--settings=config.settings"],
        check=True,
    )


def run_servers(legacy_port, patched_host):
    manage = Path(__file__).resolve()
    servers = []
    try:
        prepare(manage)
        server_env = {**os.environ, "DJANGO_RUNSERVER_HIDE_WARNING": "true"}
        for host, port, settings in (
            ("127.0.0.1", legacy_port, "config.settings"),
            (patched_host, 8001, "config.patched"),
        ):
            env = server_env
            if patched_host != "127.0.0.1":
                env = {**server_env, "OPSWATCH_PATCHED_HOST": patched_host}
                if settings == "config.patched":
                    env.setdefault("DJANGO_SECRET_KEY", token_urlsafe(48))
            command = [sys.executable, "-u", str(manage), "runserver", f"{host}:{port}",
                       f"--settings={settings}", "--insecure", "--noreload"]
            servers.append(subprocess.Popen(command, env=env))
        while True:
            for server in servers:
                status = server.poll()
                if status is not None:
                    return status or 1
            sleep(0.2)
    except KeyboardInterrupt:
        return 0
    except subprocess.CalledProcessError as error:
        return error.returncode
    finally:
        for server in servers:
            if server.poll() is None:
                server.terminate()
        for server in servers:
            server.wait()


def project_python():
    root = Path(__file__).resolve().parent
    relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    interpreter = root / ".venv" / relative
    if interpreter.is_file() and Path(sys.prefix).resolve() != interpreter.parent.parent:
        return interpreter
    return None


def main():
    if interpreter := project_python():
        try:
            return subprocess.call([str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]])
        except KeyboardInterrupt:
            return 0

    if sys.argv[1:2] == ["runserver"] and not any(arg.startswith("--settings") for arg in sys.argv[2:]):
        parser = ArgumentParser(prog="python manage.py runserver")
        parser.add_argument("--legacy-port", type=int, default=8000)
        parser.add_argument("--lan", type=IPv4Address, help="Private IPv4 address of this PC; opens only the patched site.")
        args = parser.parse_args(sys.argv[2:])
        if args.lan is not None and not any(args.lan in IPv4Network(block) for block in (
            "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        )):
            parser.error("--lan requires a private LAN IPv4 address.")
        return run_servers(args.legacy_port, str(args.lan) if args.lan is not None else "127.0.0.1")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.patched")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
