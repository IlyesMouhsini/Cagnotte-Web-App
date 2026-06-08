from __future__ import annotations

import logging
import os
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .api import api_bp
from .auth import USERS, get_session_user, verify_credentials
from .data import (
    add_expense,
    create_money_pot,
    delete_money_pot,
    get_engine,
    get_money_pot,
    init_db,
    list_money_pots,
    remove_expense,
)
from .domain import compute_transactions
from .validation import parse_amount, parse_paid_at, parse_participant, validate_money_pot_name


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Connectez-vous pour continuer.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user is None or g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def create_app(db_url: str | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("CAGNOTTE_SECRET_KEY", "cagnotte-dev-secret")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["JSON_SORT_KEYS"] = False
    engine = get_engine(db_url) if db_url else get_engine()
    app.extensions["cagnotte_engine"] = engine
    init_db(engine)

    @app.before_request
    def load_user():
        g.user = get_session_user()

    @app.context_processor
    def inject_auth_context():
        return {
            "current_user": g.user,
            "is_admin": bool(g.user and g.user["role"] == "admin"),
            "api_tokens": {username: user["token"] for username, user in USERS.items()},
        }
    
    # Configuration de la traçabilité
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("archilog.log", encoding="utf-8") 
        ]
    )
    app.logger.info("Système de log initialisé dans archilog.log")

    @app.get("/")
    def home():
        if g.user is None:
            return redirect(url_for("login"))
        return redirect(url_for("pots"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = verify_credentials(username, password)
            if user is not None:
                session.clear()
                session["username"] = username
                app.logger.info("login success user=%s role=%s", username, user["role"])
                flash(f"Bienvenue {username}.", "success")
                target = request.args.get("next") or url_for("pots")
                return redirect(target)

            app.logger.warning("login failed user=%s", username or "<empty>")
            flash("Identifiants invalides.", "error")

        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        username = g.user["username"]
        session.clear()
        app.logger.info("logout user=%s", username)
        flash("Vous etes deconnecte.", "success")
        return redirect(url_for("login"))

    @app.get("/init-db")
    @role_required("admin")
    def web_init_db():
        init_db(engine)
        app.logger.info("db initialized by user=%s", g.user["username"])
        flash("Base initialisee.", "success")
        return redirect(url_for("pots"))

    @app.get("/pots")
    @login_required
    def pots():
        return render_template("pots.html", items=list_money_pots(engine))

    @app.post("/pots")
    @role_required("admin")
    def pots_create():
        try:
            name = validate_money_pot_name(request.form.get("name", ""))
            create_money_pot(engine, name)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            app.logger.info("money pot created by user=%s name=%s", g.user["username"], name)
            flash(f"Cagnotte creee: {name}.", "success")
        return redirect(url_for("pots"))

    @app.post("/pots/<int:money_pot_id>/delete")
    @role_required("admin")
    def pots_delete(money_pot_id: int):
        delete_money_pot(engine, money_pot_id)
        app.logger.info("money pot deleted by user=%s pot_id=%s", g.user["username"], money_pot_id)
        flash("Cagnotte supprimee.", "success")
        return redirect(url_for("pots"))

    @app.get("/pots/<int:money_pot_id>")
    @login_required
    def pot_detail(money_pot_id: int):
        mp = get_money_pot(engine, money_pot_id)
        return render_template(
            "pot_detail.html",
            mp=mp,
            txs=compute_transactions(mp),
            money_pot_id=money_pot_id,
        )

    @app.post("/pots/<int:money_pot_id>/expense")
    @login_required
    def expense_add(money_pot_id: int):
        try:
            paid_by = parse_participant(request.form.get("paid_by", ""))
            amount = parse_amount(request.form.get("amount", ""))
            paid_at = parse_paid_at(request.form.get("paid_at") or None)
            add_expense(engine, money_pot_id, paid_by, amount, paid_at)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            app.logger.info(
                "expense added by user=%s pot_id=%s participant=%s amount=%s",
                g.user["username"],
                money_pot_id,
                paid_by,
                amount,
            )
            flash("Depense ajoutee.", "success")
        return redirect(url_for("pot_detail", money_pot_id=money_pot_id))

    @app.post("/pots/<int:money_pot_id>/expense/delete")
    @login_required
    def expense_delete(money_pot_id: int):
        paid_by = request.form.get("paid_by", "").strip()
        if not paid_by:
            flash("Le participant est obligatoire.", "error")
            return redirect(url_for("pot_detail", money_pot_id=money_pot_id))
        remove_expense(engine, money_pot_id, paid_by)
        app.logger.info(
            "expense deleted by user=%s pot_id=%s participant=%s",
            g.user["username"],
            money_pot_id,
            paid_by,
        )
        flash("Depense supprimee.", "success")
        return redirect(url_for("pot_detail", money_pot_id=money_pot_id))

    @app.errorhandler(ValueError)
    def handle_value_error(exc: ValueError):
        app.logger.warning("validation error path=%s error=%s", request.path, exc)
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("pots"))

    @app.errorhandler(403)
    def forbidden(_exc):
        return render_template(
            "error.html",
            title="Acces refuse",
            message="Vous n'avez pas les droits pour cette action.",
        ), 403

    @app.errorhandler(404)
    def not_found(_exc):
        return render_template(
            "error.html",
            title="Introuvable",
            message="La ressource demandee est introuvable.",
        ), 404

    @app.errorhandler(500)
    def internal_error(exc):
        app.logger.exception("internal error path=%s", request.path, exc_info=exc)
        return render_template(
            "error.html",
            title="Erreur interne",
            message="Une erreur inattendue est survenue.",
        ), 500

    app.register_blueprint(api_bp)
    return app


def run() -> None:
    app = create_app()
    app.run(debug=True)
