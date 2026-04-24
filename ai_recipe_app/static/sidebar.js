// Shared UI: sidebar toggle, profile dropdown, sign-in modal
// Included in base.html so it runs on every page.

// --- Sidebar toggle (mobile) ---
const sidebar        = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebar-overlay");
const sidebarToggle  = document.getElementById("sidebar-toggle");

function openSidebar() {
    sidebar?.classList.remove("-translate-x-full");
    sidebarOverlay?.classList.remove("hidden");
}

function closeSidebar() {
    sidebar?.classList.add("-translate-x-full");
    sidebarOverlay?.classList.add("hidden");
}

sidebarToggle?.addEventListener("click", () => {
    sidebar.classList.contains("-translate-x-full") ? openSidebar() : closeSidebar();
});

sidebarOverlay?.addEventListener("click", closeSidebar);

// --- Sidebar collapse (desktop) ---
const sidebarCollapseBtn = document.getElementById("sidebar-collapse-btn");
const collapseChevron    = document.getElementById("collapse-chevron");

function setSidebarCollapsed(collapsed) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-collapsed", collapsed);
    if (collapseChevron) {
        // Point right (expand) when collapsed, left (collapse) when expanded
        collapseChevron.innerHTML = collapsed
            ? '<path d="m9 18 6-6-6-6"/>'
            : '<path d="m15 18-6-6 6-6"/>';
    }
    localStorage.setItem("sidebarCollapsed", collapsed);
}

// Restore state on load (desktop only — don't collapse on mobile)
if (window.innerWidth >= 768) {
    setSidebarCollapsed(localStorage.getItem("sidebarCollapsed") === "true");
}

sidebarCollapseBtn?.addEventListener("click", () => {
    setSidebarCollapsed(!sidebar.classList.contains("is-collapsed"));
});

// Wire collapsed new-chat icon to the real new-chat button
document.getElementById("new-chat-btn-icon")?.addEventListener("click", () => {
    document.getElementById("new-chat-btn")?.click();
});

// --- Profile dropdown ---
const profileBtn        = document.getElementById("profile-btn");
const profileDropdown   = document.getElementById("profile-dropdown");
const profileChevron    = document.getElementById("profile-chevron");
const languageToggleBtn = document.getElementById("language-toggle");
const languageSubmenu   = document.getElementById("language-submenu");
const languageArrow     = document.getElementById("language-arrow");

function closeProfileDropdown() {
    profileDropdown?.classList.add("hidden");
    profileChevron?.classList.remove("rotate-180");
    languageSubmenu?.classList.add("hidden");
    languageArrow?.classList.remove("rotate-90");
}

profileBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = !profileDropdown.classList.contains("hidden");
    if (isOpen) {
        closeProfileDropdown();
    } else {
        const rect = profileBtn.getBoundingClientRect();
        profileDropdown.style.left   = rect.left + "px";
        profileDropdown.style.bottom = (window.innerHeight - rect.top + 6) + "px";
        profileDropdown.style.width  = Math.max(220, rect.width) + "px";
        profileDropdown.classList.remove("hidden");
        profileChevron?.classList.add("rotate-180");
    }
});

profileDropdown?.addEventListener("click", (e) => e.stopPropagation());

document.addEventListener("click", closeProfileDropdown);
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeProfileDropdown();
});

languageToggleBtn?.addEventListener("click", () => {
    languageSubmenu?.classList.toggle("hidden");
    languageArrow?.classList.toggle("rotate-90");
});

async function saveLanguage(lang) {
    try {
        const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
        await fetch("/api/set-language/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
            body: JSON.stringify({ language: lang }),
        });
    } catch (e) {
        console.error("Failed to save language:", e);
    }
}

document.querySelectorAll(".language-option").forEach((btn) => {
    btn.addEventListener("click", () => {
        const lang = btn.dataset.lang;
        document.querySelectorAll(".language-option .lang-check").forEach((c) => c.classList.add("hidden"));
        btn.querySelector(".lang-check")?.classList.remove("hidden");
        const label = document.getElementById("active-language-label");
        if (label) label.textContent = lang;
        saveLanguage(lang);
        closeProfileDropdown();
    });
});

document.getElementById("logout-btn")?.addEventListener("click", async () => {
    closeProfileDropdown();
    await fetch("/auth/logout/", {
        method: "POST",
        headers: { "X-CSRFToken": getCSRF() },
    });
    window.location.reload();
});

// --- Sign-in modal ---
const signinModal   = document.getElementById("signin-modal");
const signinBackdrop = document.getElementById("signin-backdrop");
const signinClose   = document.getElementById("signin-close");
const signinBtn     = document.getElementById("signin-btn");
const stepMain      = document.getElementById("modal-step-main");
const stepOtp       = document.getElementById("modal-step-otp");
const stepSuccess   = document.getElementById("modal-step-success");
const emailForm     = document.getElementById("email-form");
const emailInput    = document.getElementById("signin-email");
const emailError    = document.getElementById("email-error");
const otpEmailLabel = document.getElementById("otp-email-display");
const otpBack       = document.getElementById("otp-back");
const verifyBtn     = document.getElementById("verify-btn");
const resendBtn     = document.getElementById("resend-btn");
const resendTimer   = document.getElementById("resend-timer");
const otpInputs     = document.querySelectorAll(".otp-input");

let resendInterval = null;

function openSigninModal() {
    signinModal?.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
    showMainStep();
    setTimeout(() => emailInput?.focus(), 50);
}

