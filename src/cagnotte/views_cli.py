# src/cagnotte/views_cli.py
from __future__ import annotations

import click

from .data import (
    get_engine,
    init_db,
    create_money_pot,
    list_money_pots,
    delete_money_pot,
    add_expense,
    remove_expense,
    get_money_pot,
)
from .domain import compute_transactions, format_transactions
from .validation import parse_amount, parse_paid_at


@click.group()
@click.option("--db", "db_url", default=None, help="DB URL SQLAlchemy (ex: sqlite:///data.db)")
@click.pass_context
def cli(ctx: click.Context, db_url: str | None) -> None:
    """Cagnotte - CLI (Click)"""
    engine = get_engine(db_url) if db_url else get_engine()
    ctx.obj = {"engine": engine}


@cli.command("init-db")
@click.pass_context
def cmd_init_db(ctx: click.Context) -> None:
    engine = ctx.obj["engine"]
    init_db(engine)
    click.echo("Base initialisee.")


@cli.command("create")
@click.argument("name")
@click.pass_context
def cmd_create(ctx: click.Context, name: str) -> None:
    engine = ctx.obj["engine"]
    mp_id = create_money_pot(engine, name)
    click.echo(f"Cagnotte creee: id={mp_id}, name='{name}'")


@cli.command("get-all")
@click.pass_context
def cmd_get_all(ctx: click.Context) -> None:
    engine = ctx.obj["engine"]
    pots = list_money_pots(engine)
    if not pots:
        click.echo("Aucune cagnotte.")
        return
    for pid, name in pots:
        click.echo(f"- {pid}: {name}")


@cli.command("delete")
@click.argument("money_pot_id", type=int)
@click.pass_context
def cmd_delete(ctx: click.Context, money_pot_id: int) -> None:
    engine = ctx.obj["engine"]
    delete_money_pot(engine, money_pot_id)
    click.echo("Cagnotte supprimee.")


@cli.command("add-expense")
@click.argument("money_pot_id", type=int)
@click.option("--who", "paid_by", required=True, help="Participant")
@click.option("--amount", required=True, type=str, help="Montant (ex: 12.50)")
@click.option("--date", "paid_at", default=None, help="Date ISO (ex: 2026-02-26T12:00:00)")
@click.pass_context
def cmd_add_expense(ctx: click.Context, money_pot_id: int, paid_by: str, amount: str, paid_at: str | None) -> None:
    engine = ctx.obj["engine"]
    amt = parse_amount(amount)
    dt = parse_paid_at(paid_at)
    add_expense(engine, money_pot_id, paid_by, amt, dt)
    click.echo("Depense ajoutee.")


@cli.command("remove-expense")
@click.argument("money_pot_id", type=int)
@click.option("--who", "paid_by", required=True, help="Participant")
@click.pass_context
def cmd_remove_expense(ctx: click.Context, money_pot_id: int, paid_by: str) -> None:
    engine = ctx.obj["engine"]
    remove_expense(engine, money_pot_id, paid_by)
    click.echo("Depense supprimee (si existante).")


@cli.command("balance")
@click.argument("money_pot_id", type=int)
@click.pass_context
def cmd_balance(ctx: click.Context, money_pot_id: int) -> None:
    engine = ctx.obj["engine"]
    mp = get_money_pot(engine, money_pot_id)
    txs = compute_transactions(mp)
    click.echo(f"Cagnotte: {mp.name}")
    click.echo(format_transactions(txs))
