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
- Solicita a senha administradora do projeto e uma senha nova, exclusiva, para `radar_app`, com confirmação. Use 20 ou mais caracteres e guarde a nova senha em local seguro.
- Envia a senha administradora somente ao PostgreSQL Supabase, com TLS e validação de certificado/hostname.
- Calcula o verificador SCRAM localmente antes de definir a senha de `radar_app`; a instrução SQL não contém sua senha nova em texto claro.
- Verifica a conexão com `radar_app` e testa leitura/gravação numa transação descartada, sem inserir preços fictícios.
- Salva apenas a conexão restrita como `production/DATABASE_URL`, por stdin do GitHub CLI. A conexão força `sslmode=verify-full`.
- Cria `TOKEN_ENCRYPTION_KEY` somente se ausente. Uma chave existente é preservada para não invalidar tokens cifrados.
- Dispara o workflow **Database check**. Esse workflow verifica conexão e estado do banco sem acessar lojas nem enviar Discord.

As senhas não aparecem na tela, no chat, em argumentos de processos ou em arquivos. A senha administradora não é salva no GitHub. O arquivo temporário contém somente certificados públicos de autoridades certificadoras, e é removido ao terminar. O script não instala serviços, não cria recursos pagos e não ativa o monitoramento automaticamente.

Se `DATABASE_URL` já existir, o configurador não altera a senha nem sobrescreve a conexão existente; apenas preserva a configuração e solicita nova verificação. Se houver erro depois de definir a senha, execute novamente usando a mesma senha exclusiva que acabou de escolher. Erros de bibliotecas são sanitizados para não expor URI ou SQL.

## Confirmação da nuvem

Aguarde **Actions > Database check** terminar com sucesso. Isso comprova que um executor do GitHub alcançou o banco com a conta restrita. Não comprova acesso ao Mercado Livre nem funcionamento do webhook: essas são etapas separadas e ainda exigem credenciais autorizadas e anúncios revisados.

Depois dessas etapas, defina a variável de repositório `MONITOR_ENABLED=true` para liberar o cron. Antes disso, rodadas agendadas são ignoradas e o fluxo manual permanece disponível. Se um Environment existente tiver revisores obrigatórios, o workflow pode aguardar aprovação; o configurador não remove essa proteção.

Fontes: [conexão Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres), [papéis PostgreSQL no Supabase](https://supabase.com/docs/guides/database/postgres/roles), [criptografia de senha pelo libpq/psycopg](https://www.psycopg.org/psycopg3/docs/api/pq.html#psycopg.pq.PGconn.encrypt_password).
