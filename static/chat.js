// Chat-page only logic. sidebar.js handles sidebar/modal/profile (loaded via base.html).

const form        = document.getElementById("chat-form");
const input       = document.getElementById("message-input");
const messageList = document.getElementById("message-list");
const welcomeScreen = document.getElementById("welcome-screen");
const sendBtn     = document.getElementById("send-btn");
const newChatBtn  = document.getElementById("new-chat-btn");
const headerNewChatBtn = document.getElementById("header-new-chat-btn");

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

// Unit converter — metric/imperial toggle
const UNIT_TOGGLE_KEY = "recipeUnitPref";
const IMP_TO_MET = {
  cup: { factor: 240, to: "ml" }, cups: { factor: 240, to: "ml" },
  tablespoon: { factor: 15, to: "ml" }, tablespoons: { factor: 15, to: "ml" }, tbsp: { factor: 15, to: "ml" },
  teaspoon:   { factor: 5,  to: "ml" }, teaspoons:   { factor: 5,  to: "ml" }, tsp:  { factor: 5,  to: "ml" },
  "fl oz": { factor: 30, to: "ml" },
  oz:      { factor: 28, to: "g"  },
  lb:      { factor: 454, to: "g" }, pound: { factor: 454, to: "g" }, pounds: { factor: 454, to: "g" },
};
const QTY_UNIT_RE = /^((?:\d+\s+)?\d+\/\d+|\d*[.,]?\d+|[¼½¾⅓⅔⅛⅜⅝⅞])\s*(fl oz|tablespoons?|tbsp|teaspoons?|tsp|cups?|oz|lbs?|pounds?|ml|g|kg|liters?|litres?|l)\b/i;

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

// Header "New Chat" button delegates to the sidebar new-chat button
document.getElementById("header-new-chat-btn")?.addEventListener("click", () => {
    newChatBtn?.click();
});

// New chat — reset to welcome screen
newChatBtn?.addEventListener("click", () => {
    messageList?.querySelectorAll(".chat-msg").forEach((el) => el.remove());
    if (welcomeScreen) welcomeScreen.style.display = "";
    hasMessages = false;
    currentChatId = null;
    history.pushState(null, "", "/chat/");
    updateHeaderTitle("");
    // Clear active highlight from sidebar
    document.querySelectorAll("#sidebar-history a").forEach((a) => {
        a.className = "flex items-center px-3 py-2 text-xs rounded-md truncate transition-colors text-zinc-500 hover:bg-zinc-800/80 hover:text-zinc-200";
    });
    document.querySelectorAll("#sidebar-history .chat-item").forEach((item) => {
        item.classList.remove("bg-zinc-800/60");
    });
    document.querySelectorAll("#sidebar-history .chat-menu-btn").forEach((btn) => {
        btn.classList.remove("opacity-100");
        btn.classList.add("opacity-0");
    });
    if (input) { input.value = ""; input.style.height = "auto"; input.focus(); }
    document.getElementById("share-btn")?.classList.add("hidden");
    headerNewChatBtn?.classList.add("hidden");
});

function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

// ── Header chat title ────────────────────────────────────────────────────────
const titleWrap    = document.getElementById("chat-title-wrap");
const titleDisplay = document.getElementById("chat-title-display");
const titlePencil  = document.getElementById("chat-title-pencil");
const titleInput   = document.getElementById("chat-title-input");

function updateHeaderTitle(title) {
    if (!titleDisplay) return;
    titleDisplay.textContent = title || "";
    if (titleWrap) titleWrap.classList.toggle("invisible", !title);
}

function startTitleEdit() {
    if (!titleInput || !titleDisplay) return;
    titleInput.value = titleDisplay.textContent.trim();
    titleDisplay.classList.add("hidden");
    titlePencil?.classList.add("hidden");
    titleInput.classList.remove("hidden");
    titleInput.focus();
    titleInput.select();
}

