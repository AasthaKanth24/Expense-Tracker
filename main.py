# main.py (updated with scheduler)
from fastapi import FastAPI
from router import router
from auth import auth_router
from database import Base, engine
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from dateutil.relativedelta import relativedelta
from database import SessionLocal, RecurringExpense, Transaction

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Budget Tracker API")


# Add scheduler for recurring expenses
def generate_recurring_transactions():
    with SessionLocal() as db:
        recurring_expenses = (
            db.query(RecurringExpense)
            .filter(RecurringExpense.next_due_date <= datetime.today().date())
            .all()
        )

        for expense in recurring_expenses:
            # Create transaction
            transaction = Transaction(
                category=expense.category,
                amount=expense.amount,
                date=expense.next_due_date,
                user_id=expense.user_id,
            )
            db.add(transaction)

            # Update next due date
            if expense.frequency == "daily":
                delta = relativedelta(days=+1)
            elif expense.frequency == "weekly":
                delta = relativedelta(weeks=+1)
            elif expense.frequency == "monthly":
                delta = relativedelta(months=+1)
            elif expense.frequency == "yearly":
                delta = relativedelta(years=+1)

            new_date = expense.next_due_date + delta
            if expense.end_date and new_date > expense.end_date:
                db.delete(expense)
            else:
                expense.next_due_date = new_date

        db.commit()


scheduler = BackgroundScheduler()
scheduler.add_job(
    generate_recurring_transactions, "cron", hour=0, minute=0
)  # Run daily at midnight
scheduler.start()

app.include_router(router, prefix="/api", tags=["expenses"])
app.include_router(auth_router, prefix="/auth", tags=["authentication"])


@app.get("/")
def home():
    return {"message": "Welcome to Personal Budget Tracker API"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
