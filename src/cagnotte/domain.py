# src/cagnotte/domain.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


@dataclass(frozen=True)
class Expense:
    id: int | None
    paid_by: str
    amount: Decimal
    paid_at: datetime


@dataclass(frozen=True)
class MoneyPot:
    name: str
    expenses: list[Expense]


@dataclass(frozen=True)
class Transaction:
    debtor: str
    creditor: str
    amount: Decimal


def _q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_transactions(money_pot: MoneyPot) -> list[Transaction]:
    if not money_pot.expenses:
        return []

    by_person: dict[str, Decimal] = {}
    for expense in money_pot.expenses:
        by_person[expense.paid_by] = by_person.get(expense.paid_by, Decimal("0")) + expense.amount

    people = sorted(by_person.keys())
    total = sum(by_person.values(), Decimal("0"))
    avg = total / Decimal(len(people))
    balances: dict[str, Decimal] = {person: _q2(by_person[person] - avg) for person in people}

    creditors: list[tuple[str, Decimal]] = [(person, balance) for person, balance in balances.items() if balance > 0]
    debtors: list[tuple[str, Decimal]] = [(person, -balance) for person, balance in balances.items() if balance < 0]
    creditors.sort(key=lambda item: item[0])
    debtors.sort(key=lambda item: item[0])

    txs: list[Transaction] = []
    i = 0
    j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]

        amount = _q2(min(debt, credit))
        if amount > 0:
            txs.append(Transaction(debtor=debtor, creditor=creditor, amount=amount))

        debtors[i] = (debtor, _q2(debt - amount))
        creditors[j] = (creditor, _q2(credit - amount))

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return [tx for tx in txs if tx.amount > 0]


def format_transactions(txs: Iterable[Transaction]) -> str:
    txs = list(txs)
    if not txs:
        return "Aucune transaction : tout le monde est deja equilibre."
    return "\n".join(f"{tx.debtor} doit {tx.amount} EUR a {tx.creditor}" for tx in txs)
