"""Wait until PostgreSQL accepts TCP connections."""

from __future__ import annotations

import os
import socket
import time

# A bare TCP connect is not proof of readiness: a port-forwarding proxy (docker
# publishes ports that way) accepts the connection while the server behind it is
# still running initdb and the init scripts. So speak enough of the protocol to
# hear the server itself: send an SSLRequest, to which any live postmaster replies
# with a single 'S' or 'N' byte. An empty read means nobody is home yet.
SSL_REQUEST = (8).to_bytes(4, "big") + (80877103).to_bytes(4, "big")


def postgres_responds(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(SSL_REQUEST)
            return sock.recv(1) in (b"S", b"N")
    except OSError:
        return False


def main() -> None:
    host = os.environ.get("POSTGRES_HOST") or "localhost"
    port = int(os.environ.get("POSTGRES_PORT") or "5432")
    timeout_seconds = int(os.environ.get("POSTGRES_READY_TIMEOUT_SECONDS") or "60")
    deadline = time.monotonic() + timeout_seconds

    print(f"Waiting for PostgreSQL at {host}:{port}...")
    while time.monotonic() < deadline:
        if postgres_responds(host, port):
            return
        time.sleep(2)

    raise SystemExit(
        f"PostgreSQL did not become ready at {host}:{port} "
        f"within {timeout_seconds} seconds"
    )


if __name__ == "__main__":
    main()
