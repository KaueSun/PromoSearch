# Aplicativo Mercado Livre — configuração inicial

O DevCenter da conta já permite acessar **Minhas aplicações**. A integração ainda não está autorizada: nenhum token real do Mercado Livre foi obtido e nenhuma oferta real foi consultada.

## Retorno HTTPS

O Mercado Livre exige uma URL HTTPS de redirecionamento. A página estática preparada para este repositório é:

```text
https://kauesun.github.io/PromoSearch/oauth-callback.html
```

O publicador privado usa GitHub Pages de um repositório público, disponível no plano gratuito. Ele verifica a conta, o destino Git, a branch e a visibilidade do repositório; publica o código revisado e habilita a origem `main/docs`. Um site existente com outra configuração é preservado. Nenhum Secret, plano pago, permissão de banco ou webhook é alterado.

Para publicar pelo terminal privado do proprietário:

```powershell
python -m tools.prepare_meli_callback --repo KaueSun/PromoSearch
```

Espere **pages build and deployment** terminar no GitHub Actions e abra a URL. Sem parâmetros de autorização, ela deve informar **Página de retorno preparada**. Só depois use a URL no cadastro. O comando é idempotente para a mesma origem Pages e não pede senha ou token do Mercado Livre.

## Dados do aplicativo

No DevCenter, escolha **Criar aplicação** na unidade **Mercado Livre**. Quando esses campos forem exibidos, use:

| Campo | Valor |
|---|---|
| Nome | PromoSearch; se indisponível, PromoSearch KaueSun |
| Nome curto, quando solicitado | promosearch-kauesun |
| Descrição | Monitor de preços de notebooks gamers com histórico e alertas no Discord, usando consultas autorizadas às APIs do Mercado Livre. |
| Site | https://github.com/KaueSun/PromoSearch |
| URI/URL de redirecionamento | https://kauesun.github.io/PromoSearch/oauth-callback.html |
| PKCE | Habilitado, com S256 no fluxo de autorização |

Solicite apenas leitura dos usuários e dos recursos de itens/preços (**Publicação e sincronização**, em leitura) e o acesso offline necessário à renovação. Não é necessário autorizar escrita em anúncios, mensagens, pagamentos, pedidos ou faturamento. Se a tela impuser acesso extra ou uma URL obrigatória de notificações, revise esse requisito antes de enviar: a página estática de retorno não é um receptor de notificações.

O aceite dos termos e a autorização dos dados são feitos pelo proprietário no portal oficial. Não publique Client Secret, código de autorização ou tokens no chat, em commits ou screenshots. A criação do aplicativo, por si só, não confirma que a API permitirá consultar anúncios de outros vendedores; isso será testado com uma requisição real autorizada, sem contornar recusas.

## O que a página faz

A página recebe somente o código temporário e `state` devolvidos pelo fluxo OAuth. O navegador solicita a página ao GitHub Pages com esses parâmetros, como em um callback HTTPS convencional; o GitHub é o provedor de hospedagem desse retorno. A página remove os parâmetros da barra de endereço/histórico e não faz chamadas à API, não pede credenciais e não autentica o monitor sozinha. Não há rastreadores, recursos externos ou armazenamento em localStorage/sessionStorage. O envio de referrer é desativado e uma política CSP restringe os recursos à própria origem.

O botão copia somente código e `state` para a janela privada do futuro configurador OAuth. A conferência criptográfica de `state` e a troca com PKCE precisam ocorrer nesse configurador, que ainda será implementado; a validação de formato na página não substitui essa conferência. O retorno é removido da memória da página após cinco minutos. Não inicie um fluxo real de autorização antes de o configurador estar pronto.

Fontes oficiais: [cadastro da aplicação](https://developers.mercadolivre.com.br/crie-uma-aplicacao-no-mercado-livre), [autenticação e autorização](https://developers.mercadolivre.com.br/autenticacao-e-autorizacao), [permissões funcionais](https://developers.mercadolivre.com.br/pt_br/permissoes-funcionais/), [GitHub Pages em repositórios públicos](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
