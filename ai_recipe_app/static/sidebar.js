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
    isOpen ? closeProfileDropdown() : (
        profileDropdown.classList.remove("hidden"),
        profileChevron?.classList.add("rotate-180")
    );
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

document.getElementById("logout-btn")?.addEventListener("click", () => {
    closeProfileDropdown();
    alert("Logout clicked"); // wire to Django logout URL when auth is added
});

// --- Sign-in modal ---
const signinModal   = document.getElementById("signin-modal");
const signinBackdrop = document.getElementById("signin-backdrop");
const signinClose   = document.getElementById("signin-close");
const signinBtn     = document.getElementById("signin-btn");
const stepMain      = document.getElementById("modal-step-main");
const stepOtp       = document.getElementById("modal-step-otp");
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

emailForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        emailError?.classList.remove("hidden");
        emailInput?.classList.add("border-red-400");
        return;
    }
    emailError?.classList.add("hidden");
    emailInput?.classList.remove("border-red-400");
    showOtpStep(email);
});

emailInput?.addEventListener("input", () => {
    emailError?.classList.add("hidden");
    emailInput.classList.remove("border-red-400");
});

otpBack?.addEventListener("click", () => { clearInterval(resendInterval); showMainStep(); });

resendBtn?.addEventListener("click", () => {
    otpInputs.forEach((i) => (i.value = ""));
    otpInputs[0]?.focus();
    startResendTimer();
});

verifyBtn?.addEventListener("click", () => {
    const code = Array.from(otpInputs).map((i) => i.value).join("");
    if (code.length < 6) { otpInputs.forEach((i) => i.classList.add("border-red-400")); return; }
    alert(`OTP submitted: ${code}`); // wire to Django OTP endpoint
    closeSigninModal();
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
