// Chat-page only logic. sidebar.js handles sidebar/modal/profile (loaded via base.html).

const form        = document.getElementById("chat-form");
const input       = document.getElementById("message-input");
const messageList = document.getElementById("message-list");
const welcomeScreen = document.getElementById("welcome-screen");
const sendBtn     = document.getElementById("send-btn");
const newChatBtn  = document.getElementById("new-chat-btn");

// True if server pre-rendered history or user already sent a message this session
let hasMessages = document.querySelectorAll(".chat-msg").length > 0;

// Track the active chat UUID (null = new chat not yet persisted)
let currentChatId = (function () {
    const parts = window.location.pathname.replace(/\/$/, "").split("/");
    const last = parts[parts.length - 1];
    // A UUID is 36 chars with hyphens
    return last.length === 36 ? last : null;
}());

// Auto-resize textarea
input?.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
});

// Submit on Enter (Shift+Enter adds newline)
input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});

// Suggestion chip clicks
document.querySelectorAll(".suggestion-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        const label = chip.querySelector("span.font-semibold");
        input.value = label ? label.textContent.trim() : chip.textContent.trim();
        input.dispatchEvent(new Event("input"));
        form.requestSubmit();
    });
});

// New chat — reset to welcome screen
newChatBtn?.addEventListener("click", () => {
    messageList?.querySelectorAll(".chat-msg").forEach((el) => el.remove());
    if (welcomeScreen) welcomeScreen.style.display = "";
    hasMessages = false;
    currentChatId = null;
    history.pushState(null, "", "/");
    if (input) { input.value = ""; input.style.height = "auto"; input.focus(); }
});

function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

function showMessages() {
    if (!hasMessages) { hasMessages = true; if (welcomeScreen) welcomeScreen.style.display = "none"; }
}

function appendUserMessage(content) {
    showMessages();
    const wrapper = document.createElement("div");
    wrapper.className = "chat-msg flex justify-end px-4 md:px-6 py-3 max-w-4xl mx-auto w-full";
    const bubble = document.createElement("div");
    bubble.className = "user-bubble";
    bubble.textContent = content;
    wrapper.appendChild(bubble);
    messageList.appendChild(wrapper);
    messageList.scrollTop = messageList.scrollHeight;
}

function appendBotMessage() {
    showMessages();
    const wrapper = document.createElement("div");
    wrapper.className = "chat-msg flex gap-3 md:gap-4 px-4 md:px-6 py-4 max-w-4xl mx-auto w-full";
    const avatar = document.createElement("div");
    avatar.className = "bot-avatar shrink-0 mt-0.5";
    avatar.textContent = "🍳";
    const contentWrap = document.createElement("div");
    contentWrap.className = "flex-1 min-w-0";
    const bubble = document.createElement("div");
    bubble.className = "bot-bubble";
    contentWrap.appendChild(bubble);
    wrapper.appendChild(avatar);
    wrapper.appendChild(contentWrap);
    messageList.appendChild(wrapper);
    messageList.scrollTop = messageList.scrollHeight;
    return bubble;
}

async function streamResponse(userMessage) {
    const bubble = appendBotMessage();
    bubble.classList.add("streaming");
    let fullText = "";
    try {
        const response = await fetch("/api/message/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
            body: JSON.stringify({ message: userMessage, chat_id: currentChatId }),
        });
        if (!response.ok) { bubble.textContent = "⚠️ Error generating recipe."; return; }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop();
            for (const part of parts) {
                if (!part.startsWith("data: ")) continue;
                try {
                    const data = JSON.parse(part.slice(6));
                    if (data.token) {
                        fullText += data.token;
                        bubble.innerHTML = marked.parse(fullText);
                        messageList.scrollTop = messageList.scrollHeight;
                    } else if (data.error) {
                        bubble.innerHTML = `<span class="text-red-500">⚠️ ${data.error}</span>`;
                    } else if (data.done) {
                        bubble.classList.remove("streaming");
                        // Update URL and track chat ID after first exchange
                        if (data.chat_id && !currentChatId) {
                            currentChatId = data.chat_id;
                            history.pushState(null, "", `/${currentChatId}/`);
                        }
                    }
                } catch (e) { console.error("SSE parse error", e); }
            }
        }
    } catch (error) {
        bubble.textContent = `⚠️ Network error: ${error.message}`;
    } finally {
        bubble.classList.remove("streaming");
    }
}

form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const userMessage = input.value.trim();
    if (!userMessage) return;
    if (window.innerWidth < 768) closeSidebar();
    appendUserMessage(userMessage);
    input.value = "";
    input.style.height = "auto";
    sendBtn.disabled = true;
    try { await streamResponse(userMessage); }
    finally { sendBtn.disabled = false; input.focus(); }
});