function closeSigninModal() {
    signinModal?.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
    clearInterval(resendInterval);
}

function showMainStep() {
    stepMain?.classList.remove("hidden");
    stepOtp?.classList.add("hidden");
    if (emailInput) emailInput.value = "";
    emailError?.classList.add("hidden");
}

function showOtpStep(email) {
    stepMain?.classList.add("hidden");
    stepOtp?.classList.remove("hidden");
    if (otpEmailLabel) otpEmailLabel.textContent = email;
    otpInputs.forEach((i) => (i.value = ""));
    otpInputs[0]?.focus();
    startResendTimer();
}

function startResendTimer() {
    let seconds = 60;
    if (resendBtn) resendBtn.disabled = true;
    if (resendTimer) resendTimer.textContent = ` (${seconds}s)`;
    clearInterval(resendInterval);
    resendInterval = setInterval(() => {
        seconds -= 1;
        if (seconds <= 0) {
            clearInterval(resendInterval);
            if (resendBtn) resendBtn.disabled = false;
            if (resendTimer) resendTimer.textContent = "";
        } else {
            if (resendTimer) resendTimer.textContent = ` (${seconds}s)`;
        }
    }, 1000);
}

signinBtn?.addEventListener("click", openSigninModal);
signinClose?.addEventListener("click", closeSigninModal);
signinBackdrop?.addEventListener("click", closeSigninModal);
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && signinModal && !signinModal.classList.contains("hidden")) closeSigninModal();
});

function getCSRF() {
    return document.querySelector("[name=csrfmiddlewaretoken]")?.value ?? "";
}

emailForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        if (emailError) emailError.textContent = "Please enter a valid email address.";
        emailError?.classList.remove("hidden");
        emailInput?.classList.add("border-red-400");
        return;
    }
    emailError?.classList.add("hidden");
    emailInput?.classList.remove("border-red-400");

    const submitBtn = document.getElementById("email-submit-btn");
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Sending…"; }

    try {
        const res = await fetch("/auth/request-otp/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRF() },
            body: JSON.stringify({ email }),
        });
        const data = await res.json();
        if (!res.ok) {
            if (emailError) emailError.textContent = data.error || "Failed to send code.";
            emailError?.classList.remove("hidden");
            emailInput?.classList.add("border-red-400");
            return;
        }
        showOtpStep(email);
    } catch {
        if (emailError) emailError.textContent = "Network error. Please try again.";
        emailError?.classList.remove("hidden");
    } finally {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Continue with Email"; }
    }
});

emailInput?.addEventListener("input", () => {
    emailError?.classList.add("hidden");
    emailInput.classList.remove("border-red-400");
});

otpBack?.addEventListener("click", () => { clearInterval(resendInterval); showMainStep(); });

resendBtn?.addEventListener("click", async () => {
    const email = otpEmailLabel?.textContent;
    if (!email) return;
    otpInputs.forEach((i) => (i.value = ""));
    otpInputs[0]?.focus();
    startResendTimer();
    await fetch("/auth/request-otp/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRF() },
        body: JSON.stringify({ email }),
    });
});

const otpError = document.getElementById("otp-error");

verifyBtn?.addEventListener("click", async () => {
    const code = Array.from(otpInputs).map((i) => i.value).join("");
    if (code.length < 6) {
        otpInputs.forEach((i) => i.classList.add("border-red-400"));
        return;
    }
    otpError?.classList.add("hidden");
    const email = otpEmailLabel?.textContent;

    if (verifyBtn) { verifyBtn.disabled = true; verifyBtn.textContent = "Verifying…"; }

    try {
        const res = await fetch("/auth/verify-otp/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRF() },
            body: JSON.stringify({ email, code }),
        });
        const data = await res.json();
        if (!res.ok) {
            if (otpError) otpError.textContent = data.error || "Invalid code.";
            otpError?.classList.remove("hidden");
            otpInputs.forEach((i) => i.classList.add("border-red-400"));
            return;
        }
        // Show success loader then reload
        stepMain?.classList.add("hidden");
        stepOtp?.classList.add("hidden");
        if (stepSuccess) { stepSuccess.classList.remove("hidden"); stepSuccess.style.display = "flex"; }
        setTimeout(() => window.location.reload(), 2000);
    } catch {
        if (otpError) otpError.textContent = "Network error. Please try again.";
        otpError?.classList.remove("hidden");
    } finally {
        if (verifyBtn) { verifyBtn.disabled = false; verifyBtn.textContent = "Verify Code"; }
    }
});

otpInputs.forEach((inp, idx) => {
    inp.addEventListener("input", (e) => {
        e.target.value = e.target.value.replace(/\D/g, "");
        e.target.classList.remove("border-red-400");
        if (e.target.value && idx < otpInputs.length - 1) otpInputs[idx + 1].focus();
    });
    inp.addEventListener("keydown", (e) => {
        if (e.key === "Backspace") {
            if (!inp.value && idx > 0) { otpInputs[idx - 1].value = ""; otpInputs[idx - 1].focus(); }
            inp.classList.remove("border-red-400");
        }
    });
    inp.addEventListener("paste", (e) => {
        e.preventDefault();
        const digits = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
        digits.split("").forEach((d, i) => { if (otpInputs[idx + i]) otpInputs[idx + i].value = d; });
        otpInputs[Math.min(idx + digits.length, otpInputs.length - 1)]?.focus();
    });
});
