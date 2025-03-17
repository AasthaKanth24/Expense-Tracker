# database.py (corrected)
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Date,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import date
import os

DATABASE_URL = "sqlite:///./budget.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, unique=True, index=True)
    password = Column(String, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String, index=True)
    amount = Column(Float)
    date = Column(Date)
    user_id = Column(String, ForeignKey("users.username"), nullable=False)


class Expense_Limit(Base):
    __tablename__ = "expense_limit"
    user_id = Column(
        String, ForeignKey("users.username"), primary_key=True, nullable=False
    )
    salary = Column(Float)
    limit = Column(Float)


class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.username"), nullable=False)
    category = Column(String)
    amount = Column(Float)
    frequency = Column(String)
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)
    next_due_date = Column(Date)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
