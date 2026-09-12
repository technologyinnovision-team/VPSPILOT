import unittest
from vpspilot.config import hash_password, verify_password
from vpspilot.system.auth import create_session, validate_session, destroy_session, is_rate_limited, record_attempt

class TestAuth(unittest.TestCase):
    def test_password_hashing_and_verification(self):
        pwd = "SuperSecretPassword123!"
        hashed, salt = hash_password(pwd)
        self.assertTrue(len(hashed) > 0)
        self.assertTrue(len(salt) > 0)

        # Valid password
        self.assertTrue(verify_password(pwd, hashed, salt))

        # Invalid password
        self.assertFalse(verify_password("WrongPassword", hashed, salt))

    def test_session_lifecycle(self):
        token = create_session("admin", "127.0.0.1", ttl=60)
        self.assertTrue(validate_session(token))
        destroy_session(token)
        self.assertFalse(validate_session(token))

    def test_rate_limiting(self):
        test_ip = "192.168.99.99"
        self.assertFalse(is_rate_limited(test_ip))
        for _ in range(12):
            record_attempt(test_ip)
        self.assertTrue(is_rate_limited(test_ip))

if __name__ == "__main__":
    unittest.main()
