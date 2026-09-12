"""
Process Management for VPSPilot
Inspects running processes, resource consumption, and allows signals (TERM, KILL).
"""

import os
import signal
import psutil

def list_processes(limit: int = 100, sort_by: str = "cpu_percent") -> list[dict]:
    """Returns top active processes sorted by CPU or Memory usage."""
    procs = []
    for p in psutil.process_iter(attrs=["pid", "name", "username", "cpu_percent", "memory_percent", "status", "cmdline"]):
        try:
            info = p.info
            cmdline = " ".join(info.get("cmdline") or [])
            if not cmdline:
                cmdline = f"[{info.get('name')}]"
            procs.append({
                "pid": info.get("pid"),
                "name": info.get("name"),
                "user": info.get("username", "unknown"),
                "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
                "memory_percent": round(info.get("memory_percent") or 0.0, 1),
                "status": info.get("status"),
                "cmdline": cmdline[:150]
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    reverse = True
    key = "cpu_percent"
    if sort_by == "memory_percent":
        key = "memory_percent"
    elif sort_by == "pid":
        key = "pid"
        reverse = False

    procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=reverse)
    return procs[:limit]

def signal_process(pid: int, sig_name: str = "SIGTERM") -> dict:
    """Sends a signal to a process."""
    if sig_name == "SIGKILL":
        sig = signal.SIGKILL
    elif sig_name == "SIGTERM":
        sig = signal.SIGTERM
    else:
        return {"success": False, "error": f"Unsupported signal: {sig_name}"}

    try:
        os.kill(pid, sig)
        return {"success": True, "pid": pid, "signal": sig_name, "message": f"Signal {sig_name} sent to PID {pid}"}
    except ProcessLookupError:
        return {"success": False, "error": f"No such process: {pid}"}
    except PermissionError:
        return {"success": False, "error": f"Permission denied to signal process {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