async function commitTitleEdit() {
    const newTitle = titleInput.value.trim();
    const oldTitle = titleDisplay.textContent.trim();
    titleInput.classList.add("hidden");
    titleDisplay.classList.remove("hidden");
    titlePencil?.classList.remove("hidden");
    if (!newTitle || newTitle === oldTitle || !currentChatId) return;
    titleDisplay.textContent = newTitle;
    // Sync sidebar link if present
    const sidebarLink = document.querySelector(`.chat-menu-btn[data-chat-id="${currentChatId}"]`);
    if (sidebarLink) {
        sidebarLink.dataset.chatTitle = newTitle;
        const a = sidebarLink.closest(".chat-item")?.querySelector("a");
        if (a) a.textContent = newTitle;
    }
    await fetch("/chat/api/rename-chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify({ chat_id: currentChatId, title: newTitle }),
    }).catch(console.error);
}

titleDisplay?.addEventListener("click", startTitleEdit);
titlePencil?.addEventListener("click",  startTitleEdit);
titleInput?.addEventListener("blur",    commitTitleEdit);
titleInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter")  { e.preventDefault(); titleInput.blur(); }
    if (e.key === "Escape") { titleInput.value = titleDisplay.textContent; titleInput.blur(); }
});
// ────────────────────────────────────────────────────────────────────────────

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

const META_ICONS = {
    "Prep":         `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
    "Cook":         `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`,
    "Serves":       `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>`,
    "Difficulty":   `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`,
    "Pantry match": `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 11 4-7"/><path d="m19 11-4-7"/><path d="M2 11h20"/><path d="m3.5 11 1.6 7.4a2 2 0 0 0 2 1.6h9.8a2 2 0 0 0 2-1.6l1.7-7.4"/><path d="m9 11 1 9"/><path d="M4.5 15.5h15"/><path d="m15 11-1 9"/></svg>`,
    "Missing":      `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>`,
};

function styleRecipeMeta(p) {
    if (p.querySelector(".recipe-meta-chip")) return;
    const segments = p.textContent.trim().split(/[|·\n]/).map(s => s.trim()).filter(Boolean);
    const chips = [];
    segments.forEach(seg => {
        const colon = seg.indexOf(":");
        if (colon === -1) return;
        const key = seg.slice(0, colon).trim();
        const val = seg.slice(colon + 1).trim();
        const icon = META_ICONS[key];
        if (!icon) return;
        if (key === "Pantry match") chips.push(`<span class="recipe-meta-divider"></span>`);
        const diffClass = key === "Difficulty" ? ` recipe-meta-chip--${val.toLowerCase()}` : "";
        chips.push(`<span class="recipe-meta-chip${diffClass}">${icon}<b>${key}</b>${val}</span>`);
    });
    if (chips.length) p.innerHTML = chips.join("");
}

function parseFraction(str) {
    const UNICODE_FRACS = {
        "¼": 0.25, "½": 0.5, "¾": 0.75,
        "⅓": 1/3,  "⅔": 2/3,
        "⅛": 0.125,"⅜": 0.375,"⅝": 0.625,"⅞": 0.875,
    };
    str = str.trim();
    if (UNICODE_FRACS[str]) return UNICODE_FRACS[str];
    const mixed = str.match(/^(\d+)\s+(\d+)\/(\d+)$/);
    if (mixed) return parseInt(mixed[1]) + parseInt(mixed[2]) / parseInt(mixed[3]);
    const simple = str.match(/^(\d+)\/(\d+)$/);
    if (simple) return parseInt(simple[1]) / parseInt(simple[2]);
    return parseFloat(str.replace(",", "."));
}

function formatQuantity(num) {
    const FRACS = [[1/8,"⅛"],[1/4,"¼"],[1/3,"⅓"],[1/2,"½"],[2/3,"⅔"],[3/4,"¾"]];
    if (num < 10) {
        const whole = Math.floor(num);
        const frac  = num - whole;
        for (const [val, sym] of FRACS) {
            if (Math.abs(frac - val) < 0.07) {
                return whole > 0 ? `${whole} ${sym}` : sym;
            }
        }
    }
    if (num >= 100) return Math.round(num).toString();
    if (Number.isInteger(num)) return num.toString();
    return parseFloat(num.toFixed(1)).toString();
}

