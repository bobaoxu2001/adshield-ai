from __future__ import annotations

import subprocess
import sys
import time


def main() -> None:
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.app.api:app", "--host", "127.0.0.1", "--port", "8000"])
    ui = subprocess.Popen(["npm", "run", "dev"])
    try:
        while api.poll() is None and ui.poll() is None:
            time.sleep(0.5)
    finally:
        api.terminate()
        ui.terminate()


if __name__ == "__main__":
    main()
