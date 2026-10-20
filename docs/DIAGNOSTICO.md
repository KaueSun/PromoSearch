# Diagnóstico do MVP recebido

Análise do ZIP `Radar_Gamer_Discord_MVP (21).zip`, sem executar instruções externas contidas no README como se fossem ordens do proprietário.

## Reaproveitado

Os oito testes originais passaram antes das alterações. A base conceitual de comparação por SKU, avaliação antes de gravar o preço atual, controle de repetição, formatação em BRL, embeds sem menções e cadastro manual é útil. A separação entre API oficial e demonstração já era reconhecida no README.

## Problemas encontrados e tratamento

| Problema | Consequência | Tratamento na versão 0.2 |
|---|---|---|
| Demo escreve no banco padrão | Preços fictícios podem fundamentar alerta real posterior | Sem comando demo na aplicação de produção; fixtures isoladas nos testes |
| Desconto anunciado é motivo suficiente | Alerta pode reproduzir preço original inflado | Campo original da loja ignorado na seleção |
| SKUs contêm apenas "Core i5" ou "Ryzen 5" | CPUs de gerações diferentes podem ser agrupadas | CPU completa, código do fabricante e identidade por configuração completa |
| Preço consultado usa título/configuração digitados | Anúncio pode ter hardware diferente | Revisão inicial explícita + assinatura de atributos/vendedor/condição; alteração interrompe acompanhamento |
| Concorrentes distintos por anúncio | Um vendedor com várias publicações pesa várias vezes | Um preço por vendedor independente |
| Histórico limitado aos últimos 60 pontos | Com consultas a cada meia hora, cobre pouco mais de um dia apesar do rótulo de 30 dias | Janelas reais de 7/30/90 dias e cobertura de dias explicitada |
| SQLite local sem persistência no Actions | Cada runner pode começar com banco vazio | PostgreSQL privado persistente |
| Token de acesso fixo | Falha depois da expiração, incompatível com operação autônoma | OAuth rotativo cifrado, estado durável e falha segura se rotação ficar ambígua |
| POST e registro do alerta separados sem reserva | Crash após enviar pode duplicar na rodada seguinte | Reserva antes de POST; estados dispatching/uncertain exigem conciliação |
| Falhas individuais só impressas | Processo pode retornar sucesso mesmo sem consultar fonte | Estado partial/failed e código de saída não zero |
| Sem runner/workflows, limites ou retenção | Não há implantação reproduzível nem controle de crescimento | Workflows de CI e monitoramento, quotas configuráveis e retenção |

## Limite da entrega

Não houve acesso autenticado ao varejo, criação do banco Supabase, publicação do repositório ou envio de alerta real. O código foi testado com respostas sintéticas e um PostgreSQL real local. Isso valida a implementação, sem afirmar que a conta do usuário já tem acesso às APIs.

O objetivo de operar em nuvem permanece pendente até configurar as contas, aprovar ao menos um anúncio verdadeiro e verificar duas execuções agendadas. Sem essa validação, apresentar o sistema como já ativo seria incorreto.

