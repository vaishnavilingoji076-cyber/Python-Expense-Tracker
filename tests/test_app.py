import csv
import io
import tempfile
import unittest
from pathlib import Path

from expense_tracker import create_app


class ExpenseTrackerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "DATABASE": str(Path(self.temp_dir.name) / "test.sqlite3"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_expense(self, **overrides):
        data = {
            "title": "Market",
            "amount": "125.50",
            "category": "Food",
            "spent_on": "2026-03-10",
            "notes": "Weekly groceries",
        }
        data.update(overrides)
        return self.client.post("/expenses/new", data=data, follow_redirects=True)

    def test_create_and_view_expense(self):
        response = self.add_expense()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Expense added.", response.data)
        self.assertIn(b"Market", response.data)
        self.assertIn(b"125.50", response.data)

    def test_edit_and_delete_expense(self):
        self.add_expense()
        with self.app.app_context():
            from expense_tracker.db import get_db

            expense_id = get_db().execute("SELECT id FROM expenses").fetchone()["id"]

        response = self.client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "title": "Market and cafe",
                "amount": "150.00",
                "category": "Food",
                "spent_on": "2026-03-11",
                "notes": "",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Expense updated.", response.data)
        self.assertIn(b"150.00", response.data)
        response = self.client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=True
        )
        self.assertIn(b"Expense deleted.", response.data)
        self.assertIn(b"No matching expenses", response.data)

    def test_rejects_invalid_amount_and_category(self):
        response = self.add_expense(amount="-1")
        self.assertIn(b"Enter an amount greater than 0", response.data)
        response = self.add_expense(category="Unknown")
        self.assertIn(b"Choose a category from the list", response.data)
        with self.app.app_context():
            from expense_tracker.db import get_db

            count = get_db().execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        self.assertEqual(count, 0)

    def test_filters_expenses_and_exports_csv(self):
        self.add_expense()
        self.add_expense(
            title="Bus pass",
            amount="30.00",
            category="Transport",
            spent_on="2026-04-02",
            notes="",
        )
        response = self.client.get("/expenses?category=Food&month=2026-03")
        self.assertIn(b"Market", response.data)
        self.assertNotIn(b"Bus pass", response.data)

        response = self.client.get("/expenses/export.csv?category=Food&month=2026-03")
        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(response.mimetype, "text/csv")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "Market")
        self.assertEqual(rows[1][1], "125.50")

    def test_dashboard_renders_for_empty_and_populated_database(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your spending story starts here", response.data)
        self.add_expense()
        response = self.client.get("/")
        self.assertIn(b"By category", response.data)
        self.assertIn(b"Market", response.data)


if __name__ == "__main__":
    unittest.main()
