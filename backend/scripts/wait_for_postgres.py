"""Wait until PostgreSQL accepts TCP connections."""

from __future__ import annotations

import os
import socket
import time


def main() -> None:
    host = os.environ.get("POSTGRES_HOST") or "localhost"
    port = int(os.environ.get("POSTGRES_PORT") or "5432")
    timeout_seconds = int(os.environ.get("POSTGRES_READY_TIMEOUT_SECONDS") or "60")
    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None

    print(f"Waiting for PostgreSQL at {host}:{port}...")
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(2)

    raise SystemExit(
        f"PostgreSQL did not become reachable at {host}:{port}: {last_error}"
    )


if __name__ == "__main__":
    main()
