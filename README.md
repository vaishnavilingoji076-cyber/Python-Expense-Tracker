# Pennywise Expense Tracker

A lightweight personal expense tracker built with Flask and SQLite. It runs locally and stores all records in `instance/expenses.sqlite3`.

## Features

- Dashboard with this month's total and transaction count, all-time spending, six-month trend, and category breakdown.
- Create, edit, and delete expenses with title, amount, category, date, and optional notes.
- Search transactions and filter by category or month.
- Export the current transaction list or filtered results to CSV.
- Responsive layout for desktop and mobile.
- CSRF protection on form submissions; no external database or account required.

## Run locally

1. Install Python 3.10 or later.
2. From this folder, create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies and start the app:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

4. Open <http://127.0.0.1:5000>.

The database is created automatically. For a different currency symbol, set `CURRENCY_SYMBOL` before starting the app (the default is `₹`). Set `SECRET_KEY` to a private random value when using the app beyond local development.

## Run tests

```powershell
python -m unittest discover -s tests -v
```
