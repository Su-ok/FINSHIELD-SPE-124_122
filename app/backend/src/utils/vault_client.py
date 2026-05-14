"""
FinShield - Vault Secrets Manager
Fetches secrets from HashiCorp Vault instead of env vars
"""

import os
import json
import logging
import hvac
from functools import lru_cache

logger = logging.getLogger("finshield.vault")


class VaultClient:
    """HashiCorp Vault client for secure secret retrieval."""

    def __init__(self):
        self.vault_addr = os.getenv("VAULT_ADDR", "http://vault:8200")
        self.vault_token = os.getenv("VAULT_TOKEN", "")
        self.vault_role = os.getenv("VAULT_ROLE", "finshield")
        self._client = None

    @property
    def client(self) -> hvac.Client:
        if self._client is None:
            self._client = hvac.Client(url=self.vault_addr, token=self.vault_token)
            if not self._client.is_authenticated():
                logger.warning("Vault token auth failed, trying AppRole...")
                self._approle_login()
        return self._client

    def _approle_login(self):
        role_id = os.getenv("VAULT_ROLE_ID", "")
        secret_id = os.getenv("VAULT_SECRET_ID", "")
        if role_id and secret_id:
            result = self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            self._client.token = result["auth"]["client_token"]
            logger.info("Vault AppRole login successful")

    def get_secret(self, path: str) -> dict:
        """Read a KV v2 secret from Vault."""
        try:
            secret = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point="secret"
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to read Vault secret at {path}: {e}")
            return {}

    def get_db_credentials(self) -> dict:
        secret = self.get_secret("finshield/database")
        return {
            "host": secret.get("host", os.getenv("DB_HOST", "postgres")),
            "port": int(secret.get("port", os.getenv("DB_PORT", "5432"))),
            "name": secret.get("name", os.getenv("DB_NAME", "finshield")),
            "user": secret.get("user", os.getenv("DB_USER", "finshield")),
            "password": secret.get("password", os.getenv("DB_PASSWORD", "changeme")),
        }

    def get_api_keys(self) -> dict:
        secret = self.get_secret("finshield/api-keys")
        return {
            "fraud_api_key": secret.get("fraud_api_key", os.getenv("FRAUD_API_KEY", "local-dev-key")),
            "jwt_secret": secret.get("jwt_secret", os.getenv("JWT_SECRET", "local-jwt-secret")),
        }


@lru_cache(maxsize=1)
def get_vault_client() -> VaultClient:
    return VaultClient()
