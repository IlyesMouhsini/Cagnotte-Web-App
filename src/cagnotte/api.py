from __future__ import annotations

from functools import wraps

from flask import Blueprint, abort, current_app, jsonify, make_response
from flask_httpauth import HTTPTokenAuth
from pydantic import BaseModel, ConfigDict, Field
from spectree.page import PAGE_TEMPLATES
from spectree import Response, SecurityScheme, SpecTree
from werkzeug.exceptions import HTTPException

from .auth import verify_credentials, verify_token
from .data import (
    add_expense,
    create_money_pot,
    delete_money_pot,
    get_expense,
    get_money_pot,
    list_money_pots,
    remove_expense_by_id,
    update_expense,
    update_money_pot,
)
from .domain import compute_transactions
from .validation import parse_amount, parse_paid_at, parse_participant, validate_money_pot_name


api_bp = Blueprint("api", __name__, url_prefix="/api")
api_spec = SpecTree(
    "flask",
    app=api_bp,
    validation_error_status=400,
    openapi_version="3.0.3",
    security_schemes=[
        SecurityScheme(
            name="bearer_token",
            data={"type": "http", "scheme": "bearer"},
        )
    ],
    security=[{"bearer_token": []}],
)
auth = HTTPTokenAuth(scheme="Bearer")


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(ApiModel):
    error: str
    status: int


class TokenRequest(ApiModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=40)


class TokenResponse(ApiModel):
    token: str
    username: str
    role: str


class MoneyPotPayload(ApiModel):
    name: str = Field(min_length=1, max_length=80)


class ExpenseCreatePayload(ApiModel):
    paid_by: str = Field(min_length=1, max_length=80)
    amount: str
    paid_at: str | None = None


class ExpenseUpdatePayload(ApiModel):
    paid_by: str | None = Field(default=None, min_length=1, max_length=80)
    amount: str | None = None
    paid_at: str | None = None


class ExpenseResponse(ApiModel):
    id: int
    paid_by: str
    amount: str
    paid_at: str


class TransactionResponse(ApiModel):
    debtor: str
    creditor: str
    amount: str


class MoneyPotResponse(ApiModel):
    id: int
    name: str
    expenses: list[ExpenseResponse]
    transactions: list[TransactionResponse]


class MoneyPotListItem(ApiModel):
    id: int
    name: str


class MoneyPotListResponse(ApiModel):
    items: list[MoneyPotListItem]


class ExpenseListResponse(ApiModel):
    items: list[ExpenseResponse]


class DeleteResponse(ApiModel):
    deleted: bool
    id: int


def _engine():
    return current_app.extensions["cagnotte_engine"]


def _json_error(message: str, status_code: int):
    response = jsonify({"error": message, "status": status_code})
    response.status_code = status_code
    return response


@auth.verify_token
def verify_bearer_token(token: str):
    return verify_token(token)


@auth.error_handler
def handle_auth_error(status_code: int):
    return _json_error("Authentification Bearer requise.", status_code)


