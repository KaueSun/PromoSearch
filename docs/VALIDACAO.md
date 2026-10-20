# Validação da entrega — 20/10/2026

## Atualização da implantação

O repositório público foi publicado e o CI original de Linux/Python 3.12 foi aprovado. No Supabase Free, foram criadas as dez tabelas do schema `radar`; consultas reais verificaram ausência de acesso por `anon`, `authenticated` e `service_role`. O usuário `radar_app` foi criado mediante aprovação do proprietário; outra consulta real confirmou CRUD nas dez tabelas e ausência de privilégios administrativos ou CREATE no schema. Nenhuma senha foi definida pelo agente.

O configurador privado e o workflow Database check foram preparados. Os testes locais adicionais verificam transporte de segredos por stdin, ausência da senha administradora nos dados enviados ao GitHub, preservação de configurações existentes e interrupção antes de alterar o banco quando há confirmação de senha incorreta. Um teste manual em PostgreSQL local descartável verificou o verificador SCRAM e leitura/gravação com rollback usando senha fictícia. A autenticação real, gravação dos Secrets e execução do Database check ainda aguardam o proprietário.

## Resultado executado

- MVP original: **8 testes aprovados**, antes das alterações.
- Versão 0.2: **65 testes aprovados**, sem testes pulados ou warnings na execução final.
- Cobertura total medida: **85%**; análise de ofertas 99%, armazenamento 98%.
- Verificação estática e formatação: aprovadas.
- Ambiente executado: Windows, Python 3.14.8 e PostgreSQL **18.4 real**, local e descartável, sem vínculo com Supabase.
- Dependências com versões/hashes verificadas na instalação local; resolução de dependências Linux/Python 3.12 validada em dry-run. O [CI Linux/Python 3.12 do commit 88e6a30](https://github.com/KaueSun/PromoSearch/actions/runs/39451460669) passou no GitHub.
- Após incluir o certificado oficial do Supabase e diagnóstico seguro por etapa: **89 testes locais aprovados**, incluindo PostgreSQL 18 real, e análise estática aprovada. O CI desta correção aguarda sua publicação pelo configurador.
- Teste real sem senha no Session pooler: autoridades do sistema falharam na validação; o certificado público indicado pelo painel Supabase permitiu ao libpq validar cadeia/hostname e chegar ao pedido de senha. Isso ainda não comprova autenticação nem acesso aos dados pela nuvem.

## O que os testes cobrem

Identidade exata e separação de CPU/GPU/RAM/SSD/tela/código de fabricante; dinheiro em centavos; URLs/hosts inválidos; referências de 7/30/90 dias; dias insuficientes; preços suspeitos; condição e reputação; vendedores independentes; frete desconhecido; histórico sem contaminantes; persistência e limpeza; bloqueio de concorrência; repetição de alertas; entregas ambíguas; embeds e menções; contratos sintéticos da API; mudanças de atributos; moeda incorreta; anúncios com variações; retries e HTTP 429; OAuth cifrado e renovação interrompida; entradas manuais; logs sem URI de banco; separação de Secrets entre produção e pull requests; agendamento do workflow.

Os testes de PostgreSQL realmente gravaram/leram dados, exerceram índices/constraints, retenção, reserva de alertas e consulta JSON de anúncios concorrentes. Os schemas temporários foram removidos e o servidor de teste foi encerrado.

## O que não foi validado como produção

| Entregável solicitado | Estado |
|---|---|
| Código modular | Implementado e publicado; correção TLS preparada localmente |
| Repositório público PromoSearch | Publicado em KaueSun/PromoSearch; CI anterior aprovado |
| Banco persistente Supabase privado | Projeto/schema/dez tabelas/papel restrito verificados; senha/conexão/Secrets aguardam configuração pelo proprietário |
| Agendamento a cada 30 minutos | Workflow pronto, não ativado |
| Consulta oficial Mercado Livre | Conector implementado e testado com fixtures; acesso real depende da conta autorizada |
| Amazon/Shopee/KaBuM!/Magalu/Casas Bahia | Sem coleta implementada; bloqueios documentados |
| Webhook Discord | Payload/fluxo de entrega testados com fixture; webhook real não configurado |
| Comparação com frete entre vendedores | Motor testado; conector atual não fornece cotação e não ativa esse critério |
| Logs e histórico | Implementados; CI executado na nuvem, monitoramento real ainda pendente |
| Funcionamento independente do PC | Arquitetura preparada; aceitação em nuvem ainda pendente |

Não houve emissão de preço fictício a um canal real, scraping, acesso ao WhatsApp, contratação paga ou publicação de credenciais.

## Aceitação antes de declarar o sistema ativo

Após a participação do proprietário nas contas: publicar o código aprovado; configurar banco privado e Secrets; passar no CI remoto; aceitar uma consulta real autorizada; conferir o histórico após pelo menos duas execuções agendadas; confirmar um alerta verdadeiro quando houver critério calculável. Até lá, o estado correto é **preparado para implantação**, não "monitorando em produção".

