const messages = document.querySelector("#messages");
const traceList = document.querySelector("#traceList");
const stepCount = document.querySelector("#stepCount");
const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const resetButton = document.querySelector("#resetButton");
const examples = document.querySelectorAll(".examples button");

function addMessage(role, text, variant = "") {
  const article = document.createElement("article");
  article.className = `message ${role} ${variant}`.trim();
  article.innerHTML = `
    <span class="role">${role === "user" ? "You" : "Agent"}</span>
    <p></p>
  `;
  article.querySelector("p").textContent = text;
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  messageInput.disabled = isLoading;
  sendButton.textContent = isLoading ? "Thinking" : "Send";
}

function renderTrace(toolCalls) {
  stepCount.textContent = `${toolCalls.length} ${toolCalls.length === 1 ? "step" : "steps"}`;

  if (!toolCalls.length) {
    traceList.innerHTML =
      '<p class="empty-state">No tool was needed for this answer.</p>';
    return;
  }

  traceList.innerHTML = "";
  for (const call of toolCalls) {
    const card = document.createElement("article");
    card.className = `trace-card ${call.name}`;
    card.innerHTML = `
      <header>
        <h3>Step ${call.step}: ${call.name}</h3>
      </header>
      <code>${escapeHtml(JSON.stringify(call.arguments, null, 2))}</code>
      <code>${escapeHtml(call.result)}</code>
    `;
    traceList.appendChild(card);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message) return;

  addMessage("user", message);
  setLoading(true);
  const loadingMessage = addMessage("assistant", "Thinking through the tools...", "loading");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const rawText = await response.text();
    let data;
    try {
      data = rawText ? JSON.parse(rawText) : {};
    } catch {
      throw new Error(rawText || "The server returned a non-JSON response.");
    }

    if (!response.ok) {
      throw new Error(data.detail || "Request failed");
    }

    loadingMessage.remove();
    addMessage("assistant", data.answer || "No answer returned.");
    renderTrace(data.tool_calls || []);
  } catch (error) {
    loadingMessage.remove();
    addMessage("assistant", error.message, "error");
  } finally {
    setLoading(false);
    messageInput.focus();
  }
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = messageInput.value;
  messageInput.value = "";
  sendMessage(text);
});

resetButton.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  messages.innerHTML = "";
  addMessage(
    "assistant",
    "Conversation reset. Ask me something that needs search, calculation, unit conversion, or a mix of all three."
  );
  traceList.innerHTML =
    '<p class="empty-state">Tool calls will appear here when the agent uses search, math, or conversion.</p>';
  stepCount.textContent = "0 steps";
  messageInput.focus();
});

examples.forEach((button) => {
  button.addEventListener("click", () => {
    messageInput.value = button.textContent.trim();
    messageInput.focus();
  });
});
