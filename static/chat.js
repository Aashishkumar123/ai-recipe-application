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
    return last.length === 36 ? last : null;
}());

// AbortController for the active stream (null when idle)
let abortController = null;

// SVG icons
const sendIconSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4 20-7z"/><path d="M22 2 11 13"/></svg>`;
const stopIconSvg = `<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2.5"/></svg>`;

// Switch the send button between send-mode and stop-mode
function setStopMode(on) {
    if (!sendBtn) return;
    if (on) {
        sendBtn.type = "button";
        sendBtn.innerHTML = stopIconSvg;
        sendBtn.title = "Stop generating";
        sendBtn.classList.add("is-stop");
        sendBtn.disabled = false;
    } else {
        sendBtn.type = "submit";
        sendBtn.innerHTML = sendIconSvg;
        sendBtn.title = "";
        sendBtn.classList.remove("is-stop");
        sendBtn.disabled = false;
        abortController = null;
    }
}

// Stop button click (only active while streaming)
sendBtn?.addEventListener("click", () => {
    if (abortController) abortController.abort();
});

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

    const empty = document.getElementById("sidebar-empty");
    if (empty) empty.style.display = "none";

    historyEl.querySelectorAll(".chat-item").forEach((item) => {
        item.classList.remove("bg-zinc-800/60");
        const a = item.querySelector("a");
        if (a) a.className = "flex-1 min-w-0 px-3 py-2 text-xs truncate transition-colors text-zinc-500 group-hover:text-zinc-200";
    });

    const dotsSvg = `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
    </svg>`;

    const item = document.createElement("div");
    item.className = "chat-item group relative flex items-center rounded-md bg-zinc-800/60 hover:bg-zinc-800/80 transition-colors";
    item.innerHTML =
        `<a href="/chat/${chatId}/" class="flex-1 min-w-0 px-3 py-2 text-xs truncate transition-colors text-zinc-200">${title}</a>` +
        `<button class="chat-menu-btn shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100 p-1.5 mr-1 rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-700 transition-opacity"
                 data-chat-id="${chatId}" data-chat-title="${title}" title="Options">${dotsSvg}</button>`;

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
    stylePantryIngredients(bubble);
    injectRecipeImage(bubble);
}

function stylePantryIngredients(bubble) {
    // Already processed
    if (bubble.querySelector(".pantry-check")) return;

    // Find the Ingredients <ul> — it follows the h2 containing 🧂
    let ingredientsUl = null;
    bubble.querySelectorAll("h2").forEach((h2) => {
        if (h2.textContent.includes("🧂")) {
            let el = h2.nextElementSibling;
            while (el && el.tagName !== "UL") el = el.nextElementSibling;
            if (el?.tagName === "UL") ingredientsUl = el;
        }
    });
    if (!ingredientsUl) return;

    const CHECK_SVG = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;

    ingredientsUl.querySelectorAll("li").forEach((li) => {
        // marked.js may wrap li content in a <p>
        const target = li.querySelector("p") || li;
        const first  = target.firstChild;
        if (!first || first.nodeType !== Node.TEXT_NODE) return;
        if (!first.textContent.trimStart().startsWith("✓")) return;

        // Strip the ✓ and any trailing space from the text node
        first.textContent = first.textContent.replace(/^\s*✓\s*/, "");

        const icon = document.createElement("span");
        icon.className   = "pantry-check";
        icon.innerHTML   = CHECK_SVG;
        icon.title       = "You have this";
        target.insertBefore(icon, target.firstChild);
    });
}

function bubbleHtmlForSave(bubble) {
    // Return bubble HTML with ephemeral image elements stripped so they're
    // not persisted — images are always re-fetched fresh on load.
    const clone = bubble.cloneNode(true);
    clone.querySelectorAll(
        ".recipe-hero-placeholder, .recipe-hero-single, .recipe-image-grid"
    ).forEach(el => el.remove());
    return clone.innerHTML;
}

