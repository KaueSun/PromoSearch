"""Publish a public static HTTPS callback. No Mercado Livre secret or token is requested."""

import argparse
import json
import re
import sys
from pathlib import Path

from tools.configure_supabase import SetupError, gh_json, run


def callback_url(repo):
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+", repo):
        raise SetupError("Repositorio invalido.")
    owner, project = repo.split("/")
    if project.casefold() == owner.casefold() + ".github.io":
        return f"https://{owner.lower()}.github.io/oauth-callback.html"
    return f"https://{owner.lower()}.github.io/{project}/oauth-callback.html"


def prepare(repo):
    url = callback_url(repo)
    root = Path(__file__).resolve().parents[1]
    if gh_json("api", "user")["login"].casefold() != repo.split("/")[0].casefold():
        raise SetupError("O GitHub conectado nao e o proprietario informado.")
    if run(["git", "status", "--porcelain"], cwd=root):
        raise SetupError("Ha alteracoes locais sem commit. Revise antes de publicar.")
    if run(["git", "branch", "--show-current"], cwd=root) != "main":
        raise SetupError("Execute na branch main revisada.")
    remote = run(["git", "remote", "get-url", "origin"], cwd=root).removesuffix(".git")
    if remote.casefold() != ("https://github.com/" + repo).casefold():
        raise SetupError("O repositorio remoto difere do destino aprovado.")
    repository = gh_json("api", "repos/" + repo)
    if repository.get("private") is not False or repository.get("default_branch") != "main":
        raise SetupError("Este configurador exige repositorio publico com branch principal main.")
    path = f"repos/{repo}/pages"
    existing = gh_json("api", path, missing_ok=True)
    if existing and (
        existing.get("cname")
        or existing.get("build_type") != "legacy"
        or existing.get("source") != {"branch": "main", "path": "/docs"}
    ):
        raise SetupError("Ja existe um site Pages com outra configuracao; ele foi preservado.")
    print("Publicando a pagina estatica de autorizacao e a documentacao publica revisada...")
    run(["git", "push", "origin", "main"], cwd=root)
    if existing:
        print("GitHub Pages ja usa main/docs; configuracao existente preservada.")
    else:
        gh_json(
            "api", "--method", "POST", path, "--input", "-",
            payload=json.dumps({"build_type": "legacy", "source": {"branch": "main", "path": "/docs"}}),
        )
        print("GitHub Pages gratuito solicitado para o repositorio publico.")
    print("Aguarde a publicacao em GitHub > Actions > pages build and deployment.")
    print("URL de retorno para o aplicativo Mercado Livre: " + url)
    print("Abra a URL e confirme 'Pagina de retorno preparada' antes de usa-la no aplicativo.")
    print("Nenhuma senha, documento, token ou chave secreta foi solicitado ou salvo nesta etapa.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Preparar retorno HTTPS publico para OAuth do Mercado Livre")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    try:
        return prepare(args.repo)
    except SetupError as exc:
        print("Preparacao interrompida: " + str(exc), file=sys.stderr)
    except KeyboardInterrupt:
        print("Preparacao cancelada pelo operador.", file=sys.stderr)
    except Exception:
        print("Falha na preparacao; detalhes privados nao foram exibidos.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
