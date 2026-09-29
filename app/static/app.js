const collectButtons = document.querySelectorAll("#collect-button, [data-collect]");
const toast = document.querySelector("#toast");

collectButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    const label = button.querySelector("span");
    if (label) label.textContent = "Coletando…";
    try {
      const response = await fetch("/api/collect", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Não foi possível iniciar a coleta.");
      toast.textContent = `Coleta concluída: ${result.new} novas, ${result.duplicates} duplicadas.`;
      toast.classList.add("visible");
      window.setTimeout(() => window.location.reload(), 1400);
    } catch (error) {
      toast.textContent = error.message;
      toast.classList.add("visible");
      button.disabled = false;
      if (label) label.textContent = "Coletar agora";
      window.setTimeout(() => toast.classList.remove("visible"), 4000);
    }
  });
});