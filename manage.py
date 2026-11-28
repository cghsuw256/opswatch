from argparse import ArgumentParser
import os
import subprocess
import sys
from pathlib import Path
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


def run_servers(legacy_port):
    manage = Path(__file__).resolve()
    servers = []
    try:
        prepare(manage)
        server_env = {**os.environ, "DJANGO_RUNSERVER_HIDE_WARNING": "true"}
        for port, settings in ((legacy_port, "config.settings"), (8001, "config.patched")):
            command = [sys.executable, "-u", str(manage), "runserver", f"127.0.0.1:{port}",
                       f"--settings={settings}", "--insecure", "--noreload"]
            servers.append(subprocess.Popen(command, env=server_env))
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
        return run_servers(parser.parse_args(sys.argv[2:]).legacy_port)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.patched")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
