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
    history.pushState(null, "", "/chat/");
    // Clear active highlight from sidebar
    document.querySelectorAll("#sidebar-history a").forEach((a) => {
        a.className = "flex items-center px-3 py-2 text-xs rounded-md truncate transition-colors text-zinc-500 hover:bg-zinc-800/80 hover:text-zinc-200";
    });
    if (input) { input.value = ""; input.style.height = "auto"; input.focus(); }
});

function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

function addChatToSidebar(chatId, title) {
    const historyEl = document.getElementById("sidebar-history");
    if (!historyEl) return;

    // Hide empty state
    const empty = document.getElementById("sidebar-empty");
    if (empty) empty.style.display = "none";

    // Deactivate any currently active sidebar items
    historyEl.querySelectorAll(".chat-item").forEach((item) => {
        item.classList.remove("bg-zinc-800/60");
        const a = item.querySelector("a");
        if (a) a.className = "flex-1 min-w-0 px-3 py-2 text-xs truncate transition-colors text-zinc-500 group-hover:text-zinc-200";
    });

    // Build the new active chat-item group
    const dotsSvg = `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
    </svg>`;

    const item = document.createElement("div");
    item.className = "chat-item group relative flex items-center rounded-md bg-zinc-800/60 hover:bg-zinc-800/80 transition-colors";
    item.innerHTML =
        `<a href="/chat/${chatId}/" class="flex-1 min-w-0 px-3 py-2 text-xs truncate transition-colors text-zinc-200">${title}</a>` +
        `<button class="chat-menu-btn shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100 p-1.5 mr-1 rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-700 transition-opacity"
                 data-chat-id="${chatId}" data-chat-title="${title}" title="Options">${dotsSvg}</button>`;

    // Get or create the Today section
    let todayList = document.getElementById("sidebar-list-today");
    if (!todayList) {
        const section = document.createElement("div");
        section.id = "sidebar-section-today";
        section.innerHTML =
            '<p class="text-zinc-600 text-[10px] font-semibold uppercase tracking-widest px-2 pb-1 pt-1">Today</p>' +
            '<div id="sidebar-list-today" class="space-y-0.5"></div>';
        historyEl.prepend(section);
        todayList = document.getElementById("sidebar-list-today");
    }

    todayList.prepend(item);
}

function applyRecipeStyles(bubble) {
    bubble.querySelectorAll("p").forEach((p) => {
        if (p.textContent.includes("Prep:") && p.textContent.includes("Cook:")) {
            p.classList.add("recipe-meta");
        }
    });
}

function showMessages() {
    if (!hasMessages) { hasMessages = true; if (welcomeScreen) welcomeScreen.style.display = "none"; }
}

// Apply to any history bubbles already in the DOM
document.querySelectorAll(".bot-bubble").forEach(applyRecipeStyles);

const copyIconSvg = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
const checkIconSvg = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;

function appendUserMessage(content) {
    showMessages();
    const wrapper = document.createElement("div");
    wrapper.className = "chat-msg group flex justify-end items-end gap-2 px-4 md:px-6 py-3 max-w-4xl mx-auto w-full";
    const copyBtn = document.createElement("button");
    copyBtn.className = "user-copy-btn opacity-0 group-hover:opacity-100 focus:opacity-100 shrink-0 p-1.5 rounded-lg transition-all";
    copyBtn.title = "Copy message";
    copyBtn.innerHTML = copyIconSvg;
    const bubble = document.createElement("div");
    bubble.className = "user-bubble";
    bubble.textContent = content;
    wrapper.appendChild(copyBtn);
    wrapper.appendChild(bubble);
    messageList.appendChild(wrapper);
    messageList.scrollTop = messageList.scrollHeight;
}

// Copy handler — delegated so it works for both history and new messages
messageList?.addEventListener("click", (e) => {
    const btn = e.target.closest(".user-copy-btn");
    if (!btn) return;
    const text = btn.closest(".chat-msg")?.querySelector(".user-bubble")?.textContent ?? "";
    navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = checkIconSvg;
        btn.classList.add("copied");
        setTimeout(() => { btn.innerHTML = copyIconSvg; btn.classList.remove("copied"); }, 1500);
    }).catch(console.error);
});

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
        const response = await fetch("/chat/api/message/", {
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
                        applyRecipeStyles(bubble);
                        // Update URL, track chat ID, and add to sidebar after first exchange
                        if (data.chat_id && !currentChatId) {
                            currentChatId = data.chat_id;
                            window.history.pushState(null, "", `/chat/${currentChatId}/`);
                            addChatToSidebar(currentChatId, data.chat_title || userMessage);
                        }
                        // Save rendered HTML to DB so history loads identically
                        if (data.chat_id) {
                            fetch("/chat/api/save-bot-message/", {
                                method: "POST",
                                headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                                body: JSON.stringify({ chat_id: data.chat_id, content: bubble.innerHTML }),
                            }).catch(console.error);
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
