from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from tempfile import gettempdir

from click.testing import CliRunner

from cagnotte.views_cli import cli
from cagnotte.web import create_app


TEST_DIR = Path(__file__).resolve().parent


class WebAppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        db_path = TEST_DIR / f"test_web_{uuid.uuid4().hex}.db"
        self.db_path = db_path
        self.app = create_app(f"sqlite:///{db_path.as_posix()}")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.app.extensions["cagnotte_engine"].dispose()
        if self.db_path.exists():
            self.db_path.unlink()

    def login(self, username: str, password: str):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def test_login_required_for_pots(self) -> None:
        response = self.client.get("/pots", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Connexion", response.get_data(as_text=True))

    def test_admin_can_create_pot(self) -> None:
        self.login("admin", "admin")
        response = self.client.get("/init-db", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        response = self.client.post("/pots", data={"name": "Voyage"}, follow_redirects=True)

        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Voyage", text)
        self.assertIn("Cagnotte creee", text)

    def test_user_cannot_create_or_delete_pot(self) -> None:
        self.login("admin", "admin")
        self.client.get("/init-db", follow_redirects=True)
        self.client.post("/pots", data={"name": "Weekend"}, follow_redirects=True)
        self.client.post("/logout", follow_redirects=True)

        self.login("user", "user")
        response_create = self.client.post("/pots", data={"name": "Interdit"}, follow_redirects=True)
        response_delete = self.client.post("/pots/1/delete", follow_redirects=True)

        self.assertEqual(response_create.status_code, 403)
        self.assertEqual(response_delete.status_code, 403)

    def test_expense_validation_feedback(self) -> None:
        self.login("admin", "admin")
        self.client.get("/init-db", follow_redirects=True)
        self.client.post("/pots", data={"name": "Roadtrip"}, follow_redirects=True)

        response = self.client.post(
            "/pots/1/expense",
            data={"paid_by": "Alice", "amount": "abc", "paid_at": "bad-date"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Le montant doit etre un nombre decimal valide.", response.get_data(as_text=True))


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        db_path = TEST_DIR / f"test_api_{uuid.uuid4().hex}.db"
        self.db_path = db_path
        self.app = create_app(f"sqlite:///{db_path.as_posix()}")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.app.extensions["cagnotte_engine"].dispose()
        if self.db_path.exists():
            self.db_path.unlink()

    def api_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def get_token(self, username: str, password: str) -> str:
        response = self.client.post("/api/tokens", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["token"]

    def test_api_requires_bearer_token(self) -> None:
        response = self.client.get("/api/pots")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Authentification Bearer requise.")

    def test_swagger_endpoints_exist(self) -> None:
        response_spec = self.client.get("/api/openapi.json")
        response_ui = self.client.get("/api/apidoc/swagger")

        self.assertEqual(response_spec.status_code, 200)
        self.assertEqual(response_spec.get_json()["openapi"], "3.0.3")
        self.assertEqual(response_ui.status_code, 200)
        self.assertIn("Swagger UI", response_ui.get_data(as_text=True))

    def test_api_admin_and_user_roles(self) -> None:
        admin_token = self.get_token("admin", "admin")
        user_token = self.get_token("user", "user")

        create_response = self.client.post(
            "/api/pots",
            json={"name": "Voyage API"},
            headers=self.api_headers(admin_token),
        )
        forbidden_response = self.client.post(
            "/api/pots",
            json={"name": "Interdit"},
            headers=self.api_headers(user_token),
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(forbidden_response.status_code, 403)
        self.assertEqual(forbidden_response.get_json()["error"], "Acces refuse.")

    def test_api_crud_expenses_and_balance(self) -> None:
        admin_token = self.get_token("admin", "admin")
        user_token = self.get_token("user", "user")

        pot_response = self.client.post(
            "/api/pots",
            json={"name": "Roadtrip API"},
            headers=self.api_headers(admin_token),
        )
        pot_id = pot_response.get_json()["id"]

        expense_a = self.client.post(
            f"/api/pots/{pot_id}/expenses",
            json={"paid_by": "Alice", "amount": "30.00", "paid_at": "2026-03-26T10:00:00"},
            headers=self.api_headers(user_token),
        )
        expense_b = self.client.post(
            f"/api/pots/{pot_id}/expenses",
            json={"paid_by": "Bob", "amount": "10.00", "paid_at": "2026-03-26T12:00:00"},
            headers=self.api_headers(user_token),
        )
        expense_b_id = expense_b.get_json()["id"]

        update_response = self.client.patch(
            f"/api/pots/{pot_id}/expenses/{expense_b_id}",
            json={"amount": "30.00"},
            headers=self.api_headers(user_token),
        )
        balance_response = self.client.get(
            f"/api/pots/{pot_id}/balance",
            headers=self.api_headers(user_token),
        )

        self.assertEqual(expense_a.status_code, 201)
        self.assertEqual(expense_b.status_code, 201)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["amount"], "30.00")
        self.assertEqual(balance_response.status_code, 200)
        self.assertEqual(balance_response.get_json()["transactions"], [])

    def test_api_rejects_duplicate_participant(self) -> None:
        admin_token = self.get_token("admin", "admin")
        pot_response = self.client.post(
            "/api/pots",
            json={"name": "Doublon"},
            headers=self.api_headers(admin_token),
        )
        pot_id = pot_response.get_json()["id"]

        self.client.post(
            f"/api/pots/{pot_id}/expenses",
            json={"paid_by": "Alice", "amount": "15.00"},
            headers=self.api_headers(admin_token),
        )
        duplicate_response = self.client.post(
            f"/api/pots/{pot_id}/expenses",
            json={"paid_by": "Alice", "amount": "20.00"},
            headers=self.api_headers(admin_token),
        )

        self.assertEqual(duplicate_response.status_code, 400)
        self.assertIn("Une seule depense par participant", duplicate_response.get_json()["error"])


class CliTestCase(unittest.TestCase):
    def test_cli_smoke_flow(self) -> None:
        runner = CliRunner()
        db_path = Path(gettempdir()) / f"cagnotte_cli_{uuid.uuid4().hex}.db"
        db_url = f"sqlite:///{db_path.as_posix()}"
        try:
            result_init = runner.invoke(cli, ["--db", db_url, "init-db"])
            result_create = runner.invoke(cli, ["--db", db_url, "create", "Weekend"])
            result_list = runner.invoke(cli, ["--db", db_url, "get-all"])

            self.assertEqual(result_init.exit_code, 0)
            self.assertEqual(result_create.exit_code, 0)
            self.assertEqual(result_list.exit_code, 0)
            self.assertIn("Weekend", result_list.output)
        finally:
            try:
                db_path.unlink(missing_ok=True)
            except PermissionError:
                pass

if __name__ == "__main__":
    unittest.main()
