# Operação, manutenção e segurança

## Diagnóstico

| Sinal | Ação |
|---|---|
| `command_failed` / `OperationalError` | Confira DATABASE_URL, senha percent-encoded, projeto pausado, host/porta do Session pooler e TLS. Nunca cole URI em issue pública. |
| Nenhum anúncio cadastrado | Adicione produto exato, revise atributos via inspect e cadastre watch. Catálogo vazio não é sucesso de monitoramento. |
| `source_item_failed` | Execute inspect no terminal privado; confira autorização, anúncio ativo, variações e mudança de assinatura. Sem erro bruto de API em logs. |
| OAuth interrompido | Refaça o consentimento oficial. Configure o novo refresh token no terminal privado, execute `python radar.py oauth-reset` e atualize o Secret inicial. Não reuse tokens antigos. |
| Chave Fernet inválida | Recupere a chave original; trocar só a chave torna tokens existentes indecifráveis. Uma rotação planejada exige reautorizar OAuth. |
| `partial` / erro no job | Outras consultas podem ter sido persistidas. A rodada retorna erro para visibilidade no Actions; confira checked/errors/sent. |
| `running` antigo | Processo pode ter sido encerrado pelo runner. Após 20 minutos, o bloqueio expira. Verifique entregas dispatching antes de intervir. |
| Job ausente | Confira Actions habilitado, branch principal, calendário, atividade do repositório e avisos de pausa de serviço. Um cron de Actions não é SLA. |
| Banco acima de 350 MB | Reduza anúncios/retensão (mínimo 91 dias), faça limpeza e acompanhe disco no painel. Não ative upgrade automaticamente. |

`check` sem `--send` usa preços reais da API e grava histórico, mas não reserva/envia alertas. Ele não é uma demonstração fictícia. As fixtures existem apenas em `tests/`.

## Conciliar uma entrega

Execute `status` num terminal privado e procure `unresolved_alerts`. Confira o canal Discord no horário indicado na tabela `alerts`. Se a mensagem existe, execute:

```text
python radar.py resolve-alert ID_DO_REGISTRO --state sent
```

Somente quando tiver confirmado que a mensagem não chegou, marque `--state failed`; uma rodada futura poderá tentar novamente caso o desconto continue válido. Não marque como failed para "destravar" sem conferir o canal. Um crash entre POST e commit é uma entrega ambígua inevitável sem idempotência fornecida pelo Discord.

## Banco privado

Use o papel `radar_app` no schema `radar`, que não deve integrar os schemas expostos por REST/GraphQL. O processo não precisa de chave Supabase anon/service_role. O usuário da aplicação precisa criar suas próprias tabelas, mas não criar bancos, papéis ou acessar administração do projeto. A conexão ao endpoint de nuvem é autenticada e cifrada; o plano gratuito não oferece aqui uma rede privada dedicada. Não significa que o endpoint de conexão seja inacessível pela internet.

O código exige TLS em produção e desativa prepared statements para compatibilidade com poolers. O padrão `require` garante criptografia, mas não força validação de hostname do certificado; para verificação completa, use `sslmode=verify-full` e `sslrootcert` apropriado na URI, seguindo a CA do provedor. Essa configuração é preservada pelo conector. Não inclua o banco/schema em APIs públicas. Credenciais e chave Fernet ficam no Environment production; tokens rotativos são cifrados no banco e não podem ser decifrados sem a chave dos Secrets.

Os testes usam explicitamente `testing=True` para um PostgreSQL local sem TLS. A CLI de produção recusa SQLite e não possui flag que permita desligar TLS.

## Backup e retenção

A retenção padrão é 100 dias. Limpeza remove observações antigas, runs e cadastros manuais; não apaga automaticamente o estado necessário para deduplicar alertas. Observações atualizam no mesmo intervalo de meia hora e as referências usam medianas por dia para reduzir peso de consultas repetidas. Bancos podem manter espaço em disco após DELETE até autovacuum; acompanhe o painel.

Faça dumps privados com pg_dump usando os recursos recomendados pelo provedor, sem passar senha em argumentos e sem enviar backup para GitHub artifacts públicos. Guarde a chave Fernet separada do backup. Faça um teste de restauração em projeto privado descartável. Não foi ativado backup pago, PITR nem serviço externo de armazenamento.

## GitHub público

Somente schedule e workflow_dispatch na branch principal acessam Secrets. Pull requests executam testes sem credenciais de produção e sem `pull_request_target`. Checkout não persiste credenciais; permissões do GITHUB_TOKEN são somente leitura. O Environment production deve aceitar apenas a branch principal. Proteja alterações de workflows, configurações, dependências e código com revisão; um colaborador com poder de modificar código confiável pode acessar seus segredos se a alteração for integrada.

Actions usadas pelo código estão fixadas em commits; dependências estão fixadas com hashes. O CI usa somente banco descartável. Não adicionamos agendamento artificial de commits para contornar a política de inatividade do GitHub. Verifique o cron antes de 60 dias sem atividade legítima.

## Limites conhecidos

- Hardware é normalizado por curadoria de configuração exata; não há inferência por IA nem correspondência automática por título. A assinatura verifica mudanças desde a revisão, não a veracidade da revisão inicial.
- Anúncios com variações não são acompanhados. Specs incompletas exigem revisão humana, não aproximação.
- Mercado Livre ainda depende da aprovação da conta e teste real. A plataforma pode negar acesso a itens de terceiros.
- Frete desconhecido fica desconhecido. A comparação entre vendedores por total aguarda uma fonte legítima de cotação, sem usar selo de frete grátis como evidência.
- Amazon/Shopee/KaBuM!/Magalu/Casas Bahia não estão conectadas. Nenhuma busca de todo o mercado foi apresentada como funcional.
- Trabalho local e testes não confirmam implantação. A aceitação da produção exige banco na nuvem, CI aprovado, consulta real, duas rodadas agendadas e alerta real confirmado quando houver critério.

