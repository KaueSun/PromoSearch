"""Owner-run private webhook setup; CI verification never receives database credentials."""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from radar_gamer.discord import send, webhook_url
from radar_gamer.http import ApiError, Client
from tools.configure_supabase import SetupError, configure_environment, gh_json, run, set_secret


def read_webhook():
    try:
        import tkinter as tk
        from tkinter import simpledialog
    except ImportError:
        raise SetupError("Instale Tcl/Tk pelo instalador oficial do Python para abrir a entrada privada.") from None
    try:
        root = tk.Tk()
    except tk.TclError:
        raise SetupError("Nao foi possivel abrir a janela privada do webhook.") from None
    try:
        root.withdraw()
        value = simpledialog.askstring(
            "PromoSearch - webhook Discord",
            "Cole a URL do webhook do canal de ofertas.\n"
            "O link sera salvo no GitHub Secrets, sem aparecer no chat.\n\n"
            "A verificacao na nuvem enviara UMA mensagem de configuracao,\n"
            "sem ofertas nem precos, ao canal escolhido.",
            show="*",
            parent=root,
        )
    finally:
        root.destroy()
    if value is None:
        raise SetupError("Configuracao cancelada; nenhum webhook foi salvo.")
    # Validate exactly as supplied: never silently remove query parameters or hidden characters.
    webhook_url(value)
    return value


def validate_destination(client, value):
    webhook_url(value)
    metadata = client.request(value)
    expected_id = value.split("/")[-2]
    if (
        not isinstance(metadata, dict)
        or str(metadata.get("id")) != expected_id
        or metadata.get("type") != 1
        or not str(metadata.get("channel_id", "")).isdigit()
        or not str(metadata.get("guild_id", "")).isdigit()
    ):
        raise SetupError("O Discord nao confirmou um webhook de entrada associado a um canal de servidor.")


def confirmation_payload():
    return {
        "username": "Radar Gamer",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": "Conexao do Radar Gamer confirmada",
            "description": "Mensagem de configuracao enviada pelo GitHub Actions.\n"
                           "Este canal recebeu a verificacao do webhook.\n"
                           "O monitoramento de lojas ainda esta em configuracao.",
            "color": 0x3B82F6,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "PromoSearch | Verificacao tecnica, sem oferta ou preco"},
        }],
    }


def verify_cloud():
    value = os.getenv("DISCORD_WEBHOOK_URL", "")
    client = Client()
    validate_destination(client, value)
    send(client, value, confirmation_payload())
    print("Discord confirmou o recebimento da mensagem de configuracao enviada pela nuvem.")
    return 0


def configure(repo):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SetupError("Repositorio invalido.")
    root = Path(__file__).resolve().parents[1]
    if gh_json("api", "user")["login"].casefold() != repo.split("/")[0].casefold():
        raise SetupError("O GitHub conectado nao e o proprietario informado.")
    if run(["git", "status", "--porcelain"], cwd=root):
        raise SetupError("Ha alteracoes locais sem commit. Revise antes de publicar.")
    if run(["git", "branch", "--show-current"], cwd=root) != "main":
        raise SetupError("Execute a configuracao na branch main revisada.")
    remote = run(["git", "remote", "get-url", "origin"], cwd=root).removesuffix(".git")
    if remote.casefold() != ("https://github.com/" + repo).casefold():
        raise SetupError("O repositorio remoto difere do destino aprovado.")
    print("Publicando a verificacao do Discord no repositorio " + repo + "...")
    run(["git", "push", "origin", "main"], cwd=root)
    configure_environment(repo)
    names = {
        s["name"] for s in gh_json("secret", "list", "--repo", repo, "--env", "production", "--json", "name")
    }
    if "DISCORD_WEBHOOK_URL" in names:
        print("DISCORD_WEBHOOK_URL ja existe e foi preservado; nenhum novo envio foi solicitado.")
        print("Para verificar novamente, confira o canal e execute manualmente Actions > Discord check.")
        return 0
    print("Cole o webhook na janela privada. A nuvem enviara uma unica mensagem tecnica, sem precos.")
    value = read_webhook()
    validate_destination(Client(), value)
    set_secret(repo, "DISCORD_WEBHOOK_URL", value)
    print("Webhook validado e salvo em production/DISCORD_WEBHOOK_URL.")
    try:
        run(["gh", "workflow", "run", "discord.yml", "--repo", repo, "--ref", "main"])
    except SetupError:
        raise SetupError(
            "Webhook salvo. Confira Actions > Discord check antes de solicitar outro envio; "
            "a solicitacao anterior pode ter sido aceita."
        ) from None
    print("Verificacao solicitada. Acompanhe Actions > Discord check e a mensagem no canal.")
    print("O monitoramento de lojas continua aguardando acesso oficial e anuncios revisados.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Configurar webhook Discord sem compartilhar o link no chat")
    parser.add_argument("--repo")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_only:
            return verify_cloud()
        if not args.repo:
            raise SetupError("Informe --repo DONO/REPOSITORIO.")
        return configure(args.repo)
    except SetupError as exc:
        print("Configuracao interrompida: " + str(exc), file=sys.stderr)
    except ValueError:
        print("Webhook invalido. Use a URL HTTPS copiada do Discord, sem parametros extras.", file=sys.stderr)
    except ApiError as exc:
        if exc.ambiguous:
            message = "Entrega incerta. Confira o canal antes de repetir a verificacao."
        else:
            message = {
                "401": "Webhook recusado pelo Discord.",
                "403": "Discord negou acesso ao webhook.",
                "404": "Webhook nao encontrado; confira se ainda existe no Discord.",
                "429": "Limite de requisicoes do Discord atingido; tente novamente mais tarde.",
            }.get(exc.code, "Falha de comunicacao com Discord; confira o canal e tente novamente.")
        print(message, file=sys.stderr)
    except KeyboardInterrupt:
        print("Configuracao cancelada pelo operador.", file=sys.stderr)
    except Exception:
        print("Falha na configuracao; detalhes privados nao foram exibidos.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
