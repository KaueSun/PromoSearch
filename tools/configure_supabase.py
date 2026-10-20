"""Run by the owner in a private terminal. No passwords or secret URLs are printed/saved.

The administrator password goes only to the specified Supabase PostgreSQL server.
Only radar_app's connection and a new encryption key go to GitHub environment Secrets.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote


class SetupError(RuntimeError):
    pass


CA_FILE = "certs/supabase-prod-ca-2021.crt"
CA_SHA256 = "700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7"


def certificate_path(root):
    path = root / CA_FILE
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != CA_SHA256:
        raise SetupError("Certificado oficial ausente ou diferente do revisado; restaure o arquivo do projeto.")
    return path


@contextmanager
def database_step(stage, *, password_changed=False):
    """Report only fixed diagnostic labels, never raw driver messages or SQL."""
    import psycopg

    try:
        yield
    except psycopg.Error as exc:
        message = str(exc).lower()
        if any(text in message for text in ("certificate", "ssl error", "tls error")):
            reason = "Falha na validacao TLS; confira o certificado oficial e a data do computador."
        elif "circuit breaker" in message:
            reason = "Pooler bloqueou tentativas temporariamente; aguarde alguns minutos antes de repetir."
        elif exc.sqlstate == "28P01" or "password authentication failed" in message:
            reason = "Autenticacao recusada; confira a senha do usuario desta etapa."
        elif "tenant or user not found" in message:
            reason = "Projeto/usuario nao localizado no pooler; confira host e referencia no painel Connect."
        elif exc.sqlstate == "42501":
            reason = "Permissao insuficiente; revise o acesso restrito aprovado."
        elif any(text in message for text in ("timeout", "timed out")):
            reason = "Tempo de conexao esgotado; confira rede e disponibilidade do projeto."
        elif any(text in message for text in ("translate host", "getaddrinfo", "resolve hostname")):
            reason = "Falha de DNS; confira rede e endereco do pooler."
        else:
            reason = "Falha de comunicacao com PostgreSQL; confira o projeto e tente novamente."
        state = (
            " A senha radar_app pode ter sido alterada; reutilize a mesma senha exclusiva ao repetir."
            if password_changed else " Nenhuma senha foi alterada nesta tentativa."
        )
        raise SetupError(stage + ": " + reason + state) from None


def run(command, *, payload=None, cwd=None, missing_ok=False):
    result = subprocess.run(
        command, input=payload, text=True, capture_output=True, cwd=cwd, timeout=90, check=False
    )
    if result.returncode:
        if missing_ok and "HTTP 404" in result.stderr:
            return None
        raise SetupError(
            "Comando recusado. Confira login GitHub, permissoes e conectividade; segredos nao foram exibidos."
        )
    return result.stdout.strip()


def gh_json(*args, payload=None, missing_ok=False):
    output = run(["gh", *args], payload=payload, missing_ok=missing_ok)
    return json.loads(output) if output else None


def connection_url(project_ref, host, password):
    return (
        f"postgresql+psycopg://radar_app.{project_ref}:{quote(password, safe='')}"
        f"@{host}:5432/postgres?sslmode=verify-full&sslrootcert={CA_FILE}"
    )


def set_secret(repo, name, value):
    # stdin, never argv, files, shell interpolation or public logs.
    run(["gh", "secret", "set", name, "--repo", repo, "--env", "production"], payload=value)


def configure_environment(repo):
    path = f"repos/{repo}/environments/production"
    existing = gh_json("api", path, missing_ok=True)
    policy = (existing or {}).get("deployment_branch_policy")
    if policy and policy.get("protected_branches"):
        # Preserve an existing stricter policy; never weaken approvals or restrictions.
        return
    if not policy:
        payload = {"deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}}
        for rule in (existing or {}).get("protection_rules", []):
            if rule.get("type") == "wait_timer":
                payload["wait_timer"] = rule["wait_timer"]
            elif rule.get("type") == "required_reviewers":
                payload["reviewers"] = [
                    {"type": r["type"], "id": r["reviewer"]["id"]} for r in rule.get("reviewers", [])
                ]
                payload["prevent_self_review"] = rule.get("prevent_self_review", False)
        if existing and "can_admins_bypass" in existing:
            payload["can_admins_bypass"] = existing["can_admins_bypass"]
        gh_json("api", "--method", "PUT", path, "--input", "-", payload=json.dumps(payload))
    policies = gh_json("api", path + "/deployment-branch-policies")
    if not any(
        p["name"] == "main" and p.get("type", "branch") == "branch"
        for p in policies.get("branch_policies", [])
    ):
        gh_json(
            "api",
            "--method",
            "POST",
            path + "/deployment-branch-policies",
            "--input",
            "-",
            payload=json.dumps({"name": "main", "type": "branch"}),
        )


def configure_database(args, new_password, admin_password, ca_path):
    import psycopg
    from psycopg import sql

    common = dict(
        host=args.pooler_host,
        port=5432,
        dbname="postgres",
        connect_timeout=20,
        sslmode="verify-full",
        sslrootcert=str(ca_path),
        prepare_threshold=None,
    )
    print("Validando conexao administradora com certificado oficial...")
    with database_step("Conexao administradora"):
        admin = psycopg.connect(
            **common, user="postgres." + args.project_ref, password=admin_password, autocommit=True
        )
    with admin:
        with database_step("Verificacao do usuario restrito"):
            row = admin.execute(
                "SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                "FROM pg_roles WHERE rolname='radar_app'"
            ).fetchone()
            if row != (True, False, False, False, False, False):
                raise SetupError("radar_app nao existe ou possui privilegios diferentes dos aprovados.")
        # libpq hashes locally. The ALTER ROLE statement contains a SCRAM verifier, not cleartext.
        with database_step("Definicao da senha restrita", password_changed=True):
            verifier = admin.pgconn.encrypt_password(
                new_password.encode("utf-8"), b"radar_app", b"scram-sha-256"
            )
            admin.execute(
                sql.SQL("ALTER ROLE radar_app PASSWORD {}").format(sql.Literal(verifier.decode("ascii")))
            )
    print("Validando conexao e permissoes de radar_app...")
    with database_step("Conexao restrita", password_changed=True), psycopg.connect(
        **common, user="radar_app." + args.project_ref, password=new_password
    ) as app:
        if app.execute("SELECT current_user, current_schema()").fetchone() != ("radar_app", "radar"):
            raise SetupError("A conexao nao usou o usuario/schema esperado.")
        count = app.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='radar'"
        ).fetchone()[0]
        if count != 10:
            raise SetupError("Quantidade inesperada de tabelas; nenhuma conexao foi publicada.")
        # A transaction-only lease proves SELECT/INSERT/UPDATE/DELETE without polluting price history.
        name = "setup_" + secrets.token_hex(10)
        app.execute("INSERT INTO radar.leases(name,owner,until) VALUES (%s,%s,%s)", (name, "setup", 0))
        app.execute("UPDATE radar.leases SET until=1 WHERE name=%s", (name,))
        app.execute("DELETE FROM radar.leases WHERE name=%s", (name,))
        app.rollback()


def parser():
    p = argparse.ArgumentParser(
        description="Configurar Supabase e GitHub Secrets sem compartilhar senhas no chat"
    )
    p.add_argument("--repo", required=True)
    p.add_argument("--project-ref", required=True)
    p.add_argument("--pooler-host", required=True)
    return p


def execute(args):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        raise SetupError("Repositorio invalido.")
    if not re.fullmatch(r"[a-z]{20}", args.project_ref):
        raise SetupError("Referencia do projeto invalida.")
    if not re.fullmatch(r"aws-\d+-[a-z0-9-]+\.pooler\.supabase\.com", args.pooler_host):
        raise SetupError("Use o host oficial Session pooler exibido no Supabase.")
    root = Path(__file__).resolve().parents[1]
    info = gh_json("api", "user")
    if info["login"].casefold() != args.repo.split("/")[0].casefold():
        raise SetupError("O GitHub conectado nao e o proprietario informado.")
    if run(["git", "status", "--porcelain"], cwd=root):
        raise SetupError("Ha alteracoes locais sem commit. Revise antes de publicar a configuracao.")
    if run(["git", "branch", "--show-current"], cwd=root) != "main":
        raise SetupError("Execute a configuracao na branch main revisada.")
    remote = run(["git", "remote", "get-url", "origin"], cwd=root).removesuffix(".git")
    if remote.casefold() != ("https://github.com/" + args.repo).casefold():
        raise SetupError("O repositorio remoto difere do destino aprovado.")
    print("Publicando a verificacao do banco no repositorio " + args.repo + "...")
    run(["git", "push", "origin", "main"], cwd=root)
    configure_environment(args.repo)
    names = {
        s["name"]
        for s in gh_json("secret", "list", "--repo", args.repo, "--env", "production", "--json", "name")
    }
    if "DATABASE_URL" not in names:
        ca_path = certificate_path(root)
        # Detect missing dependencies before asking for private credentials.
        try:
            import psycopg  # noqa: F401
        except ImportError:
            raise SetupError(
                'Instale a dependencia: python -m pip install "psycopg[binary]==3.3.4"'
            ) from None

        print("A senha administradora sera enviada somente ao seu PostgreSQL Supabase por TLS.")
        print("No GitHub sera salva apenas a conexao do usuario restrito radar_app.")
        admin_password = getpass.getpass("Senha do banco que voce definiu ao criar o projeto: ")
        new_password = getpass.getpass("Nova senha exclusiva para radar_app (20+ caracteres): ")
        confirmation = getpass.getpass("Repita a nova senha: ")
        if len(new_password) < 20 or not secrets.compare_digest(new_password.encode(), confirmation.encode()):
            raise SetupError("Nova senha muito curta ou confirmacao diferente; nenhuma senha foi alterada.")
        if new_password == admin_password:
            raise SetupError("Use uma senha diferente da administradora; nenhuma senha foi alterada.")
        configure_database(args, new_password, admin_password, ca_path)
        set_secret(
            args.repo, "DATABASE_URL", connection_url(args.project_ref, args.pooler_host, new_password)
        )
        print("Conexao restrita validada e salva em production/DATABASE_URL.")
    else:
        print("DATABASE_URL ja existe: a senha e a conexao existentes foram preservadas.")
    if "TOKEN_ENCRYPTION_KEY" not in names:
        set_secret(
            args.repo, "TOKEN_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        )
        print("Chave de criptografia gerada e salva em production/TOKEN_ENCRYPTION_KEY.")
    for attempt in range(3):
        try:
            run(["gh", "workflow", "run", "database.yml", "--repo", args.repo, "--ref", "main"])
            break
        except SetupError:
            if attempt == 2:
                raise SetupError(
                    "Secrets salvos. Abra Actions > Database check > Run workflow para verificar o banco."
                ) from None
            time.sleep(3)
    print("Configuracao enviada. Acompanhe o workflow Database check no GitHub Actions.")
    print("O monitoramento de lojas ainda aguarda credenciais oficiais e anuncios revisados.")
    return 0


def main():
    args = parser().parse_args()
    try:
        return execute(args)
    except SetupError as exc:
        print("Configuracao interrompida: " + str(exc), file=sys.stderr)
    except KeyboardInterrupt:
        print("Configuracao cancelada pelo operador.", file=sys.stderr)
    except Exception as exc:
        # Library exceptions can include connection strings, passwords or SQL. Never print them.
        print(
            "Configuracao interrompida (" + type(exc).__name__ + "). Confira acesso e execute novamente.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