function convertQtyUnit(qty, unitRaw, direction) {
    const unit = unitRaw.toLowerCase().trim();
    const num  = parseFraction(qty);

    if (direction === "metric") {
        const rule = IMP_TO_MET[unit];
        if (!rule) return { qty, unit: unitRaw, changed: false };
        const converted = num * rule.factor;
        return { qty: formatQuantity(converted), unit: rule.to, changed: true };
    }

    if (unit === "ml") {
        const mlNum = num;
        if (mlNum >= 960) {
            return { qty: formatQuantity(mlNum / 240), unit: "cups", changed: true };
        } else if (mlNum >= 15) {
            const tbsp = mlNum / 15;
            if (Number.isInteger(tbsp) || Math.abs(tbsp - Math.round(tbsp)) < 0.1) {
                return { qty: formatQuantity(tbsp), unit: "tbsp", changed: true };
            }
            return { qty: formatQuantity(mlNum / 5), unit: "tsp", changed: true };
        } else {
            return { qty: formatQuantity(mlNum / 5), unit: "tsp", changed: true };
        }
    }
    if (unit === "g") {
        if (num >= 454) return { qty: formatQuantity(num / 454), unit: "lb", changed: true };
        return { qty: formatQuantity(num / 28), unit: "oz", changed: true };
    }
    if (unit === "kg") {
        return { qty: formatQuantity(num * 2.205), unit: "lb", changed: true };
    }
    return { qty, unit: unitRaw, changed: false };
}

function _detectDefaultPref(ul) {
    let metricCount = 0, imperialCount = 0;
    ul.querySelectorAll("li").forEach((li) => {
        if (!li.dataset.origUnit) return;
        const u = li.dataset.origUnit.toLowerCase().trim();
        if (IMP_TO_MET[u]) imperialCount++;
        else if (["ml","g","kg","l","liter","litre","liters","litres"].includes(u)) metricCount++;
    });
    return imperialCount >= metricCount ? "imperial" : "metric";
}

function _applyUnitPref(ul, toggleWrap, pref) {
    toggleWrap.querySelectorAll(".unit-toggle-btn").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.unit === pref);
    });

    ul.querySelectorAll("li").forEach((li) => {
        if (!li.dataset.origText) return;
        if (li.dataset.unitChanged === "0") return;

        const target = li.querySelector("p") || li;
        let textNode = null;
        for (const node of target.childNodes) {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                textNode = node; break;
            }
        }
        if (!textNode) return;

        const suffix = li.dataset.origSuffix;
        if (pref === "metric") {
            textNode.textContent = `${li.dataset.metricQty} ${li.dataset.metricUnit}${suffix}`;
        } else {
            textNode.textContent = `${li.dataset.imperialQty} ${li.dataset.imperialUnit}${suffix}`;
        }
    });
}

function injectUnitToggle(bubble) {
    if (bubble.dataset.unitToggleInit) return;

    let ingredientsUl = null;
    bubble.querySelectorAll("h2").forEach((h2) => {
        if (h2.textContent.includes("🧂")) {
            let el = h2.nextElementSibling;
            while (el && el.tagName !== "UL") el = el.nextElementSibling;
            if (el?.tagName === "UL") ingredientsUl = el;
        }
    });
    if (!ingredientsUl) { bubble.dataset.unitToggleInit = "1"; return; }

    let hasImperial = false, hasMetric = false;

    ingredientsUl.querySelectorAll("li").forEach((li) => {
        const target = li.querySelector("p") || li;
        let textNode = null;
        for (const node of target.childNodes) {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                textNode = node; break;
            }
        }
        if (!textNode) return;

        const rawText = textNode.textContent;
        const match   = rawText.match(QTY_UNIT_RE);
        if (!match) return;

        const origQty  = match[1];
        const origUnit = match[2];
        const unitLow  = origUnit.toLowerCase().trim();

        const isImperial = !!IMP_TO_MET[unitLow];
        const isMetric   = ["ml", "g", "kg", "l", "liter", "litre", "liters", "litres"].includes(unitLow);

        if (isImperial) hasImperial = true;
        if (isMetric)   hasMetric   = true;

        const metricResult   = convertQtyUnit(origQty, origUnit, "metric");
        const imperialResult = convertQtyUnit(origQty, origUnit, "imperial");

        const suffix = rawText.slice(match[0].length);

        li.dataset.origText      = rawText;
        li.dataset.origQty       = origQty;
        li.dataset.origUnit      = origUnit;
        li.dataset.origSuffix    = suffix;
        li.dataset.metricQty     = metricResult.qty;
        li.dataset.metricUnit    = metricResult.unit;
        li.dataset.imperialQty   = imperialResult.qty;
        li.dataset.imperialUnit  = imperialResult.unit;
        li.dataset.unitChanged   = metricResult.changed || imperialResult.changed ? "1" : "0";
    });

    if (!hasImperial && !hasMetric) {
        bubble.dataset.unitToggleInit = "1";
        return;
    }

    const toggleWrap = document.createElement("div");
    toggleWrap.className = "unit-toggle-wrap";

    const metricBtn   = document.createElement("button");
    metricBtn.type    = "button";
    metricBtn.className = "unit-toggle-btn";
    metricBtn.dataset.unit = "metric";
    metricBtn.textContent = "Metric";

    const imperialBtn   = document.createElement("button");
    imperialBtn.type    = "button";
    imperialBtn.className = "unit-toggle-btn";
    imperialBtn.dataset.unit = "imperial";
    imperialBtn.textContent = "Imperial";

    toggleWrap.appendChild(metricBtn);
    toggleWrap.appendChild(imperialBtn);

    ingredientsUl.insertAdjacentElement("beforebegin", toggleWrap);

    const pref = localStorage.getItem(UNIT_TOGGLE_KEY) || _detectDefaultPref(ingredientsUl);
    _applyUnitPref(ingredientsUl, toggleWrap, pref);

    toggleWrap.addEventListener("click", (e) => {
        const btn = e.target.closest(".unit-toggle-btn");
        if (!btn) return;
        const chosen = btn.dataset.unit;
        localStorage.setItem(UNIT_TOGGLE_KEY, chosen);
        _applyUnitPref(ingredientsUl, toggleWrap, chosen);
    });

    bubble.dataset.unitToggleInit = "1";
}

