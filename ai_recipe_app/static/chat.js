const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const sendBtn = document.getElementById("send-btn");

function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

function createMessageBubble(sender) {
    const wrapper = document.createElement("div");
    wrapper.classList.add("message", `message--${sender}`);

    const bubble = document.createElement("div");
    bubble.classList.add("message-bubble");

    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
}

function addMessage(content, sender, isMarkdown = false) {
    const bubble = createMessageBubble(sender);
    if (isMarkdown) {
        bubble.innerHTML = marked.parse(content);
    } else {
        bubble.textContent = content;
    }
    messages.scrollTop = messages.scrollHeight;
}

async function streamResponse(userMessage) {
    const bubble = createMessageBubble("bot");
    bubble.classList.add("streaming");
    let fullText = "";

    try {
        const response = await fetch("/api/message/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            body: JSON.stringify({ message: userMessage }),
        });

        if (!response.ok) {
            bubble.textContent = "⚠️ Error generating recipe";
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // SSE messages are separated by double newlines
            const parts = buffer.split("\n\n");
            buffer = parts.pop(); // keep the incomplete chunk for next iteration

            for (const part of parts) {
                if (!part.startsWith("data: ")) continue;
                const jsonStr = part.slice(6);
                try {
                    const data = JSON.parse(jsonStr);
                    if (data.token) {
                        fullText += data.token;
                        bubble.innerHTML = marked.parse(fullText);
                        messages.scrollTop = messages.scrollHeight;
                    } else if (data.error) {
                        bubble.innerHTML = `⚠️ ${data.error}`;
                    } else if (data.done) {
                        bubble.classList.remove("streaming");
                    }
                } catch (e) {
                    console.error("Failed to parse SSE data:", jsonStr);
                }
            }
        }
    } catch (error) {
        bubble.textContent = `⚠️ Network error: ${error.message}`;
    } finally {
        bubble.classList.remove("streaming");
    }
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const userMessage = input.value.trim();
    if (!userMessage) return;

    addMessage(userMessage, "user");
    input.value = "";
    sendBtn.disabled = true;

    try {
        await streamResponse(userMessage);
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
});