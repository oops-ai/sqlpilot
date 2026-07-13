import unittest

from src.services.realtime_service import RealtimeService


class RealtimeServiceTest(unittest.TestCase):
    def test_formats_sse_event(self):
        service = RealtimeService(connection_service=None)

        event = service._event("database_change", {"table": "workspaces", "operation": "INSERT"})

        self.assertIn("event: database_change", event)
        self.assertIn('"table": "workspaces"', event)
        self.assertTrue(event.endswith("\n\n"))

    def test_payload_parses_json_or_wraps_text(self):
        service = RealtimeService(connection_service=None)

        self.assertEqual({"table": "workspaces"}, service._payload('{"table":"workspaces"}'))
        self.assertEqual({"message": "raw"}, service._payload("raw"))


if __name__ == "__main__":
    unittest.main()
