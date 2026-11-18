import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from .db import get_db

bp = Blueprint("tracker", __name__)

CATEGORIES = (
    "Food",
    "Transport",
    "Housing",
    "Utilities",
    "Healthcare",
    "Entertainment",
    "Shopping",
    "Education",
    "Travel",
    "Other",
)


def _parse_form():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "")
    spent_on = request.form.get("spent_on", "")
    notes = request.form.get("notes", "").strip()

    if not title or len(title) > 100:
        raise ValueError("Enter a title of 1 to 100 characters.")
    if category not in CATEGORIES:
        raise ValueError("Choose a category from the list.")
    try:
        amount = Decimal(request.form.get("amount", "").strip())
        if (
            not amount.is_finite()
            or amount <= 0
            or amount > Decimal("999999999.99")
            or amount != amount.quantize(Decimal("0.01"))
        ):
            raise ValueError
        amount_cents = int(amount.quantize(Decimal("0.01")) * 100)
    except (InvalidOperation, ValueError):
        raise ValueError("Enter an amount greater than 0 with up to 2 decimal places.")

    try:
        parsed_date = date.fromisoformat(spent_on)
    except ValueError:
        raise ValueError("Enter a valid expense date.")
    if parsed_date.isoformat() != spent_on:
        raise ValueError("Enter a valid expense date.")
    if len(notes) > 500:
        raise ValueError("Notes must be 500 characters or fewer.")

    return title, amount_cents, category, spent_on, notes


def _expense_filters():
    conditions = []
    values = []
    month = request.args.get("month", "").strip()
    category = request.args.get("category", "").strip()
    search = request.args.get("q", "").strip()

    if month:
        try:
            year, month_number = (int(part) for part in month.split("-"))
            date(year, month_number, 1)
        except (ValueError, TypeError):
            month = ""
        else:
            conditions.append("substr(spent_on, 1, 7) = ?")
            values.append(month)
    if category in CATEGORIES:
        conditions.append("category = ?")
        values.append(category)
    else:
        category = ""
    if search:
        conditions.append("(title LIKE ? OR notes LIKE ?)")
        values.extend((f"%{search}%", f"%{search}%"))

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, values, {"month": month, "category": category, "q": search}


@bp.route("/")
def index():
    db = get_db()
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    month_next = (
        today.replace(year=today.year + 1, month=1, day=1).isoformat()
        if today.month == 12
        else today.replace(month=today.month + 1, day=1).isoformat()
    )
    month_summary = db.execute(
        """
        SELECT COALESCE(SUM(amount_cents), 0) AS total, COUNT(*) AS count
        FROM expenses WHERE spent_on >= ? AND spent_on < ?
        """,
        (month_start, month_next),
    ).fetchone()
    overall_total = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM expenses"
    ).fetchone()[0]
    recent = db.execute(
        "SELECT * FROM expenses ORDER BY spent_on DESC, id DESC LIMIT 6"
    ).fetchall()
    category_totals = db.execute(
        """
        SELECT category, SUM(amount_cents) AS total
        FROM expenses WHERE spent_on >= ? AND spent_on < ?
        GROUP BY category ORDER BY total DESC
        """,
        (month_start, month_next),
    ).fetchall()

    months = []
    year, month_number = today.year, today.month
    for _ in range(6):
        months.append(f"{year:04d}-{month_number:02d}")
        month_number -= 1
        if month_number == 0:
            year -= 1
            month_number = 12
    months.reverse()
    trend_rows = db.execute(
        """
        SELECT substr(spent_on, 1, 7) AS month, SUM(amount_cents) AS total
        FROM expenses WHERE substr(spent_on, 1, 7) >= ?
        GROUP BY month ORDER BY month
        """,
        (months[0],),
    ).fetchall()
    totals_by_month = {row["month"]: row["total"] for row in trend_rows}
    monthly_trend = [
        {"month": month, "total": totals_by_month.get(month, 0)} for month in months
    ]
    max_month_total = max((item["total"] for item in monthly_trend), default=0)

    return render_template(
        "index.html",
        month_total=month_summary["total"],
        month_count=month_summary["count"],
        overall_total=overall_total,
        recent=recent,
        category_totals=category_totals,
        monthly_trend=monthly_trend,
        max_month_total=max_month_total,
        current_month=today.strftime("%B %Y"),
    )


@bp.route("/expenses")
def expenses():
    where_clause, values, filters = _expense_filters()
    rows = get_db().execute(
        f"SELECT * FROM expenses{where_clause} ORDER BY spent_on DESC, id DESC",
        values,
    ).fetchall()
    return render_template(
        "expenses.html", expenses=rows, categories=CATEGORIES, filters=filters
    )


@bp.route("/expenses/new", methods=("GET", "POST"))
def create_expense():
    form_data = {
        "title": "",
        "amount": "",
        "category": CATEGORIES[0],
        "spent_on": date.today().isoformat(),
        "notes": "",
    }
    if request.method == "POST":
        form_data.update(request.form)
        try:
            values = _parse_form()
        except ValueError as error:
            flash(str(error), "error")
        else:
            get_db().execute(
                """
                INSERT INTO expenses (title, amount_cents, category, spent_on, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                values,
            )
            get_db().commit()
            flash("Expense added.", "success")
            return redirect(url_for("tracker.expenses"))
    return render_template(
        "expense_form.html",
        heading="Add an expense",
        submit_label="Save expense",
        expense=form_data,
        categories=CATEGORIES,
    )


@bp.route("/expenses/<int:expense_id>/edit", methods=("GET", "POST"))
def edit_expense(expense_id):
    db = get_db()
    expense = db.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    if expense is None:
        return "Expense not found", 404

    form_data = dict(expense)
    form_data["amount"] = f"{expense['amount_cents'] / 100:.2f}"
    if request.method == "POST":
        form_data.update(request.form)
        try:
            values = _parse_form()
        except ValueError as error:
            flash(str(error), "error")
        else:
            db.execute(
                """
                UPDATE expenses
                SET title = ?, amount_cents = ?, category = ?, spent_on = ?, notes = ?
                WHERE id = ?
                """,
                (*values, expense_id),
            )
            db.commit()
            flash("Expense updated.", "success")
            return redirect(url_for("tracker.expenses"))
    return render_template(
        "expense_form.html",
        heading="Edit expense",
        submit_label="Save changes",
        expense=form_data,
        categories=CATEGORIES,
    )


@bp.route("/expenses/<int:expense_id>/delete", methods=("POST",))
def delete_expense(expense_id):
    db = get_db()
    result = db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    db.commit()
    if result.rowcount == 0:
        return "Expense not found", 404
    flash("Expense deleted.", "success")
    return redirect(url_for("tracker.expenses"))


@bp.route("/expenses/export.csv")
def export_expenses():
    where_clause, values, _filters = _expense_filters()
    rows = get_db().execute(
        f"""
        SELECT title, amount_cents, category, spent_on, notes
        FROM expenses{where_clause} ORDER BY spent_on DESC, id DESC
        """,
        values,
    ).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("Title", "Amount", "Category", "Date", "Notes"))
    for row in rows:
        writer.writerow(
            (
                row["title"],
                f"{row['amount_cents'] / 100:.2f}",
                row["category"],
                row["spent_on"],
                row["notes"],
            )
        )
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="expenses.csv"'
    return response