function applyRecipeStyles(bubble) {
    bubble.querySelectorAll("p").forEach((p) => {
        if (p.textContent.includes("Prep:") && p.textContent.includes("Cook:")) {
            p.classList.add("recipe-meta");
            styleRecipeMeta(p);
        }
    });
    injectCountryBadge(bubble);
    injectUnitToggle(bubble);
    stylePantryIngredients(bubble);
    styleNutritionTable(bubble);
    styleMealPlanTable(bubble);
    animateInstructions(bubble);
    styleFollowUpSuggestions(bubble);
    injectRecipeImage(bubble);
}

async function injectYouTubeVideos(bubble) {
    if (bubble.dataset.ytState || bubble.querySelector(".recipe-videos")) return;
    bubble.dataset.ytState = "loading";

    const dishName = (bubble.querySelector("h1")?.textContent ?? "")
        .replace(/\p{Emoji}/gu, "").trim();
    if (!dishName) { delete bubble.dataset.ytState; return; }

    try {
        const res  = await fetch(`/chat/api/youtube-videos/?q=${encodeURIComponent(dishName)}`);
        const data = await res.json();
        if (!data.videos?.length || !bubble.isConnected) return;

        const section = document.createElement("div");
        section.className = "recipe-videos";

        section.innerHTML = `
            <div class="recipe-videos-header">
                <div class="recipe-videos-icon-wrap">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                </div>
                <div class="recipe-videos-text">
                    <p class="recipe-videos-title">Watch &amp; Learn</p>
                    <p class="recipe-videos-subtitle">Hand-picked video tutorials</p>
                </div>
            </div>
        `;

        const grid = document.createElement("div");
        grid.className = "recipe-videos-grid";

        data.videos.forEach((v, idx) => {
            const initial = (v.channel?.[0] ?? "Y").toUpperCase();
            const total   = data.videos.length;
            const card = document.createElement("div");
            card.className = "recipe-video-card";
            card.innerHTML =
                `<div class="recipe-video-thumb" data-vid="${v.id}">` +
                    `<img src="${v.thumbnail}" alt="${v.title}" loading="lazy" class="recipe-video-img">` +
                    `<div class="recipe-video-overlay"></div>` +
                    `<div class="recipe-video-play">` +
                        `<span class="recipe-video-play-btn"><svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M8 5v14l11-7z"/></svg></span>` +
                    `</div>` +
                    `<span class="recipe-video-badge">${idx + 1}/${total}</span>` +
                    `<span class="recipe-video-watch-pill"><svg viewBox="0 0 24 24" fill="currentColor" width="10" height="10"><path d="M8 5v14l11-7z"/></svg>Watch</span>` +
                `</div>` +
                `<div class="recipe-video-info">` +
                    `<p class="recipe-video-title">${v.title}</p>` +
                    `<div class="recipe-video-meta">` +
                        `<span class="recipe-video-avatar">${initial}</span>` +
                        `<span class="recipe-video-channel">${v.channel}</span>` +
                        `<span class="recipe-video-yt-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg></span>` +
                    `</div>` +
                `</div>`;
            grid.appendChild(card);
        });

        section.appendChild(grid);
        bubble.appendChild(section);
    } catch {
        // silently skip if API unavailable or key not set
    } finally {
        delete bubble.dataset.ytState;
    }
}

