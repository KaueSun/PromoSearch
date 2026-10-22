"use strict";

(() => {
  const params = new URLSearchParams(window.location.search);
  // Remove temporary values from the address bar/history, including malformed responses.
  window.history.replaceState(null, "", window.location.pathname);
  const title = document.getElementById("title");
  const status = document.getElementById("status");
  const copy = document.getElementById("copy");
  let result = null;

  if (!params.size) {
    title.textContent = "Página de retorno preparada";
    status.textContent = "A URL está pronta para o cadastro do aplicativo. A autorização deve ser iniciada pelo configurador privado.";
    return;
  }
  if (params.has("error")) {
    title.textContent = "Autorização não concluída";
    status.textContent = "Volte ao configurador privado para iniciar uma nova tentativa.";
    return;
  }
  const code = params.get("code") || "";
  const state = params.get("state") || "";
  if (params.getAll("code").length !== 1 || params.getAll("state").length !== 1
      || !/^[A-Za-z0-9_-]{43}$/.test(state)
      || code.length < 8 || code.length > 2048 || /[\s\u0000-\u001f\u007f-\u009f]/.test(code)) {
    title.textContent = "Retorno inválido";
    status.textContent = "Inicie a autorização pelo configurador privado. Não publique os dados do endereço.";
    return;
  }

  result = JSON.stringify({ code, state });
  copy.disabled = false;
  title.textContent = "Retorno recebido";
  status.textContent = "Copie o retorno e cole somente na janela privada do configurador. Ele verificará se a autorização corresponde à solicitação iniciada.";
  copy.addEventListener("click", async () => {
    if (!result || copy.disabled) return;
    try {
      await navigator.clipboard.writeText(result);
      status.textContent = "Retorno copiado. Cole na janela privada, sem enviar pelo chat.";
    } catch {
      status.textContent = "O navegador não permitiu copiar. Habilite a cópia para esta página e tente novamente.";
    }
  });
  window.setTimeout(() => {
    result = null;
    copy.disabled = true;
    status.textContent = "O retorno foi removido desta página. Se não concluiu a configuração, inicie uma nova autorização.";
  }, 300000);
})();
