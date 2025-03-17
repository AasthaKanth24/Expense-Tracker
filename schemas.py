# schemas.py (corrected)
from pydantic import BaseModel, constr
from datetime import date
from typing import Optional


class UserBase(BaseModel):
    username: constr(min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str


class UserLogin(UserBase):
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Expense(BaseModel):
    category: str
    amount: float
    date: date
    user_id: Optional[str] = None

    class Config:
        from_attributes = True


class ExpenseLimit(BaseModel):
    salary: float
    limit: float
    user_id: Optional[str] = None

    class Config:
        from_attributes = True


class RecurringExpenseSchema(BaseModel):
    category: str
    amount: float
    frequency: str
    start_date: date
    end_date: Optional[date] = None

    class Config:
        from_attributes = True


class RecurringExpenseResponse(RecurringExpenseSchema):
    id: int
    user_id: str
    next_due_date: date

    class Config:
        from_attributes = True


class CategoryTrend(BaseModel):
    category: str
    month: str
    total: float

    class Config:
        from_attributes = True