function styleFollowUpSuggestions(bubble) {
    const contentWrap = bubble.parentElement;
    // Guard: chips already placed outside bubble
    if (contentWrap?.querySelector(".followup-chips")) return;
    // Also migrate any old chips that are still inside the bubble
    const oldChips = bubble.querySelector(".followup-chips");
    if (oldChips) { bubble.insertAdjacentElement("afterend", oldChips); return; }

    let h2 = null;
    bubble.querySelectorAll("h2").forEach(el => {
        if (el.textContent.includes("💬")) h2 = el;
    });
    if (!h2) return;

    let ul = h2.nextElementSibling;
    while (ul && ul.tagName !== "UL") ul = ul.nextElementSibling;
    if (!ul) return;

    const questions = [...ul.querySelectorAll("li")]
        .map(li => li.textContent.trim())
        .filter(Boolean);
    if (!questions.length) return;

    // Hide heading and list inside bubble (keep in DOM so saved HTML preserves them for history reloads)
    h2.style.display = "none";
    ul.style.display = "none";

    // Store the recipe name so the click handler can anchor the question to the right dish
    const recipeName = (bubble.querySelector("h1")?.textContent ?? "")
        .replace(/\p{Emoji}/gu, "").trim();

    const wrapper = document.createElement("div");
    wrapper.className = "followup-chips";
    if (recipeName) wrapper.dataset.recipe = recipeName;
    questions.forEach(q => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "followup-chip";
        btn.textContent = q;
        wrapper.appendChild(btn);
    });

    // Place chips after the bubble, outside it
    bubble.insertAdjacentElement("afterend", wrapper);
}

function injectCountryBadge(bubble) {
    if (bubble.querySelector(".recipe-country-badge")) return;
    const match = bubble.innerHTML.match(/<!--\s*country:\s*(.+?)\s*-->/);
    if (!match) return;
    const h1 = bubble.querySelector("h1");
    if (!h1) return;
    const badge = document.createElement("div");
    badge.className = "recipe-country-badge";
    badge.textContent = match[1].trim();
    h1.insertAdjacentElement("afterend", badge);
}

function styleMealPlanTable(bubble) {
    const h1 = bubble.querySelector("h1");
    const txt = h1 ? h1.textContent.toLowerCase() : "";
    const isMealPlan = txt.includes("🗓") || txt.includes("meal plan") || txt.includes("-day meal");
    if (!isMealPlan) return;
    bubble.classList.add("meal-plan-bubble");
    if (bubble.querySelector(".meal-plan-scroll")) return;
    const table = bubble.querySelector("table");
    if (!table) return;
    table.classList.add("meal-plan-table");
    const wrapper = document.createElement("div");
    wrapper.className = "meal-plan-scroll";
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
}

// ── Floating step tooltip ──
const TOOLTIP_MODE_COLORS = {
    "Pantry":    { bg: "#16a34a", text: "#fff" },
    "Meal Plan": { bg: "#7c3aed", text: "#fff" },
    "Recipe":    { bg: "#f97316", text: "#fff" },
};
const TOOLTIP_MODE_COLORS_DARK = {
    "Pantry":    { bg: "#15803d", text: "#d1fae5" },
    "Meal Plan": { bg: "#6d28d9", text: "#ede9fe" },
    "Recipe":    { bg: "#c2410c", text: "#ffedd5" },
};

function _tooltipModeFromBubble(li) {
    const bubble = li.closest(".bot-bubble");
    if (!bubble) return "Recipe";
    if (bubble.classList.contains("pantry-bubble"))    return "Pantry";
    if (bubble.classList.contains("meal-plan-bubble")) return "Meal Plan";
    return "Recipe";
}

