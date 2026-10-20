# Configurar o Discord com entrada privada

## Preparar o canal

Crie ou escolha um canal de texto do seu servidor. Em **Configurações do servidor > Integrações > Webhooks**, crie um webhook chamado **Radar Gamer**, selecione o canal correto, salve e copie a URL. É necessário ter permissão para gerenciar webhooks. Não publique a URL em issues, commits ou no chat. [Instruções oficiais do Discord](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks).

## Salvar a credencial

No PowerShell privado do proprietário, com GitHub CLI autenticado e as dependências do projeto instaladas, execute a partir da raiz do repositório:

```powershell
python -m tools.configure_discord --repo DONO/REPOSITORIO
```

O configurador confere a conta GitHub, a branch main, o destino remoto e a ausência de alterações sem commit. Publica os commits revisados e mantém as restrições do Environment production. Uma janela local com campo mascarado pede a URL. O programa valida o domínio HTTPS/path e consulta somente o próprio webhook no Discord para confirmar que ele pertence a um canal de servidor. Não há acesso às conversas ou à conta pessoal.

O link é salvo em `production/DISCORD_WEBHOOK_URL` por stdin do GitHub CLI, sem argumento de processo, arquivo ou impressão. Nenhum Secret de banco ou criptografia é alterado. Se o webhook já existir em Secrets, ele é preservado e nenhuma nova mensagem é solicitada automaticamente. Para substituir um webhook revogado, atualize esse Secret pelo painel seguro do GitHub.

## Confirmar a entrega pela nuvem

O configurador solicita o workflow manual **Discord check**, que recebe somente o Secret do webhook. Ele valida novamente o destino e envia **uma mensagem técnica**, identificada como configuração, sem produto, preço ou promoção. O envio usa `wait=true` e exige que o Discord devolva o identificador da mensagem. Menções estão desativadas. Não repita a verificação sem conferir o canal se ocorrer timeout ou entrega incerta.

Confira o workflow verde e a mensagem **Conexao do Radar Gamer confirmada** no canal escolhido. Isso comprova GitHub Actions → Discord; não comprova consultas a lojas. A rotina de ofertas e o cron continuam aguardando credenciais oficiais e anúncios revisados.

O programa não cria recursos pagos, não acessa mensagens privadas e não usa dados fictícios como ofertas. Testes automatizados desse fluxo usam exclusivamente fixtures sintéticas, com a rede substituída.

## Resultado verificado no PromoSearch

Em 20/10/2026, o proprietário concluiu o cadastro privado e o [Discord check](https://github.com/KaueSun/PromoSearch/actions/runs/39457382809) confirmou a entrega real da mensagem técnica pela nuvem. Não é necessário cadastrar o webhook novamente. As consultas de preços continuam aguardando autorização da fonte e anúncios revisados.
