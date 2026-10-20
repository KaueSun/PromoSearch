# Avaliação das fontes — 20/10/2026

Documentação pública indica viabilidade, mas não substitui autorização da conta. Não foi feita consulta real de preços nesta entrega e nenhuma API paga foi contratada.

| Fonte | Acesso e restrições verificadas | Estado da implementação |
|---|---|---|
| Mercado Livre | Bearer Token em `/items/{id}/sale_price?context=channel_marketplace`; preço `amount`, moeda BRL; `regular_amount` não é histórico. OAuth autorizado; access token dura cerca de 6h, refresh token roda e deve ser preservado. Acesso pode ser recusado para o aplicativo/conta/anúncio. | Conector para IDs exatos implementado; precisa de credenciais e validação real. Sem busca global nem cotação de frete. |
| Amazon BR | Creators API exige cadastro Amazon Associates do marketplace, acesso de desenvolvedor e credenciais. A introdução informa pelo menos 10 vendas qualificadas nos últimos 30 dias para acesso à PA API via Creators API. Regras de uso/exibição e retenção de conteúdo precisam ser revisadas antes de guardar históricos ou distribuir no Discord. | Sem conector; importação manual identificada. Não presumimos que um histórico de 90 dias seja permitido para conteúdo da API. |
| Shopee BR | Explorer oficial solicita AppId e Secret. Elegibilidade de afiliado, schema liberado, quotas e condições devem ser confirmados no portal da conta. Não há base documental pública suficiente aqui para afirmar acesso irrestrito ou custo zero universal. | Sem conector nem endpoints adivinhados. |
| KaBuM! | Documentação HubScore exige permissão da aplicação e descreve integração de marketplace. Isso não comprova acesso aberto ao catálogo para comparação de varejo. | Aguardar feed/API de afiliado ou autorização escrita; manual por enquanto. |
| Magalu | Portal oficial possui APIs de marketplace e autenticação; não comprova acesso geral gratuito a preços de todo o varejo para afiliados. | Sem conector. Solicitar escopo/feed autorizado. |
| Casas Bahia | Portal documenta operações de marketplace, incluindo cadastro de produtos para sellers. Não é evidência de API aberta de comparação. | Sem conector. Aguardar acesso autorizado/feed. |

Não atribuímos preço fixo nem quota universal às APIs de parceiros sem documentação da conta. Os pedidos são limitados a três tentativas por operação, timeout de 20s e espera limitada para 429. O workflow comporta no máximo 50 anúncios inicialmente, três consultas por anúncio (detalhes, preço e reputação), cerca de 150 requisições por rodada antes de retries. Aumentar cobertura depende das quotas autorizadas. Uma negativa 401/403 não é contornada.

Fontes oficiais:

- [Mercado Livre: preços](https://developers.mercadolivre.com.br/devcenter/api-de-precos)
- [Mercado Livre: OAuth](https://developers.mercadolivre.com.br/autenticacao-e-autorizacao)
- [Mercado Livre: reputação](https://developers.mercadolivre.com.br/pt_br/produto-consulta-de-usuarios/reputacao-de-vendedores)
- [Amazon: pré-requisitos](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction)
- [Amazon: cadastro por marketplace](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/onboarding/sign-up-as-an-amazon-associate)
- [Shopee: explorer oficial](https://open-api.affiliate.shopee.com.br/explorer)
- [KaBuM!: documentação autorizada](https://www.kabum.com.br/hotsite/documentacao-hubscore/)
- [Magalu: ambientes](https://developers.magalu.com/docs/first-steps/environment/index.html)
- [Casas Bahia: portal](https://developers.grupocasasbahia.com.br/marketplace/docs/cadastro-de-produtos)
- [Discord: execução de webhooks](https://docs.discord.com/developers/resources/webhook#execute-webhook)

