from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .domain import Expense, MoneyPot


DEFAULT_DB_URL = "sqlite:///data.db"


def get_engine(db_url: str = DEFAULT_DB_URL) -> Engine:
    return create_engine(db_url, future=True)


metadata = MetaData()

money_pots = Table(
    "money_pots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False, unique=True),
)

expenses = Table(
    "expenses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("money_pot_id", Integer, ForeignKey("money_pots.id", ondelete="CASCADE"), nullable=False),
    Column("paid_by", String, nullable=False),
    Column("amount", Numeric(10, 2), nullable=False),
    Column("paid_at", DateTime, nullable=False),
    UniqueConstraint("money_pot_id", "paid_by", name="uq_one_expense_per_person_per_pot"),
)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)


def create_money_pot(engine: Engine, name: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Le nom de cagnotte est vide.")
    stmt = insert(money_pots).values(name=name)
    with engine.begin() as conn:
        res = conn.execute(stmt)
        return int(res.inserted_primary_key[0])


def list_money_pots(engine: Engine) -> list[tuple[int, str]]:
    stmt = select(money_pots.c.id, money_pots.c.name).order_by(money_pots.c.name.asc())
    with engine.begin() as conn:
        rows = conn.execute(stmt).all()
    return [(int(r.id), str(r.name)) for r in rows]


def get_money_pot_id(engine: Engine, name: str) -> Optional[int]:
    stmt = select(money_pots.c.id).where(money_pots.c.name == name)
    with engine.begin() as conn:
        row = conn.execute(stmt).first()
    return int(row.id) if row else None


def update_money_pot(engine: Engine, money_pot_id: int, name: str) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Le nom de cagnotte est vide.")
    stmt = update(money_pots).where(money_pots.c.id == money_pot_id).values(name=name)
    with engine.begin() as conn:
        result = conn.execute(stmt)
    if result.rowcount == 0:
        raise ValueError(f"Cagnotte introuvable (id={money_pot_id}).")


def delete_money_pot(engine: Engine, money_pot_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(delete(expenses).where(expenses.c.money_pot_id == money_pot_id))
        conn.execute(delete(money_pots).where(money_pots.c.id == money_pot_id))


def add_expense(
    engine: Engine,
    money_pot_id: int,
    paid_by: str,
    amount: Decimal,
    paid_at: datetime,
) -> int:
    paid_by = paid_by.strip()
    if not paid_by:
        raise ValueError("Le nom du participant est vide.")
    if amount <= 0:
        raise ValueError("Le montant doit etre > 0.")

    stmt = insert(expenses).values(
        money_pot_id=money_pot_id,
        paid_by=paid_by,
        amount=amount,
        paid_at=paid_at,
    )
    try:
        with engine.begin() as conn:
            res = conn.execute(stmt)
            return int(res.inserted_primary_key[0])
    except IntegrityError as exc:
        raise ValueError("Une seule depense par participant est autorisee dans une cagnotte.") from exc


def remove_expense(engine: Engine, money_pot_id: int, paid_by: str) -> None:
    stmt = delete(expenses).where(
        (expenses.c.money_pot_id == money_pot_id) & (expenses.c.paid_by == paid_by)
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def remove_expense_by_id(engine: Engine, money_pot_id: int, expense_id: int) -> None:
    stmt = delete(expenses).where(
        (expenses.c.money_pot_id == money_pot_id) & (expenses.c.id == expense_id)
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def update_expense(
    engine: Engine,
    money_pot_id: int,
    expense_id: int,
    paid_by: str,
    amount: Decimal,
    paid_at: datetime,
) -> None:
    paid_by = paid_by.strip()
    if not paid_by:
        raise ValueError("Le nom du participant est vide.")
    if amount <= 0:
        raise ValueError("Le montant doit etre > 0.")

    stmt = (
        update(expenses)
        .where((expenses.c.money_pot_id == money_pot_id) & (expenses.c.id == expense_id))
        .values(paid_by=paid_by, amount=amount, paid_at=paid_at)
    )
    try:
        with engine.begin() as conn:
            result = conn.execute(stmt)
        if result.rowcount == 0:
            raise ValueError(f"Depense introuvable (id={expense_id}).")
    except IntegrityError as exc:
        raise ValueError("Une seule depense par participant est autorisee dans une cagnotte.") from exc


def get_expense(engine: Engine, money_pot_id: int, expense_id: int) -> Expense:
    stmt = (
        select(expenses.c.id, expenses.c.paid_by, expenses.c.amount, expenses.c.paid_at)
        .where((expenses.c.money_pot_id == money_pot_id) & (expenses.c.id == expense_id))
    )
    with engine.begin() as conn:
        row = conn.execute(stmt).mappings().first()
    if not row:
        raise ValueError(f"Depense introuvable (id={expense_id}).")
    return Expense(
        id=int(row["id"]),
        paid_by=str(row["paid_by"]),
        amount=Decimal(str(row["amount"])),
        paid_at=row["paid_at"],
    )


def list_expenses(engine: Engine, money_pot_id: int) -> list[Expense]:
    stmt = (
        select(expenses.c.id, expenses.c.paid_by, expenses.c.amount, expenses.c.paid_at)
        .where(expenses.c.money_pot_id == money_pot_id)
        .order_by(expenses.c.paid_at.asc(), expenses.c.paid_by.asc())
    )
    with engine.begin() as conn:
        rows = conn.execute(stmt).mappings().all()

    return [
        Expense(
            id=int(row["id"]),
            paid_by=str(row["paid_by"]),
            amount=Decimal(str(row["amount"])),
            paid_at=row["paid_at"],
        )
        for row in rows
    ]


def get_money_pot(engine: Engine, money_pot_id: int) -> MoneyPot:
    stmt = select(money_pots.c.name).where(money_pots.c.id == money_pot_id)
    with engine.begin() as conn:
        row = conn.execute(stmt).first()
    if not row:
        raise ValueError(f"Cagnotte introuvable (id={money_pot_id}).")

    return MoneyPot(name=str(row.name), expenses=list_expenses(engine, money_pot_id))
