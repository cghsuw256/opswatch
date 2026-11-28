from argparse import ArgumentParser
import subprocess
import sys
from pathlib import Path
from time import sleep


def main(legacy_port):
    manage = Path(__file__).with_name("manage.py")
    servers = []
    try:
        for port, settings in ((legacy_port, "config.settings"), (8001, "config.patched")):
            command = [sys.executable, "-u", str(manage), "runserver", f"127.0.0.1:{port}",
                       f"--settings={settings}", "--insecure", "--noreload"]
            servers.append(subprocess.Popen(command))
        while True:
            for server in servers:
                status = server.poll()
                if status is not None:
                    return status or 1
            sleep(0.2)
    except KeyboardInterrupt:
        return 0
    finally:
        for server in servers:
            if server.poll() is None:
                server.terminate()
        for server in servers:
            server.wait()


if __name__ == "__main__":
    parser = ArgumentParser(description="Run both local OpsWatch presentation sites.")
    parser.add_argument("--legacy-port", type=int, default=8000)
    sys.exit(main(parser.parse_args().legacy_port))