def role_required(*roles: str):
    def decorator(view):
        @wraps(view)
        @auth.login_required
        def wrapped(*args, **kwargs):
            user = auth.current_user()
            if user is None or user["role"] not in roles:
                return _json_error("Acces refuse.", 403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _serialize_expense(expense) -> dict[str, object]:
    return {
        "id": expense.id,
        "paid_by": expense.paid_by,
        "amount": str(expense.amount),
        "paid_at": expense.paid_at.isoformat(),
    }


def _serialize_transaction(tx) -> dict[str, str]:
    return {
        "debtor": tx.debtor,
        "creditor": tx.creditor,
        "amount": str(tx.amount),
    }


def _serialize_money_pot(money_pot_id: int) -> dict[str, object]:
    money_pot = get_money_pot(_engine(), money_pot_id)
    return {
        "id": money_pot_id,
        "name": money_pot.name,
        "expenses": [_serialize_expense(expense) for expense in money_pot.expenses],
        "transactions": [_serialize_transaction(tx) for tx in compute_transactions(money_pot)],
    }


def _load_money_pot_or_404(money_pot_id: int) -> dict[str, object]:
    try:
        return _serialize_money_pot(money_pot_id)
    except ValueError as exc:
        abort(404, description=str(exc))


def _swagger_html() -> str:
    spec_path = f"{api_bp.url_prefix}/{api_spec.config.path}".strip("/")
    return PAGE_TEMPLATES["swagger"].format(
        spec_url=f"/{spec_path}/{api_spec.config.filename}",
        spec_path=spec_path,
        client_id="",
        client_secret="",
        realm="",
        app_name="",
        scope_separator=" ",
        additional_query_string_params={},
        use_basic_authentication_with_access_code_grant="false",
        use_pkce_with_authorization_code_grant="false",
    )


@api_bp.errorhandler(ValueError)
def handle_value_error(exc: ValueError):
    return _json_error(str(exc), 400)


@api_bp.errorhandler(HTTPException)
def handle_http_exception(exc: HTTPException):
    return _json_error(exc.description, exc.code or 500)


@api_bp.errorhandler(Exception)
def handle_exception(exc: Exception):
    current_app.logger.exception("api error path=%s", exc_info=exc)
    return _json_error("Une erreur inattendue est survenue.", 500)


@api_bp.get("/openapi.json")
def openapi_json():
    return jsonify(api_spec.spec)


@api_bp.get("/apidoc/swagger")
def swagger_ui_alias():
    return make_response(_swagger_html())


@api_bp.post("/tokens")
@api_spec.validate(
    json=TokenRequest,
    resp=Response(HTTP_200=TokenResponse, HTTP_401=ErrorResponse),
    tags=["api"],
    security=[],
)
def create_token(json: TokenRequest):
    user = verify_credentials(json.username, json.password)
    if user is None:
        return {"error": "Identifiants invalides.", "status": 401}, 401
    return {"token": user["token"], "username": user["username"], "role": user["role"]}


@api_bp.get("/pots")
@auth.login_required
@api_spec.validate(resp=Response(HTTP_200=MoneyPotListResponse, HTTP_401=ErrorResponse), tags=["api"])
def pots_list():
    return {"items": [{"id": money_pot_id, "name": name} for money_pot_id, name in list_money_pots(_engine())]}


@api_bp.post("/pots")
@role_required("admin")
@api_spec.validate(
    json=MoneyPotPayload,
    resp=Response(HTTP_201=MoneyPotResponse, HTTP_400=ErrorResponse, HTTP_401=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["api"],
)
def pots_create(json: MoneyPotPayload):
    name = validate_money_pot_name(json.name)
    money_pot_id = create_money_pot(_engine(), name)
    return _serialize_money_pot(money_pot_id), 201


@api_bp.get("/pots/<int:money_pot_id>")
@auth.login_required
@api_spec.validate(resp=Response(HTTP_200=MoneyPotResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse), tags=["api"])
def pots_get(money_pot_id: int):
    return _load_money_pot_or_404(money_pot_id)


@api_bp.patch("/pots/<int:money_pot_id>")
@role_required("admin")
@api_spec.validate(
    json=MoneyPotPayload,
    resp=Response(HTTP_200=MoneyPotResponse, HTTP_400=ErrorResponse, HTTP_401=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["api"],
)
def pots_update(money_pot_id: int, json: MoneyPotPayload):
    update_money_pot(_engine(), money_pot_id, validate_money_pot_name(json.name))
    return _serialize_money_pot(money_pot_id)


@api_bp.delete("/pots/<int:money_pot_id>")
@role_required("admin")
@api_spec.validate(resp=Response(HTTP_200=DeleteResponse, HTTP_401=ErrorResponse, HTTP_403=ErrorResponse), tags=["api"])
def pots_delete(money_pot_id: int):
    _load_money_pot_or_404(money_pot_id)
    delete_money_pot(_engine(), money_pot_id)
    return {"deleted": True, "id": money_pot_id}


@api_bp.get("/pots/<int:money_pot_id>/expenses")
@auth.login_required
@api_spec.validate(resp=Response(HTTP_200=ExpenseListResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse), tags=["api"])
def expenses_list(money_pot_id: int):
    money_pot = _load_money_pot_or_404(money_pot_id)
    return {"items": money_pot["expenses"]}


@api_bp.post("/pots/<int:money_pot_id>/expenses")
@auth.login_required
@api_spec.validate(
    json=ExpenseCreatePayload,
    resp=Response(HTTP_201=ExpenseResponse, HTTP_400=ErrorResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse),
    tags=["api"],
)
def expenses_create(money_pot_id: int, json: ExpenseCreatePayload):
    _load_money_pot_or_404(money_pot_id)
    expense_id = add_expense(
        _engine(),
        money_pot_id,
        parse_participant(json.paid_by),
        parse_amount(json.amount),
        parse_paid_at(json.paid_at),
    )
    return _serialize_expense(get_expense(_engine(), money_pot_id, expense_id)), 201


@api_bp.get("/pots/<int:money_pot_id>/expenses/<int:expense_id>")
@auth.login_required
@api_spec.validate(resp=Response(HTTP_200=ExpenseResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse), tags=["api"])
def expenses_get(money_pot_id: int, expense_id: int):
    _load_money_pot_or_404(money_pot_id)
    return _serialize_expense(get_expense(_engine(), money_pot_id, expense_id))


@api_bp.patch("/pots/<int:money_pot_id>/expenses/<int:expense_id>")
@auth.login_required
@api_spec.validate(
    json=ExpenseUpdatePayload,
    resp=Response(HTTP_200=ExpenseResponse, HTTP_400=ErrorResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse),
    tags=["api"],
)
def expenses_update(money_pot_id: int, expense_id: int, json: ExpenseUpdatePayload):
    _load_money_pot_or_404(money_pot_id)
    current = get_expense(_engine(), money_pot_id, expense_id)
    paid_by = parse_participant(json.paid_by if json.paid_by is not None else current.paid_by)
    amount = parse_amount(json.amount if json.amount is not None else str(current.amount))
    paid_at = parse_paid_at(json.paid_at if json.paid_at is not None else current.paid_at.isoformat())
    update_expense(_engine(), money_pot_id, expense_id, paid_by, amount, paid_at)
    return _serialize_expense(get_expense(_engine(), money_pot_id, expense_id))


@api_bp.delete("/pots/<int:money_pot_id>/expenses/<int:expense_id>")
@auth.login_required
@api_spec.validate(resp=Response(HTTP_200=DeleteResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse), tags=["api"])
def expenses_delete(money_pot_id: int, expense_id: int):
    _load_money_pot_or_404(money_pot_id)
    get_expense(_engine(), money_pot_id, expense_id)
    remove_expense_by_id(_engine(), money_pot_id, expense_id)
    return {"deleted": True, "id": expense_id}


@api_bp.get("/pots/<int:money_pot_id>/balance")
@auth.login_required
@api_spec.validate(resp=Response(HTTP_200=MoneyPotResponse, HTTP_401=ErrorResponse, HTTP_404=ErrorResponse), tags=["api"])
def balance_get(money_pot_id: int):
    return _load_money_pot_or_404(money_pot_id)
