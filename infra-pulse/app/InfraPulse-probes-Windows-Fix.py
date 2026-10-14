"""Cross-platform ICMP monitoring without an asyncio subprocess requirement.

On Windows, Uvicorn's --reload mode can choose a SelectorEventLoop, which
cannot launch async subprocesses. Run the OS ping command in a worker thread
so the async monitoring loop remains responsive with or without --reload.
"""
from __future__ import annotations

import asyncio
import locale
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from statistics import mean

from .config import Target

# OS ping output differs between operating systems and locales. A successful
# exit code means a reply was received even if latency cannot be parsed.
RTT_PATTERN = re.compile(r"(?:time|χρόνος)\s*[=<]\s*([\d.,]+)\s*ms", re.I)


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


def _run_ping(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a single OS ping without shell interpolation or an asyncio subprocess."""
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=4,
        check=False,
        **kwargs,
    )


async def ping_once(host: str) -> tuple[bool, float | None]:
    if sys.platform == "win32":
        args = ["ping", "-n", "1", "-w", "1000", host]
    elif sys.platform == "darwin":
        args = ["ping", "-n", "-c", "1", "-W", "1000", host]
    else:
        args = ["ping", "-n", "-c", "1", "-W", "1", host]

    try:
        result = await asyncio.to_thread(_run_ping, args)
    except FileNotFoundError as exc:
        raise RuntimeError("OS ping executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Ping process timed out") from exc
    except PermissionError as exc:
        raise RuntimeError("OS ping is blocked by local permissions") from exc

    output = result.stdout or b""
    ping_text = output.decode(locale.getpreferredencoding(False), errors="replace")
    if result.returncode != 0:
        # Permission problems are instrumentation errors, not evidence that
        # the target is offline. A normal failed ping is instead a lost packet.
        low = ping_text.lower()
        if any(term in low for term in (
            "operation not permitted", "permission denied", "socket: operation",
            "access is denied", "access denied",
        )):
            raise RuntimeError("OS ping is blocked by local permissions or container capabilities")
        return False, None

    match = RTT_PATTERN.search(ping_text)
    latency_ms = float(match.group(1).replace(",", ".")) if match else None
    return True, latency_ms


async def probe_target(target: Target, count: int = 3) -> ProbeResult:
    if count < 1:
        raise ValueError("count must be at least 1")

    successful = 0
    rtts: list[float] = []
    try:
        for _ in range(count):
            alive, rtt = await ping_once(target.host)
            if alive:
                successful += 1
                if rtt is not None:
                    rtts.append(rtt)
    except (RuntimeError, OSError) as exc:
        # Some low-level errors (notably NotImplementedError) have no message.
        message = str(exc).strip() or type(exc).__name__
        return ProbeResult(target.name, target.host, "error", 100.0, None, message[:160])

    loss = round((1 - successful / count) * 100, 1)
    status = "down" if not successful else ("up" if successful == count else "degraded")
    latency_ms = round(mean(rtts), 2) if rtts else None
    return ProbeResult(target.name, target.host, status, loss, latency_ms)
