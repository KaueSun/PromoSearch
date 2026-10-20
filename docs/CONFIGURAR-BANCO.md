# Configuração privada do Supabase e GitHub Actions

O projeto utiliza PostgreSQL direto. A Data API fica desativada e o schema `radar` não concede acesso a `anon`, `authenticated` ou `service_role`. O usuário `radar_app` lê/grava somente as dez tabelas e usa as sequências necessárias. Ele não é administrador, não é proprietário das tabelas e não cria papéis, bancos ou tabelas.

## Preparação do banco

1. No projeto Supabase **Free**, execute `setup-schema.sql` no SQL Editor como `postgres`.
2. Em Database > Roles, crie `radar_app` marcando somente **User can login**. A criação desse acesso deve ser autorizada pelo proprietário.
3. Execute `setup-access.sql`. Confira `tabelas_com_acesso=10`, `pode_criar_tabelas=false` e todos os privilégios administrativos como `false`.

As etapas acima já foram verificadas no projeto atual. Os scripts não contêm senhas ou preços e não inserem demonstrações no histórico. A estrutura é idempotente e preserva registros existentes.

## Configurador executado pelo proprietário

Execute em seu PowerShell privado, fora da automação do navegador:

```powershell
python tools/configure_supabase.py --repo DONO/REPOSITORIO --project-ref REFERENCIA --pooler-host HOST_DO_SESSION_POOLER
```

Copie referência e host reais do painel **Connect > Direct > Session pooler**. O configurador aceita apenas o domínio oficial `pooler.supabase.com`, valida o proprietário GitHub, a branch `main`, o destino remoto e a ausência de alterações sem commit. É necessário ter GitHub CLI autenticado e Python com `psycopg[binary]==3.3.4`.

O configurador:

- Publica os commits locais já revisados para disponibilizar o workflow de banco.
- Prepara o Environment `production`, restringindo novos ambientes à branch `main` e preservando revisores/esperas existentes. Políticas existentes de branches protegidas são mantidas.
- Solicita apenas a senha administradora do banco do projeto (não a senha de login do painel Supabase). Gera automaticamente uma senha exclusiva para `radar_app`, usando 32 bytes aleatórios seguros (256 bits), sem exibi-la nem pedir confirmação.
- No Windows, abre uma janela local com campo mascarado e suporte à colagem, evitando comandos de controle recebidos pelo campo oculto do terminal. A entrada não é registrada e a área de transferência não é lida pelo configurador. `--password-input gui` força a janela; `--password-input console` mantém o modo terminal com entrada privada obrigatória. Cancelamento e caracteres de controle interrompem antes de enviar a senha.
- Envia a senha administradora somente ao PostgreSQL Supabase, com TLS e validação de certificado/hostname.
- Calcula o verificador SCRAM localmente antes de definir a senha de `radar_app`; a instrução SQL não contém sua senha nova em texto claro.
- Verifica a conexão com `radar_app` e testa leitura/gravação numa transação descartada, sem inserir preços fictícios.
- Salva apenas a conexão restrita como `production/DATABASE_URL`, por stdin do GitHub CLI. A conexão força `sslmode=verify-full`.
- Cria `TOKEN_ENCRYPTION_KEY` somente se ausente. Uma chave existente é preservada para não invalidar tokens cifrados.
- Dispara o workflow **Database check**. Esse workflow verifica conexão e estado do banco sem acessar lojas nem enviar Discord.

As senhas não aparecem na tela, no chat, em argumentos de processos ou em arquivos. A senha administradora não é salva no GitHub. O certificado público oficial do Supabase está em `certs/supabase-prod-ca-2021.crt`; o configurador verifica seu SHA-256 antes de usá-lo. Tanto a configuração local quanto a conexão nos Actions exigem validação da cadeia e do hostname (`verify-full`). A URL salva aponta para esse arquivo relativo à raiz do repositório; execute o aplicativo nessa pasta, como fazem os workflows. O script não instala serviços, não cria recursos pagos e não ativa o monitoramento automaticamente.

Se `DATABASE_URL` já existir, o configurador não altera a senha nem sobrescreve a conexão existente; apenas preserva a configuração e solicita nova verificação. Se houver erro depois de definir a senha e antes de salvar o Secret, execute novamente: uma nova senha aleatória será gerada para concluir a configuração. A senha de `radar_app` fica somente na memória durante essa etapa e, depois, na conexão privada do GitHub Secrets. Erros de bibliotecas são sanitizados para não expor URI ou SQL.

O erro informa a etapa (administradora, definição da senha ou conexão restrita) e um motivo seguro: certificado, autenticação, DNS, timeout, permissão ou bloqueio temporário. Não compartilhe a mensagem bruta do driver nem sua URL de conexão. Uma falha antes de definir a senha é indicada explicitamente; uma falha durante/depois dessa operação pode significar que a senha de `radar_app` já foi alterada.

Depois de redefinir uma senha, o cache de credenciais do Session pooler pode causar recusas temporárias mesmo com a senha correta. O configurador faz até três tentativas de conexão, aguardando 15 segundos entre recusas de autenticação, sem repetir a alteração da senha. Falhas de certificado ou bloqueio explícito do pooler não são repetidas. Se persistir, não redefina a senha sucessivamente: confirme a entrada e o projeto; uma conexão direta por IPv6 pode distinguir senha incorreta de cache do pooler. Veja o [diagnóstico oficial de autenticação após rotação](https://supabase.com/docs/guides/troubleshooting/supavisor-error-password-authentication-failed-after-password-rotation).

## Confirmação da nuvem

Aguarde **Actions > Database check** terminar com sucesso. Isso comprova que um executor do GitHub alcançou o banco com a conta restrita. Não comprova acesso ao Mercado Livre nem funcionamento do webhook: essas são etapas separadas e ainda exigem credenciais autorizadas e anúncios revisados.

Depois dessas etapas, defina a variável de repositório `MONITOR_ENABLED=true` para liberar o cron. Antes disso, rodadas agendadas são ignoradas e o fluxo manual permanece disponível. Se um Environment existente tiver revisores obrigatórios, o workflow pode aguardar aprovação; o configurador não remove essa proteção.

Fontes: [conexão Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres), [papéis PostgreSQL no Supabase](https://supabase.com/docs/guides/database/postgres/roles), [criptografia de senha pelo libpq/psycopg](https://www.psycopg.org/psycopg3/docs/api/pq.html#psycopg.pq.PGconn.encrypt_password).
