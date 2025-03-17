from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, Transaction, Expense_Limit, RecurringExpense, User
from schemas import (
    Expense,
    ExpenseLimit,
    RecurringExpenseSchema,
    RecurringExpenseResponse,
    CategoryTrend,
)
from auth import get_current_user
from datetime import datetime, date
from typing import Optional
import csv
from io import StringIO


router = APIRouter()


@router.post("/expenses")
async def create_expense(
    expense: Expense,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Fetch user's expense limit and salary details
    expense_limit = (
        db.query(Expense_Limit)
        .filter(Expense_Limit.user_id == current_user.username)
        .first()
    )

    if not expense_limit:
        raise HTTPException(
            status_code=400, detail="Set an expense limit and salary first!"
        )

    # Check if the user has enough salary remaining
    if expense_limit.salary - expense.amount < 0:
        raise HTTPException(status_code=400, detail="Insufficient salary balance!")

    # Check if this expense will exceed the limit
    remaining_after_expense = expense_limit.salary - expense.amount
    warning_message = None

    if remaining_after_expense <= expense_limit.limit:
        warning_message = (
            "Warning: Your remaining salary is at or below your expense limit!"
        )

    # Deduct the transaction amount from the salary
    expense_limit.salary = remaining_after_expense

    # Add the expense to the transaction table
    db_expense = Transaction(
        category=expense.category,
        amount=expense.amount,
        date=expense.date,
        user_id=current_user.username,
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)

    # Prepare the response
    response = {"expense": db_expense}
    if warning_message:
        response["warning"] = warning_message

    return response


@router.get("/expenses")
async def get_expenses(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    expenses = (
        db.query(Transaction).filter(Transaction.user_id == current_user.username).all()
    )
    return expenses


@router.get("/expenses/{expense_id}")
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (
        db.query(Transaction)
        .filter(
            Transaction.id == expense_id, Transaction.user_id == current_user.username
        )
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = (
        db.query(Transaction)
        .filter(
            Transaction.id == expense_id, Transaction.user_id == current_user.username
        )
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"message": "Expense deleted successfully"}


@router.post("/expenses/expense-limit")
async def set_expense_limit(
    expense_limit: ExpenseLimit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if the user already has a limit set
    existing_limit = (
        db.query(Expense_Limit)
        .filter(Expense_Limit.user_id == current_user.username)
        .first()
    )

    if existing_limit:
        # Update the existing limit
        existing_limit.limit = expense_limit.limit
        existing_limit.salary = expense_limit.salary
    else:
        # Create a new limit entry
        db_expense_limit = Expense_Limit(
            user_id=current_user.username,
            salary=expense_limit.salary,
            limit=expense_limit.limit,
        )
        db.add(db_expense_limit)

    db.commit()
    return {"message": "Expense limit set successfully", "details": db_expense_limit}


# endpoints for recurring expenses
@router.post("/recurring-expenses", status_code=status.HTTP_201_CREATED)
async def create_recurring_expense(
    expense: RecurringExpenseSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate frequency
    allowed_frequencies = ["daily", "weekly", "monthly", "yearly"]
    if expense.frequency.lower() not in allowed_frequencies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid frequency. Allowed values: {allowed_frequencies}",
        )

    # Create database object
    db_recurring_expense = RecurringExpense(
        user_id=current_user.username,
        category=expense.category,
        amount=expense.amount,
        frequency=expense.frequency.lower(),
        start_date=expense.start_date,
        end_date=expense.end_date,
        next_due_date=expense.start_date,  # Initialize next_due_date
    )

    # Save to database
    db.add(db_recurring_expense)
    db.commit()
    db.refresh(db_recurring_expense)

    return db_recurring_expense


@router.get("/recurring-expenses", response_model=list[RecurringExpenseResponse])
async def get_recurring_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recurring_expenses = (
        db.query(RecurringExpense)
        .filter(RecurringExpense.user_id == current_user.username)
        .all()
    )

    if not recurring_expenses:
        return []

    return recurring_expenses


@router.get("/analytics/category-trends", response_model=list[CategoryTrend])
async def get_category_trends(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(
        Transaction.category,
        func.strftime("%Y-%m", Transaction.date).label("month"),
        func.sum(Transaction.amount).label("total"),
    ).filter(Transaction.user_id == current_user.username)

    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)

    trends = (
        query.group_by(Transaction.category, func.strftime("%Y-%m", Transaction.date))
        .order_by("month", Transaction.category)
        .all()
    )

    return [
        {"category": row.category, "month": row.month, "total": row.total or 0.0}
        for row in trends
    ]


@router.get("/export-report")
async def export_financial_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Exports financial report as CSV containing:
    - All transactions
    - Category-wise totals
    - Monthly trends
    """
    # Get all transactions for the user
    transactions = (
        db.query(Transaction).filter(Transaction.user_id == current_user.username).all()
    )

    # Create CSV content
    csv_data = StringIO()
    writer = csv.writer(csv_data)

    # Write header
    writer.writerow(["Date", "Category", "Amount", "User ID"])

    # Write transactions
    for t in transactions:
        writer.writerow([t.date, t.category, t.amount, t.user_id])

    # Add summary section
    writer.writerow([])
    writer.writerow(["Category", "Total Spending"])

    # Get category totals
    category_totals = (
        db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
        .filter(Transaction.user_id == current_user.username)
        .group_by(Transaction.category)
        .all()
    )

    for category, total in category_totals:
        writer.writerow([category, total])

    # Reset buffer position
    csv_data.seek(0)

    # Create streaming response
    response = StreamingResponse(
        iter([csv_data.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={current_user.username}_financial_report.csv"
        },
    )

    return response
