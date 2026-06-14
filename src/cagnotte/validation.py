from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def validate_money_pot_name(raw_name: str) -> str:
    name = raw_name.strip()
    if not name:
        raise ValueError("Le nom de la cagnotte est obligatoire.")
    return name


def parse_participant(raw_paid_by: str) -> str:
    paid_by = raw_paid_by.strip()
    if not paid_by:
        raise ValueError("Le participant est obligatoire.")
    return paid_by


def parse_amount(raw_amount: str) -> Decimal:
    try:
        amount = Decimal(raw_amount)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Le montant doit etre un nombre decimal valide.") from exc
    if amount <= 0:
        raise ValueError("Le montant doit etre strictement positif.")
    return amount


def parse_paid_at(raw_paid_at: str | None) -> datetime:
    if not raw_paid_at:
        return datetime.now()
    try:
        return datetime.fromisoformat(raw_paid_at)
    except ValueError as exc:
        raise ValueError("La date doit respecter le format ISO (ex: 2026-03-26T12:00:00).") from exc
