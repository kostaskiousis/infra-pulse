
"""Cross-platform ICMP monitoring compatible with Windows."""

from __future__ import annotations

import asyncio
import locale
import re
import subprocess
import sys

from dataclasses import asdict, dataclass
from statistics import mean

from .config import Target


RTT_PATTERN = re.compile(
    r"(?:time|χρόνος)\s*[=<]\s*([\d.,]+)\s*ms",
    re.IGNORECASE,
)


@dataclass
class ProbeResult:
    name: str
    host: str
    status: str
    packet_loss: float
    latency_ms: float | None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _run_ping(
    args: list[str],
) -> subprocess.CompletedProcess[bytes]:
    """Execute the OS ping command in a worker thread."""

    kwargs = {}

    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=4,
        check=False,
        **kwargs,
    )


async def ping_once(
    host: str,
) -> tuple[bool, float | None]:

    if sys.platform == "win32":
        args = [
            "ping", "-n", "1",
            "-w", "1000", host
        ]

    elif sys.platform == "darwin":
        args = [
            "ping", "-n", "-c", "1",
            "-W", "1000", host
        ]

    else:
        args = [
            "ping", "-n", "-c", "1",
            "-W", "1", host
        ]

    try:
        result = await asyncio.to_thread(
            _run_ping,
            args,
        )

    except FileNotFoundError as exc:
        raise RuntimeError(
            "OS ping executable was not found"
        ) from exc

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Ping process timed out"
        ) from exc

    except PermissionError as exc:
        raise RuntimeError(
            "OS ping is blocked by local permissions"
        ) from exc

    output = result.stdout or b""

    ping_text = output.decode(
        locale.getpreferredencoding(False),
        errors="replace",
    )

    if result.returncode != 0:
        low = ping_text.lower()

        permission_errors = (
            "operation not permitted",
            "permission denied",
            "socket: operation",
            "access is denied",
            "access denied",
        )

        if any(
            term in low
            for term in permission_errors
        ):
            raise RuntimeError(
                "OS ping is blocked by local permissions "
                "or container capabilities"
            )

        return False, None

    match = RTT_PATTERN.search(ping_text)

    latency_ms = (
        float(match.group(1).replace(",", "."))
        if match
        else None
    )

    return True, latency_ms


async def probe_target(
    target: Target,
    count: int = 3,
) -> ProbeResult:

    if count < 1:
        raise ValueError(
            "count must be at least 1"
        )

    successful = 0
    rtts: list[float] = []

    try:
        for _ in range(count):
            alive, rtt = await ping_once(
                target.host
            )

            if alive:
                successful += 1

                if rtt is not None:
                    rtts.append(rtt)

    except (RuntimeError, OSError) as exc:
        message = (
            str(exc).strip()
            or type(exc).__name__
        )

        return ProbeResult(
            name=target.name,
            host=target.host,
            status="error",
            packet_loss=100.0,
            latency_ms=None,
            error=message[:160],
        )

    loss = round(
        (1 - successful / count) * 100,
        1,
    )

    if successful == 0:
        status = "down"

    elif successful == count:
        status = "up"

    else:
        status = "degraded"

    latency_ms = (
        round(mean(rtts), 2)
        if rtts
        else None
    )

    return ProbeResult(
        name=target.name,
        host=target.host,
        status=status,
        packet_loss=loss,
        latency_ms=latency_ms,
    )
