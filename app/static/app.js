const collectButtons = document.querySelectorAll("#collect-button, [data-collect]");
const toast = document.querySelector("#toast");
const topicDialog = document.querySelector("#topic-dialog");
const translateDialog = document.querySelector("#translate-dialog");

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 4000);
}

const topicForm = document.querySelector("#topic-form");
const topicSubmit = topicForm.querySelector("[type=submit]");
document.querySelector("#topic-open").addEventListener("click", () => {
  topicForm.reset();
  topicForm.elements.topic_id.value = "";
  document.querySelector("#topic-dialog-title").textContent = "Novo tema";
  topicSubmit.textContent = "Adicionar tema";
  topicDialog.showModal();
});
document.querySelector("#translate-open").addEventListener("click", () => translateDialog.showModal());
document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog").close());
});

collectButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    const label = button.querySelector("span");
    const originalLabel = label?.textContent;
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
      if (label) label.textContent = originalLabel;
    }
  });
});

document.querySelectorAll("[data-edit-topic]").forEach((button) => {
  button.addEventListener("click", () => {
    topicForm.reset();
    topicForm.elements.topic_id.value = button.dataset.editTopic;
    topicForm.elements.name.value = button.dataset.topicName;
    try {
      topicForm.elements.queries.value = JSON.parse(button.dataset.topicQueries).join("\n");
    } catch {
      topicForm.elements.queries.value = "";
    }
    document.querySelector("#topic-dialog-title").textContent = "Editar tema";
    topicSubmit.textContent = "Salvar alterações";
    topicDialog.showModal();
  });
});

document.querySelector("#topic-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("[type=submit]");
  const fields = new FormData(form);
  button.disabled = true;
  try {
    const topicId = fields.get("topic_id");
    const response = await fetch(topicId ? `/api/topics/${encodeURIComponent(topicId)}` : "/api/topics", {
      method: topicId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: fields.get("name"),
        queries: fields.get("queries").split(/\r?\n/).map((query) => query.trim()).filter(Boolean),
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

document.querySelectorAll("time.article-date[data-utc]").forEach((element) => {
  const value = element.dataset.utc;
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return;
  const now = new Date();
  const dayNumber = (value) => Date.UTC(value.getFullYear(), value.getMonth(), value.getDate()) / 86_400_000;
  const dayDiff = dayNumber(now) - dayNumber(date);
  const timeText = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(date);
  const dateOptions = {
    day: "2-digit",
    month: "short",
    ...(date.getFullYear() !== now.getFullYear() ? { year: "numeric" } : {}),
  };
  const dayText = dayDiff === 0
    ? "Hoje"
    : dayDiff === 1
      ? "Ontem"
      : new Intl.DateTimeFormat("pt-BR", dateOptions).format(date).replace(" de ", " ").replace(/\.$/, "");
  element.querySelector(".date-day").textContent = dayText;
  element.querySelector(".date-time").textContent = timeText;
  const dateKind = element.dataset.dateKind === "discovered" ? "Descoberto" : "Publicado";
  element.querySelector(".date-label").textContent = dateKind.toLowerCase();
  element.dateTime = date.toISOString();
  const fullDate = new Intl.DateTimeFormat("pt-BR", { dateStyle: "full", timeStyle: "short" }).format(date);
  element.title = `${dateKind} em ${fullDate}`;
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
      body: JSON.stringify({
        text: new FormData(form).get("text"),
        target: document.querySelector("#translation-target").value,
      }),
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
      const target = document.querySelector("#translation-target").value;
      const response = await fetch(
        `/api/articles/${encodeURIComponent(button.dataset.translateArticle)}/translate?target=${encodeURIComponent(target)}`,
        {
        method: "POST",
        },
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Tradução indisponível.");
      window.location.reload();
    } catch (error) {
      showToast(error.message);
      button.disabled = false;
    }
  });
});
