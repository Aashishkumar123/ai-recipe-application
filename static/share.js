// Share modal logic — loaded only on the chat page.

const shareBtn          = document.getElementById("share-btn");
const shareModal        = document.getElementById("share-modal");
const shareBackdrop     = document.getElementById("share-backdrop");
const shareModalClose   = document.getElementById("share-modal-close");
const shareStatePrivate = document.getElementById("share-state-private");
const shareStatePublic  = document.getElementById("share-state-public");
const shareLoading      = document.getElementById("share-loading");
const sharePublicUrl    = document.getElementById("share-public-url");
const shareCopyBtn      = document.getElementById("share-copy-btn");
const shareMakePublic   = document.getElementById("share-make-public-btn");
const shareMakePrivate  = document.getElementById("share-make-private-btn");
const shareKeepPrivate  = document.getElementById("share-keep-private-btn");
const shareDoneBtn      = document.getElementById("share-done-btn");

// Synced with server — updated after each toggle
let chatIsPublic = typeof _chatIsPublic !== "undefined" ? _chatIsPublic : false;

function getCsrf() {
    return document.querySelector("[name=csrfmiddlewaretoken]")?.value ?? "";
}

function getActiveChatId() {
    // Prefer the JS-tracked ID (chat.js sets currentChatId), fall back to URL
    if (typeof currentChatId !== "undefined" && currentChatId) return currentChatId;
    const parts = window.location.pathname.replace(/\/$/, "").split("/");
    const last = parts[parts.length - 1];
    return last.length === 36 ? last : null;
}

function showShareState(isPublic, publicUrl) {
    chatIsPublic = isPublic;
    shareStatePrivate.classList.toggle("hidden", isPublic);
    shareStatePublic.classList.toggle("hidden", !isPublic);
    if (isPublic && publicUrl) sharePublicUrl.textContent = publicUrl;
}

function openShareModal() {
    const chatId = getActiveChatId();
    if (!chatId) {
        alert("Send a message first before sharing.");
        return;
    }
    // Reset copy button label
    if (shareCopyBtn) shareCopyBtn.textContent = "Copy";
    showShareState(chatIsPublic, sharePublicUrl?.textContent || "");
    shareModal?.classList.remove("hidden");
}

function closeShareModal() {
    shareModal?.classList.add("hidden");
}

shareBtn?.addEventListener("click", openShareModal);
shareModalClose?.addEventListener("click", closeShareModal);
shareBackdrop?.addEventListener("click", closeShareModal);
shareKeepPrivate?.addEventListener("click", closeShareModal);
shareDoneBtn?.addEventListener("click", closeShareModal);

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && shareModal && !shareModal.classList.contains("hidden")) closeShareModal();
});

async function toggleShare(makePublic) {
    const chatId = getActiveChatId();
    if (!chatId) return;

    shareLoading?.classList.remove("hidden");
    try {
        const res = await fetch("/chat/api/share-chat/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
            body: JSON.stringify({ chat_id: chatId, public: makePublic }),
        });
        const data = await res.json();
        if (!res.ok) { alert(data.error || "Failed to update share settings."); return; }
        showShareState(data.is_public, data.public_url);
    } catch (err) {
        console.error("Share toggle error", err);
        alert("Network error. Please try again.");
    } finally {
        shareLoading?.classList.add("hidden");
    }
}

shareMakePublic?.addEventListener("click",  () => toggleShare(true));
shareMakePrivate?.addEventListener("click", () => toggleShare(false));

shareCopyBtn?.addEventListener("click", async () => {
    const url = sharePublicUrl?.textContent?.trim();
    if (!url) return;
    try {
        await navigator.clipboard.writeText(url);
        shareCopyBtn.textContent = "Copied!";
        setTimeout(() => { shareCopyBtn.textContent = "Copy"; }, 2000);
    } catch {
        // Fallback for browsers that don't allow clipboard in certain contexts
        sharePublicUrl?.select?.();
    }
});
