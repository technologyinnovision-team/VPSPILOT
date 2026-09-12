import unittest
from vpspilot.system.metrics import (
    get_system_info,
    get_cpu_metrics,
    get_memory_metrics,
    get_disk_metrics,
    get_network_metrics,
    get_telemetry_snapshot
)

class TestMetrics(unittest.TestCase):
    def test_system_info(self):
        info = get_system_info()
        self.assertIn("hostname", info)
        self.assertIn("os", info)
        self.assertIn("kernel", info)
        self.assertIn("uptime_seconds", info)
        self.assertGreater(info["uptime_seconds"], 0)

    def test_cpu_metrics(self):
        cpu = get_cpu_metrics()
        self.assertIn("total_percent", cpu)
        self.assertIn("cores", cpu)
        self.assertIn("core_count", cpu)
        self.assertGreater(cpu["core_count"], 0)
        self.assertIsInstance(cpu["cores"], list)

    def test_memory_metrics(self):
        mem = get_memory_metrics()
        self.assertIn("ram", mem)
        self.assertIn("swap", mem)
        self.assertIn("total", mem["ram"])
        self.assertIn("percent", mem["ram"])
        self.assertGreater(mem["ram"]["total"], 0)

    def test_disk_metrics(self):
        disks = get_disk_metrics()
        self.assertIsInstance(disks, list)
        self.assertGreater(len(disks), 0)
        root = disks[0]
        self.assertIn("mountpoint", root)
        self.assertIn("total", root)

    def test_telemetry_snapshot(self):
        snapshot = get_telemetry_snapshot()
        self.assertIn("system", snapshot)
        self.assertIn("cpu", snapshot)
        self.assertIn("memory", snapshot)
        self.assertIn("disks", snapshot)
        self.assertIn("network", snapshot)

if __name__ == "__main__":
    unittest.main()
