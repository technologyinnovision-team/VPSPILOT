import unittest
from vpspilot.system.services import sanitize_service_name, list_services, control_service

class TestServices(unittest.TestCase):
    def test_sanitize_service_name(self):
        self.assertEqual(sanitize_service_name("cron"), "cron.service")
        self.assertEqual(sanitize_service_name("ssh.service"), "ssh.service")
        self.assertEqual(sanitize_service_name("user@1000.service"), "user@1000.service")

        with self.assertRaises(ValueError):
            sanitize_service_name("cron; rm -rf /")

    def test_list_services(self):
        services = list_services()
        self.assertIsInstance(services, list)
        self.assertGreater(len(services), 0)
        first = services[0]
        self.assertIn("name", first)
        self.assertIn("active", first)
        self.assertIn("sub", first)

    def test_disallowed_service_action(self):
        res = control_service("cron", "destroy_everything")
        self.assertFalse(res["success"])
        self.assertIn("not permitted", res["error"])

if __name__ == "__main__":
    unittest.main()
