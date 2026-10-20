"""Encrypted, durable OAuth rotation. Caller must hold the database lease."""

import json
import os
from urllib.parse import urlencode

import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken

from .storage import timestamp, tokens


class OAuth:
    def __init__(self, store, client):
        self.store, self.client = store, client
        try:
            self.fernet = Fernet(os.environ["TOKEN_ENCRYPTION_KEY"].encode())
        except (KeyError, ValueError):
            raise ValueError("Configure TOKEN_ENCRYPTION_KEY válida nos Secrets") from None

    def save(self, data):
        encrypted = self.fernet.encrypt(json.dumps(data).encode()).decode()
        self.store.upsert(tokens, tokens.c.provider == "meli", dict(provider="meli", ciphertext=encrypted))

    def access_token(self):
        rows = self.store.rows(sa.select(tokens).where(tokens.c.provider == "meli"))
        if rows:
            try:
                data = json.loads(self.fernet.decrypt(rows[0]["ciphertext"].encode()))
            except (InvalidToken, ValueError):
                raise ValueError("Não foi possível decifrar OAuth; confirme a chave original") from None
        else:
            refresh = os.getenv("MELI_REFRESH_TOKEN")
            if not refresh:
                raise ValueError("Conclua OAuth oficial e configure MELI_REFRESH_TOKEN inicial")
            data = {"refresh_token": refresh, "expires_at": 0, "state": "ready"}
        if data.get("state") != "ready":
            raise ValueError("Rotação OAuth interrompida; reautorize a conta e use oauth-reset")
        if data.get("expires_at", 0) > timestamp() + 60:
            return data["access_token"]
        app_id, app_secret = os.getenv("MELI_CLIENT_ID"), os.getenv("MELI_CLIENT_SECRET")
        if not app_id or not app_secret:
            raise ValueError("Configure MELI_CLIENT_ID e MELI_CLIENT_SECRET")
        # Single-use refresh tokens cannot be retried after an ambiguous network failure.
        self.save({"state": "refreshing"})
        response = self.client.request(
            "https://api.mercadolibre.com/oauth/token",
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=urlencode(
                {
                    "grant_type": "refresh_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "refresh_token": data["refresh_token"],
                }
            ).encode(),
        )
        if not isinstance(response, dict) or not all(
            isinstance(response.get(k), str) and response[k] for k in ("access_token", "refresh_token")
        ):
            raise ValueError("Resposta OAuth incompleta; reautorização necessária")
        expires = response.get("expires_in", 0)
        if type(expires) is not int or not 120 <= expires <= 86400:
            raise ValueError("Validade OAuth inválida")
        self.save(
            dict(
                state="ready",
                access_token=response["access_token"],
                refresh_token=response["refresh_token"],
                expires_at=timestamp() + expires,
            )
        )
        return response["access_token"]