let _stepTooltipEl = null;
function showStepTooltip(e) {
    if (e.currentTarget.dataset.expanded === "1") return;
    if (!_stepTooltipEl) {
        _stepTooltipEl = document.createElement("div");
        _stepTooltipEl.className = "step-tooltip";
        _stepTooltipEl.textContent = "Tap for tips";
        document.body.appendChild(_stepTooltipEl);
    }
    const isDark  = document.documentElement.getAttribute("data-theme") === "dark";
    const mode    = _tooltipModeFromBubble(e.currentTarget);
    const palette = (isDark ? TOOLTIP_MODE_COLORS_DARK : TOOLTIP_MODE_COLORS)[mode];
    _stepTooltipEl.style.background = palette.bg;
    _stepTooltipEl.style.color      = palette.text;

    const r = e.currentTarget.getBoundingClientRect();
    _stepTooltipEl.style.top  = (r.top - 28) + "px";
    _stepTooltipEl.style.left = (r.left + r.width / 2 - _stepTooltipEl.offsetWidth / 2) + "px";
    _stepTooltipEl.classList.add("visible");
}
function hideStepTooltip() {
    _stepTooltipEl?.classList.remove("visible");
}

function animateInstructions(bubble) {
    if (bubble.dataset.instructionsAnimated) return;
    bubble.querySelectorAll("h2").forEach(h2 => {
        if (h2.textContent.includes("👨") || h2.textContent.toLowerCase().includes("instruction")) {
            let el = h2.nextElementSibling;
            while (el && el.tagName !== "OL") el = el.nextElementSibling;
            if (!el) return;
            const recipeName = bubble.querySelector("h1")?.textContent.replace(/\p{Emoji}/gu, "").trim() ?? "";
            el.querySelectorAll("li").forEach((li, i) => {
                li.style.animationDelay = `${i * 0.09}s`;
                li.classList.add("instruction-step-animated", "instruction-expandable");
                // Store plain step text before we append any children
                li.dataset.stepText = li.textContent.trim();
                li.addEventListener("click", () => expandStep(li, recipeName));
                li.addEventListener("mouseenter", showStepTooltip);
                li.addEventListener("mouseleave", hideStepTooltip);
            });
        }
    });
    bubble.dataset.instructionsAnimated = "1";
}

async function expandStep(li, recipeName) {
    if (li.dataset.loading === "1") return;

    if (li.dataset.expanded === "1") {
        const detail = li.querySelector(".step-detail");
        if (detail) {
            detail.classList.add("step-detail-collapsing");
            setTimeout(() => { detail.remove(); }, 250);
        }
        li.dataset.expanded = "0";
        li.classList.remove("step-expanded");
        return;
    }

    // Already fetched — just re-show from cache
    if (li.dataset.detailText) {
        renderStepDetail(li, li.dataset.detailText);
        return;
    }

    // First fetch — show loader
    li.dataset.loading = "1";
    li.classList.add("step-loading");

    const loader = document.createElement("div");
    loader.className = "step-loader";
    loader.innerHTML = `
        <span class="step-spinner"></span>
        <span class="step-loader-text">Getting cooking tips…</span>
    `;
    li.appendChild(loader);

    const stepText = (li.dataset.stepText || li.childNodes[0]?.textContent || li.textContent).trim();

    try {
        const res = await fetch("/chat/api/step-detail/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
            body: JSON.stringify({ recipe: recipeName, step: stepText }),
        });
        const data = await res.json();
        loader.remove();
        if (data.detail) {
            li.dataset.detailText = data.detail;
            renderStepDetail(li, data.detail);
        }
    } catch (_) {
        loader.remove();
        li.querySelector(".step-hint")?.classList.remove("hidden");
    }

    li.dataset.loading = "0";
    li.classList.remove("step-loading");
}

function renderStepDetail(li, text) {
    const div = document.createElement("div");
    div.className = "step-detail";
    div.innerHTML = `
        <div class="step-detail-icon">💡</div>
        <p class="step-detail-text">${text}</p>
    `;
    li.appendChild(div);
    li.dataset.expanded = "1";
    li.classList.add("step-expanded");
}

