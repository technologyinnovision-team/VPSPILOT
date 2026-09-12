"""
System Telemetry and Metrics Engine for VPSPilot
Captures real-time CPU, RAM, Disk, Network, and OS health.
"""

import time
import os
import platform
import psutil

# Previous network I/O counters for calculating transfer rates (KB/s)
_LAST_NET_TIME = 0.0
_LAST_NET_IO = None

def get_system_info() -> dict:
    """Returns general operating system and host information."""
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)

    # Distro name parsing
    distro = "Linux"
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass

    return {
        "hostname": platform.node(),
        "os": platform.system(),
        "distro": distro,
        "kernel": platform.release(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "uptime_seconds": uptime_seconds,
        "boot_time": int(boot_time)
    }

def get_cpu_metrics() -> dict:
    """Returns CPU usage overall and per core, plus load averages."""
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

    freq = psutil.cpu_freq()
    current_freq = round(freq.current, 1) if freq else 0.0

    return {
        "total_percent": cpu_percent,
        "cores": cpu_cores,
        "core_count": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True),
        "frequency_mhz": current_freq,
        "load_1m": round(load_avg[0], 2),
        "load_5m": round(load_avg[1], 2),
        "load_15m": round(load_avg[2], 2)
    }

def get_memory_metrics() -> dict:
    """Returns detailed RAM and Swap statistics."""
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()

    return {
        "ram": {
            "total": vm.total,
            "used": vm.used,
            "free": vm.free,
            "available": vm.available,
            "percent": vm.percent,
            "cached": getattr(vm, "cached", 0),
            "buffers": getattr(vm, "buffers", 0)
        },
        "swap": {
            "total": sm.total,
            "used": sm.used,
            "free": sm.free,
            "percent": sm.percent
        }
    }

def get_disk_metrics() -> list[dict]:
    """Returns usage for all relevant mounted filesystems."""
    disks = []
    seen_mounts = set()
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint in seen_mounts:
            continue
        # Skip special/read-only filesystems
        if part.fstype in ("squashfs", "tmpfs", "devtmpfs", "overlay", ""):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent
            })
            seen_mounts.add(part.mountpoint)
        except (PermissionError, OSError):
            continue
    return disks

def get_network_metrics() -> dict:
    """Returns network interface details and computed I/O rates."""
    global _LAST_NET_TIME, _LAST_NET_IO

    current_time = time.time()
    current_io = psutil.net_io_counters(pernic=False)
    net_if_addrs = psutil.net_if_addrs()
    net_if_stats = psutil.net_if_stats()

    rx_speed = 0.0
    tx_speed = 0.0

    if _LAST_NET_IO is not None and _LAST_NET_TIME > 0:
        dt = current_time - _LAST_NET_TIME
        if dt > 0.1:
            rx_speed = max(0.0, (current_io.bytes_recv - _LAST_NET_IO.bytes_recv) / dt)
            tx_speed = max(0.0, (current_io.bytes_sent - _LAST_NET_IO.bytes_sent) / dt)

    _LAST_NET_TIME = current_time
    _LAST_NET_IO = current_io

    interfaces = {}
    for iface, addrs in net_if_addrs.items():
        if iface == "lo":
            continue
        stats = net_if_stats.get(iface)
        is_up = stats.isup if stats else False
        speed = stats.speed if stats else 0

        ipv4_list = []
        ipv6_list = []
        for addr in addrs:
            if addr.family.name == "AF_INET":
                ipv4_list.append(addr.address)
            elif addr.family.name == "AF_INET6":
                ipv6_list.append(addr.address)

        interfaces[iface] = {
            "is_up": is_up,
            "speed_mbps": speed,
            "ipv4": ipv4_list,
            "ipv6": ipv6_list
        }

    return {
        "bytes_sent": current_io.bytes_sent,
        "bytes_recv": current_io.bytes_recv,
        "tx_rate_bps": round(tx_speed, 1),
        "rx_rate_bps": round(rx_speed, 1),
        "interfaces": interfaces
    }

def get_telemetry_snapshot() -> dict:
    """Returns an integrated telemetry snapshot for dashboard consumption."""
    return {
        "timestamp": time.time(),
        "system": get_system_info(),
        "cpu": get_cpu_metrics(),
        "memory": get_memory_metrics(),
        "disks": get_disk_metrics(),
        "network": get_network_metrics()
    }
