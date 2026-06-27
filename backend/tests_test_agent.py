import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import database
from app.agent import handle_turn, start_call


class AgentFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = TemporaryDirectory()
        cls.original_db_path = database.DB_PATH
        database.DB_PATH = Path(cls.temp_dir.name) / "test.sqlite3"

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls.original_db_path
        cls.temp_dir.cleanup()

    def setUp(self):
        database.init_db()

    def test_late_fee_turn_uses_due_tool_and_policy(self):
        call = start_call("CUST-1188", "inbound")
        result = handle_turn(
            call["call_id"],
            "CUST-1188",
            "Why was I charged a late fee?",
            "inbound",
        )
        self.assertEqual(result["intent"], "late_fee_question")
        self.assertTrue(
            any(item["tool"] == "get_customer_emi_status" for item in result["tool_trace"])
        )
        self.assertGreaterEqual(len(result["citations"]), 1)

    def test_angry_customer_escalates(self):
        call = start_call("CUST-1188", "inbound")
        result = handle_turn(
            call["call_id"],
            "CUST-1188",
            "This is ridiculous and unacceptable, I want a human.",
            "inbound",
        )
        self.assertEqual(result["resolution_status"], "escalated")
        self.assertIsNotNone(result["escalation_reason"])

    def test_refund_prompt_creates_ticket_and_handoff(self):
        call = start_call("CUST-1188", "inbound")
        result = handle_turn(
            call["call_id"],
            "CUST-1188",
            "I already paid and want a refund.",
            "inbound",
        )
        tools = [item["tool"] for item in result["tool_trace"]]
        self.assertEqual(result["intent"], "refund_or_dispute")
        self.assertIn("create_support_ticket", tools)
        self.assertIn("handoff_to_human", tools)
        self.assertEqual(result["resolution_status"], "escalated")


if __name__ == "__main__":
    unittest.main()