function styleNutritionTable(bubble) {
    if (bubble.querySelector(".nutrition-grid")) return;

    let nutritionH2 = null;
    bubble.querySelectorAll("h2").forEach(h2 => {
        if (h2.textContent.includes("📊") || h2.textContent.toLowerCase().includes("nutrition")) {
            nutritionH2 = h2;
        }
    });
    if (!nutritionH2) return;

    let table = nutritionH2.nextElementSibling;
    while (table && table.tagName !== "TABLE") table = table.nextElementSibling;
    if (!table) return;

    const headers = [...table.querySelectorAll("thead th")].map(th => th.textContent.trim());
    const values  = [...table.querySelectorAll("tbody td")].map(td => td.textContent.trim());

    const MACROS = [
        { key: "Calories", icon: "🔥", cls: "nutrition-card--cal"     },
        { key: "Protein",  icon: "💪", cls: "nutrition-card--protein"  },
        { key: "Carbs",    icon: "🌾", cls: "nutrition-card--carbs"    },
        { key: "Fat",      icon: "🥑", cls: "nutrition-card--fat"      },
    ];

    const grid = document.createElement("div");
    grid.className = "nutrition-grid";

    MACROS.forEach(({ key, icon, cls }) => {
        const idx = headers.indexOf(key);
        if (idx === -1) return;
        const val = values[idx] || "—";
        const card = document.createElement("div");
        card.className = `nutrition-card ${cls}`;
        card.innerHTML =
            `<span class="nutrition-icon">${icon}</span>` +
            `<span class="nutrition-value">${val}</span>` +
            `<span class="nutrition-label">${key}</span>`;
        grid.appendChild(card);
    });

    if (grid.children.length) table.replaceWith(grid);
}

function stylePantryIngredients(bubble) {
    if (bubble.textContent.includes("Pantry match")) bubble.classList.add("pantry-bubble");
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
    const clone = bubble.cloneNode(true);
    clone.querySelectorAll(
        ".recipe-hero-placeholder, .recipe-hero-single, .recipe-image-grid, .recipe-images-section, .unit-toggle-wrap"
    ).forEach(el => el.remove());
    clone.querySelectorAll("li[data-orig-text]").forEach((li) => {
        const target = li.querySelector("p") || li;
        for (const node of target.childNodes) {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                node.textContent = li.dataset.origText;
                break;
            }
        }
    });
    return clone.innerHTML;
}

async function injectRecipeImage(bubble) {
    if (bubble.dataset.imgState || bubble.querySelector(".recipe-hero-img, .recipe-image-grid, .recipe-images-section")) return;
    bubble.dataset.imgState = "loading";

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

        const cameraSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>`;
        const zoomSvg   = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`;

        const section = document.createElement("div");
        section.className = "recipe-images-section";
        section.innerHTML = `
          <div class="recipe-images-header">
            <div class="recipe-images-header-icon">${cameraSvg}</div>
            <div class="recipe-images-header-text">
              <span class="recipe-images-header-title">Recipe Gallery</span>
              <span class="recipe-images-header-sub">Visual reference · Wikipedia</span>
            </div>
            <span class="recipe-images-count-badge">${srcs.length} photo${srcs.length > 1 ? "s" : ""}</span>
          </div>`;

        const grid = document.createElement("div");
        grid.className = `recipe-img-grid recipe-img-grid--${srcs.length}`;

        srcs.forEach((src, i) => {
            const card = document.createElement("div");
            card.className = "recipe-image-card";

            const img   = document.createElement("img");
            img.src     = src;
            img.alt     = `${label} — photo ${i + 1}`;
            img.className = "recipe-hero-img";
            img.loading = "lazy";
            img.onerror = () => card.remove();

            const overlay = document.createElement("div");
            overlay.className = "recipe-image-overlay";
            overlay.innerHTML = `
              <span class="recipe-image-card-label">${label}</span>
              <span class="recipe-image-card-counter">${i + 1}/${srcs.length}</span>`;

            const zoomBtn = document.createElement("div");
            zoomBtn.className = "recipe-image-zoom-btn";
            zoomBtn.innerHTML = zoomSvg;

            card.appendChild(img);
            card.appendChild(overlay);
            card.appendChild(zoomBtn);
            grid.appendChild(card);
        });

        section.appendChild(grid);
        placeholder.replaceWith(section);
    } catch {
        placeholder.remove();
    } finally {
        delete bubble.dataset.imgState;
    }
}