async function injectRecipeImage(bubble) {
    // Guard: already has images, OR a load is already in-flight (data attr, not DOM)
    if (bubble.dataset.imgState || bubble.querySelector(".recipe-hero-img, .recipe-image-grid")) return;
    bubble.dataset.imgState = "loading";

    // Derive slug: prefer <!-- wiki: ... --> comment, fall back to <h1> text
    const commentMatch = bubble.innerHTML.match(/<!--\s*wiki:\s*([A-Za-z0-9_%()\-]+)\s*-->/);
    let slug = commentMatch?.[1]?.trim();

    if (!slug) {
        const h1text = bubble.querySelector("h1")?.textContent?.trim();
        if (!h1text) return;
        slug = h1text
            .replace(/\p{Emoji}/gu, "")
            .replace(/[^a-zA-Z0-9\s\-'()]/g, "")
            .trim()
            .replace(/\s+/g, "_");
    }
    if (!slug) return;

    const label = slug.replace(/_/g, " ");

    const placeholder = document.createElement("div");
    placeholder.className = "recipe-hero-placeholder";
    bubble.insertBefore(placeholder, bubble.firstChild);

    try {
        const SKIP  = /\.svg$/i;
        const NOISE = /flag|map|icon|logo|symbol|seal|emblem|coat|crest|locator/i;

        let srcs = [];

        // Try media-list for up to 3 images
        const mediaRes = await fetch(
            `https://en.wikipedia.org/api/rest_v1/page/media-list/${encodeURIComponent(slug)}`
        );
        if (mediaRes.ok) {
            const media = await mediaRes.json();
            srcs = (media.items || [])
                .filter(it =>
                    it.type === "image" &&
                    !SKIP.test(it.title || "") &&
                    !NOISE.test(it.title || "")
                )
                .map(it => {
                    const srcset = it.srcset || [];
                    const rel    = srcset[srcset.length - 1]?.src || "";
                    return rel.startsWith("//") ? "https:" + rel : rel;
                })
                .filter(src => src.startsWith("https://"))
                .slice(0, 3);
        }

        // Fall back to summary thumbnail
        if (srcs.length === 0) {
            const summaryRes = await fetch(
                `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(slug)}`
            );
            if (summaryRes.ok) {
                const data = await summaryRes.json();
                if (data.thumbnail?.source) srcs = [data.thumbnail.source];
            }
        }

        if (!placeholder.isConnected || srcs.length === 0) {
            placeholder.remove();
            return;
        }

        const container = document.createElement("div");
        container.className = srcs.length === 1
            ? "recipe-hero-single"
            : `recipe-image-grid recipe-image-grid--${srcs.length}`;

        srcs.forEach((src, i) => {
            const img     = document.createElement("img");
            img.src       = src;
            img.alt       = `${label} — photo ${i + 1}`;
            img.className = "recipe-hero-img";
            img.loading   = "lazy";
            img.onerror   = () => img.remove();
            container.appendChild(img);
        });

        placeholder.replaceWith(container);
    } catch {
        placeholder.remove();
    } finally {
        delete bubble.dataset.imgState;
    }
}

function showMessages() {
    if (!hasMessages) { hasMessages = true; if (welcomeScreen) welcomeScreen.style.display = "none"; }
}

// Apply to any history bubbles already in the DOM.
// First strip any stale placeholders that were accidentally persisted before this fix.
document.querySelectorAll(".bot-bubble .recipe-hero-placeholder").forEach(el => el.remove());
document.querySelectorAll(".bot-bubble").forEach(applyRecipeStyles);

const copyIconSvg     = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
const checkIconSvg    = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
const downloadIconSvg = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
const spinnerSvg      = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin .8s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;

// PDF download
messageList?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".bot-download-btn");
    if (!btn) return;
    const bubble = btn.closest(".chat-msg")?.querySelector(".bot-bubble");
    if (!bubble) return;

    const title = bubble.querySelector("h1")?.innerText?.trim() || "Recipe";

    const clone = bubble.cloneNode(true);
    clone.querySelectorAll("[class*='mt-1']").forEach((el) => el.remove());

    const originalHTML = btn.innerHTML;
    btn.innerHTML = spinnerSvg;
    btn.disabled  = true;

    try {
        const res = await fetch("/chat/api/download-pdf/", {
            method:  "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
            body:    JSON.stringify({ html: clone.innerHTML, title }),
        });

        if (!res.ok) throw new Error(await res.text());

        const blob     = await res.blob();
        const url      = URL.createObjectURL(blob);
        const anchor   = document.createElement("a");
        const filename = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + ".pdf";
        anchor.href     = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error("PDF download error", err);
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled  = false;
    }
});

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

// User message copy — delegated
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
    wrapper.className = "chat-msg group flex gap-3 md:gap-4 px-4 md:px-6 py-4 max-w-4xl mx-auto w-full";
    const avatar = document.createElement("div");
    avatar.className = "bot-avatar shrink-0 mt-0.5";
    avatar.textContent = "🍳";
    const contentWrap = document.createElement("div");
    contentWrap.className = "flex-1 min-w-0";
    const bubble = document.createElement("div");
    bubble.className = "bot-bubble";
    const toolbar = document.createElement("div");
    toolbar.className = "mt-1.5 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity";
    toolbar.innerHTML =
        `<button class="bot-copy-btn p-1.5 rounded-lg transition-all" title="Copy response">${copyIconSvg}</button>` +
        `<button class="bot-download-btn p-1.5 rounded-lg transition-all" title="Download as PDF">${downloadIconSvg}</button>`;
    contentWrap.appendChild(bubble);
    contentWrap.appendChild(toolbar);
    wrapper.appendChild(avatar);
    wrapper.appendChild(contentWrap);
    messageList.appendChild(wrapper);
    messageList.scrollTop = messageList.scrollHeight;
    return bubble;
}

