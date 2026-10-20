# Validação da entrega — 20/10/2026

## Atualização da implantação

O repositório público foi publicado e o CI original de Linux/Python 3.12 foi aprovado. No Supabase Free, foram criadas as dez tabelas do schema `radar`; consultas reais verificaram ausência de acesso por `anon`, `authenticated` e `service_role`. O usuário `radar_app` foi criado mediante aprovação do proprietário; outra consulta real confirmou CRUD nas dez tabelas e ausência de privilégios administrativos ou CREATE no schema. Nenhuma senha foi definida pelo agente.

O proprietário executou o configurador privado: a conexão administradora autenticou, a conta restrita passou pelo teste de leitura/gravação com rollback e os Secrets DATABASE_URL e TOKEN_ENCRYPTION_KEY foram salvos no GitHub. A senha administradora permaneceu fora do GitHub. O [Database check no commit 782cd8a](https://github.com/KaueSun/PromoSearch/actions/runs/39455732091) terminou com sucesso, confirmando a conexão real de um executor do GitHub ao Supabase. O [CI do mesmo commit](https://github.com/KaueSun/PromoSearch/actions/runs/39455636648) também passou.

A revisão da entrada de senha e das reconexões passou em **36 testes locais do configurador/workflows**. Os testes verificam preservação de caracteres especiais, rejeição de controles de colagem/cancelamento, proibição de entrada visível no terminal e limite de duas reconexões somente para recusas de autenticação, mantendo a mesma senha e sem repetir ALTER ROLE. O proprietário utilizou a janela e concluiu a configuração real. A causa exata das recusas anteriores não foi comprovada: tanto a entrada quanto a política de reconexão foram alteradas.

O configurador privado do Discord e seu workflow manual foram preparados. **57 testes locais dos configuradores/workflows** passaram, incluindo fixtures de validação do destino, transporte privado de Secrets, confirmação de mensagem, proteção contra reenvio após despacho incerto e isolamento do Secret do webhook. Nenhum webhook real foi usado nesses testes; a configuração real do Discord aguarda o proprietário.

## Resultado executado

- MVP original: **8 testes aprovados**, antes das alterações.
- Versão 0.2: **65 testes aprovados**, sem testes pulados ou warnings na execução final.
- Cobertura total medida: **85%**; análise de ofertas 99%, armazenamento 98%.
- Verificação estática e formatação: aprovadas.
- Ambiente executado: Windows, Python 3.14.8 e PostgreSQL **18.4 real**, local e descartável, sem vínculo com Supabase.
- Dependências com versões/hashes verificadas na instalação local; resolução de dependências Linux/Python 3.12 validada em dry-run. O [CI Linux/Python 3.12 do commit 88e6a30](https://github.com/KaueSun/PromoSearch/actions/runs/39451460669) passou no GitHub.
- Após incluir o certificado oficial do Supabase e diagnóstico seguro por etapa: **89 testes locais aprovados**, incluindo PostgreSQL 18 real, e análise estática aprovada. As correções subsequentes também passaram no CI remoto.
- Teste real no Session pooler: autoridades do sistema falharam na validação; o certificado público indicado pelo painel Supabase permitiu ao libpq validar cadeia/hostname. Posteriormente, autenticação e acesso ao banco pela nuvem foram confirmados pelo proprietário e pelo Database check.

## O que os testes cobrem

Identidade exata e separação de CPU/GPU/RAM/SSD/tela/código de fabricante; dinheiro em centavos; URLs/hosts inválidos; referências de 7/30/90 dias; dias insuficientes; preços suspeitos; condição e reputação; vendedores independentes; frete desconhecido; histórico sem contaminantes; persistência e limpeza; bloqueio de concorrência; repetição de alertas; entregas ambíguas; embeds e menções; contratos sintéticos da API; mudanças de atributos; moeda incorreta; anúncios com variações; retries e HTTP 429; OAuth cifrado e renovação interrompida; entradas manuais; logs sem URI de banco; separação de Secrets entre produção e pull requests; agendamento do workflow.

Os testes de PostgreSQL realmente gravaram/leram dados, exerceram índices/constraints, retenção, reserva de alertas e consulta JSON de anúncios concorrentes. Os schemas temporários foram removidos e o servidor de teste foi encerrado.

## O que não foi validado como produção

| Entregável solicitado | Estado |
|---|---|
| Código modular | Implementado e publicado; configurador Discord preparado localmente |
| Repositório público PromoSearch | Publicado em KaueSun/PromoSearch; CI do commit 782cd8a aprovado |
| Banco persistente Supabase privado | Conexão restrita/Secrets configurados; acesso real pelo GitHub Actions confirmado |
| Agendamento a cada 30 minutos | Workflow pronto, não ativado |
| Consulta oficial Mercado Livre | Conector implementado e testado com fixtures; acesso real depende da conta autorizada |
| Amazon/Shopee/KaBuM!/Magalu/Casas Bahia | Sem coleta implementada; bloqueios documentados |
| Webhook Discord | Configurador privado e verificação na nuvem preparados e testados com fixtures; webhook real não configurado |
| Comparação com frete entre vendedores | Motor testado; conector atual não fornece cotação e não ativa esse critério |
| Logs e histórico | Implementados; CI executado na nuvem, monitoramento real ainda pendente |
| Funcionamento independente do PC | Arquitetura preparada; aceitação em nuvem ainda pendente |

Não houve emissão de preço fictício a um canal real, scraping, acesso ao WhatsApp, contratação paga ou publicação de credenciais.

## Aceitação antes de declarar o sistema ativo

Após a participação do proprietário nas contas: publicar o código aprovado; configurar banco privado e Secrets; passar no CI remoto; aceitar uma consulta real autorizada; conferir o histórico após pelo menos duas execuções agendadas; confirmar um alerta verdadeiro quando houver critério calculável. Até lá, o estado correto é **preparado para implantação**, não "monitorando em produção".