function showMessages() {
    if (!hasMessages) { hasMessages = true; if (welcomeScreen) welcomeScreen.style.display = "none"; document.getElementById("share-btn")?.classList.remove("hidden"); headerNewChatBtn?.classList.remove("hidden"); }
}

// Apply to any history bubbles already in the DOM.
// First strip any stale placeholders that were accidentally persisted before this fix.
document.querySelectorAll(".bot-bubble .recipe-hero-placeholder").forEach(el => el.remove());
document.querySelectorAll(".bot-bubble").forEach(bubble => {
    applyRecipeStyles(bubble);
    injectYouTubeVideos(bubble); // no-op if videos already in saved HTML; fallback for old messages
});

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
// Follow-up chip clicks — delegated so history bubbles work too
messageList?.addEventListener("click", (e) => {
    const chip = e.target.closest(".followup-chip");
    if (!chip || abortController) return;
    const recipe = chip.closest(".followup-chips")?.dataset.recipe;
    // Anchor question to the specific recipe so multi-recipe sessions don't confuse the LLM
    input.value = recipe ? `For the ${recipe}: ${chip.textContent.trim()}` : chip.textContent.trim();
    input.dispatchEvent(new Event("input"));
    form.requestSubmit();
});

// YouTube thumbnail → inline iframe
messageList?.addEventListener("click", (e) => {
    const thumb = e.target.closest(".recipe-video-thumb");
    if (!thumb) return;
    const vid = thumb.dataset.vid;
    if (!vid) return;
    const iframe = document.createElement("iframe");
    iframe.src = `https://www.youtube.com/embed/${vid}?autoplay=1`;
    iframe.className = "recipe-video-iframe";
    iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.allowFullscreen = true;
    thumb.replaceWith(iframe);
});

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
                            updateHeaderTitle(data.chat_title || userMessage);
                        }
                        if (streamChatId) {
                            // Fetch YouTube videos first so they're included in the saved HTML
                            // and never need to be re-fetched on history reload.
                            await injectYouTubeVideos(bubble);
                            fetch("/chat/api/save-bot-message/", {
                                method: "POST",
                                headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                                body: JSON.stringify({ chat_id: streamChatId, content: bubbleHtmlForSave(bubble), markdown: fullText }),
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
                    updateHeaderTitle(userMessage);
                }
                fetch("/chat/api/save-bot-message/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                    body: JSON.stringify({ chat_id: saveId, content: bubbleHtmlForSave(bubble), markdown: fullText }),
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
    const userMessage = pantryActive ? `I have: ${raw}` : mealPlanActive ? `Meal plan: ${raw}` : raw;
    if (window.innerWidth < 768) closeSidebar();
    appendUserMessage(userMessage);
    input.value = "";
    input.style.height = "auto";
    exitPantryMode();
    exitMealPlanMode();
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
    exitMealPlanMode();
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

// --- Meal plan mode ---
const mealPlanBtn        = document.getElementById("meal-plan-btn");
const mealPlanWelcomeBtn = document.getElementById("meal-plan-welcome-btn");
const mealPlanPrefix     = document.getElementById("meal-plan-prefix");

let mealPlanActive = false;

function enterMealPlanMode() {
    mealPlanActive = true;
    exitPantryMode();
    mealPlanBtn?.classList.add("is-active");
    mealPlanPrefix?.classList.remove("hidden");
    input.placeholder = "7 days, vegetarian, low-carb…";
    input.value = "";
    input.dispatchEvent(new Event("input"));
    input.focus();
}

function exitMealPlanMode() {
    mealPlanActive = false;
    mealPlanBtn?.classList.remove("is-active");
    mealPlanPrefix?.classList.add("hidden");
    input.placeholder = "Ask for a recipe...";
}

mealPlanBtn?.addEventListener("click", () => {
    if (mealPlanActive) { exitMealPlanMode(); input.focus(); }
    else { enterMealPlanMode(); }
});

mealPlanWelcomeBtn?.addEventListener("click", () => {
    enterMealPlanMode();
    document.getElementById("chat-form")?.scrollIntoView({ behavior: "smooth", block: "end" });
});
