const collectButtons = document.querySelectorAll("#collect-button, [data-collect]");
const toast = document.querySelector("#toast");
const topicDialog = document.querySelector("#topic-dialog");
const translateDialog = document.querySelector("#translate-dialog");

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 4000);
}

document.querySelector("#topic-open").addEventListener("click", () => topicDialog.showModal());
document.querySelector("#translate-open").addEventListener("click", () => translateDialog.showModal());
document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog").close());
});

collectButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    const label = button.querySelector("span");
    if (label) label.textContent = "Coletando…";
    try {
      const response = await fetch("/api/collect", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Não foi possível iniciar a coleta.");
      showToast(`Coleta concluída: ${result.new} novas, ${result.duplicates} duplicadas.`);
      window.setTimeout(() => window.location.reload(), 1400);
    } catch (error) {
      showToast(error.message);
      button.disabled = false;
      if (label) label.textContent = "Coletar agora";
    }
  });
});

document.querySelector("#topic-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("[type=submit]");
  const fields = new FormData(form);
  button.disabled = true;
  try {
    const response = await fetch("/api/topics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: fields.get("name"),
        queries: fields.get("queries").split("\n").map((query) => query.trim()).filter(Boolean),
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Não foi possível adicionar o tema.");
    window.location.reload();
  } catch (error) {
    showToast(error.message);
    button.disabled = false;
  }
});

document.querySelectorAll("[data-disable-topic]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const response = await fetch(`/api/topics/${encodeURIComponent(button.dataset.disableTopic)}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Não foi possível desativar o tema.");
      window.location.reload();
    } catch (error) {
      showToast(error.message);
      button.disabled = false;
    }
  });
});

document.querySelector("#translate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("[type=submit]");
  const output = document.querySelector("#translation-output");
  button.disabled = true;
  output.hidden = false;
  output.textContent = "Traduzindo…";
  try {
    const response = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: new FormData(form).get("text") }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Tradução indisponível.");
    output.textContent = result.translation;
  } catch (error) {
    output.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll("[data-translate-article]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const response = await fetch(`/api/articles/${encodeURIComponent(button.dataset.translateArticle)}/translate`, {
        method: "POST",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Tradução indisponível.");
      window.location.reload();
    } catch (error) {
      showToast(error.message);
      button.disabled = false;
    }
  });
});