// Bot message copy — delegated
messageList?.addEventListener("click", (e) => {
    const btn = e.target.closest(".bot-copy-btn");
    if (!btn) return;
    const text = btn.closest(".chat-msg")?.querySelector(".bot-bubble")?.innerText ?? "";
    navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = checkIconSvg;
        btn.classList.add("copied");
        setTimeout(() => { btn.innerHTML = copyIconSvg; btn.classList.remove("copied"); }, 1500);
    }).catch(console.error);
});

async function streamResponse(userMessage) {
    abortController = new AbortController();
    setStopMode(true);

    const bubble = appendBotMessage();
    bubble.classList.add("streaming");
    let fullText = "";
    let streamChatId = null; // received from server before first token

    try {
        const response = await fetch("/chat/api/message/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
            body: JSON.stringify({ message: userMessage, chat_id: currentChatId }),
            signal: abortController.signal,
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
                    if (data.chat_id && !data.done && !data.token) {
                        // Early chat_id event — store so we can save on abort
                        streamChatId = data.chat_id;
                    } else if (data.token) {
                        fullText += data.token;
                        bubble.innerHTML = marked.parse(fullText);
                        messageList.scrollTop = messageList.scrollHeight;
                    } else if (data.error) {
                        bubble.innerHTML = `<span class="text-red-500">⚠️ ${data.error}</span>`;
                    } else if (data.done) {
                        bubble.classList.remove("streaming");
                        applyRecipeStyles(bubble);
                        streamChatId = data.chat_id || streamChatId;
                        if (data.chat_id && !currentChatId) {
                            currentChatId = data.chat_id;
                            window.history.pushState(null, "", `/chat/${currentChatId}/`);
                            addChatToSidebar(currentChatId, data.chat_title || userMessage);
                        }
                        if (streamChatId) {
                            fetch("/chat/api/save-bot-message/", {
                                method: "POST",
                                headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                                body: JSON.stringify({ chat_id: streamChatId, content: bubbleHtmlForSave(bubble) }),
                            }).catch(console.error);
                        }
                    }
                } catch (e) { console.error("SSE parse error", e); }
            }
        }
    } catch (error) {
        if (error.name === "AbortError") {
            // User stopped — render whatever was streamed and save it to DB
            if (fullText) bubble.innerHTML = marked.parse(fullText);
            applyRecipeStyles(bubble);
            const saveId = streamChatId || currentChatId;
            if (saveId && bubble.innerHTML) {
                // Update URL + sidebar for new chats that were aborted before done
                if (!currentChatId && streamChatId) {
                    currentChatId = streamChatId;
                    window.history.pushState(null, "", `/chat/${currentChatId}/`);
                    addChatToSidebar(currentChatId, userMessage);
                }
                fetch("/chat/api/save-bot-message/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                    body: JSON.stringify({ chat_id: saveId, content: bubbleHtmlForSave(bubble) }),
                }).catch(console.error);
            }
        } else {
            bubble.textContent = `⚠️ Network error: ${error.message}`;
        }
    } finally {
        bubble.classList.remove("streaming");
        setStopMode(false);
    }
}

form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = input.value.trim();
    if (!raw || abortController) return; // ignore submit while streaming
    const userMessage = pantryActive ? `I have: ${raw}` : raw;
    if (window.innerWidth < 768) closeSidebar();
    appendUserMessage(userMessage);
    input.value = "";
    input.style.height = "auto";
    exitPantryMode();
    try { await streamResponse(userMessage); }
    finally { input.focus(); }
});

// --- Pantry mode ---
const pantryBtn        = document.getElementById("pantry-btn");
const pantryWelcomeBtn = document.getElementById("pantry-welcome-btn");
const pantryPrefix     = document.getElementById("pantry-prefix");

let pantryActive = false;

function enterPantryMode() {
    pantryActive = true;
    pantryBtn?.classList.add("is-active");
    pantryPrefix?.classList.remove("hidden");
    input.placeholder = "potatoes, garlic, chicken...";
    input.value = "";
    input.dispatchEvent(new Event("input"));
    input.focus();
}

function exitPantryMode() {
    pantryActive = false;
    pantryBtn?.classList.remove("is-active");
    pantryPrefix?.classList.add("hidden");
    input.placeholder = "Ask for a recipe...";
}

pantryBtn?.addEventListener("click", () => {
    if (pantryActive) {
        exitPantryMode();
        input.focus();
    } else {
        enterPantryMode();
    }
});

pantryWelcomeBtn?.addEventListener("click", () => {
    enterPantryMode();
    document.getElementById("chat-form")?.scrollIntoView({ behavior: "smooth", block: "end" });
});
