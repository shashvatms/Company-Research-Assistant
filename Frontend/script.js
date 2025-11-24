// ========= SAFETY: Escape HTML to prevent broken template strings =========


function escapeHTML(str = "") {
    return str
        .replace(/&/g, "&amp;")
        .replace(/'/g, "&apos;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}


// ========= DOM Elements =========

// Safe element lookup (prevents null-crash)
const conflictBanner = document.getElementById("conflict-banner") || { style: {} };
const conflictText   = document.getElementById("conflict-text") || {};
const digBtn         = document.getElementById("dig-btn") || {};

const editorModal    = document.getElementById("editor-modal") || { style: {} };
const editorTitle    = document.getElementById("editor-title") || {};
const editorContent  = document.getElementById("editor-content") || {};
const editorCancel   = document.getElementById("editor-cancel") || {};
const editorSave     = document.getElementById("editor-save") || {};

editorContent.addEventListener("input", () => {
    editorContent.style.height = "auto";
    editorContent.style.height = editorContent.scrollHeight + "px";
});
function addTypingEffect(text, callback) {
    const chatBox = document.getElementById("chat-box");
    let div = document.createElement("div");
    div.className = "bot-msg";
    chatBox.appendChild(div);

    let i = 0;
    let speed = 10;

    function type() {
        if (i < text.length) {
            div.innerHTML = text.substring(0, i+1);
            i++;
            chatBox.scrollTop = chatBox.scrollHeight;
            setTimeout(type, speed);
        } else if (callback) callback();
    }
    type();
}
function handleConflicts(conflicts, session_id = "default-session") {
    const banner = document.getElementById("conflict-banner");
    const text = document.getElementById("conflict-text");
    const digBtn = document.getElementById("dig-btn");

    let summary = Object.keys(conflicts)
        .map(k => `${k}: ${conflicts[k].map(v => v.value).join(" / ")}`)
        .join(", ");

    text.textContent = "I'm finding conflicting data: " + summary;

    banner.classList.remove("hidden");

    digBtn.onclick = async () => {
        const topic = Object.keys(conflicts)[0];

        const res = await fetch("http://127.0.0.1:8000/dig-deeper", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id, topic })
        });

        const data = await res.json();
        addMessage("bot", data.reconciliation || data.reply);

        banner.classList.add("hidden");
    };
}
document.getElementById("reset-btn").onclick = async () => {
    await fetch("http://127.0.0.1:8000/reset-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: "default-session" })
    });

    addMessage("bot", "🔄 Session reset. You can start fresh!");
    document.getElementById("conflict-banner").classList.add("hidden");
};


// ========= Editor Modal =========
function openEditor(section, currentText = "", session_id = "default-session") {
    editorModal.style.display = "block";
    editorTitle.textContent = "Edit: " + section;
    editorContent.value = currentText;

    editorSave.onclick = async () => {
        const newContent = editorContent.value;

        const res = await fetch("http://localhost:8000/edit-section", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id,
                section,
                new_content: newContent
            })
        });

        const data = await res.json();
        editorModal.style.display = "none";

        if (data.conflicts) handleConflicts(data.conflicts);

        if (data.account_plan) {
            addMessage("bot", "🔄 Section updated.");
            addMessage("bot", formatBotMessage({ account_plan: data.account_plan }));
        } else {
            addMessage("bot", data.reply || JSON.stringify(data));
        }
    };

    editorCancel.onclick = () => {
        editorModal.style.display = "none";
    };
}


// ========= Add Messages =========
function addMessage(sender, text) {
    const chatBox = document.getElementById("chat-box");
    const div = document.createElement("div");

    div.className = sender === "user" ? "user-msg" : "bot-msg";
    div.innerHTML = text;

    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}


// ========= Send Message =========
// ===== SEND MESSAGE TO BACKEND =====
async function sendMessage() {
    const inputBox = document.getElementById("user-input");
    const loader = document.getElementById("loader");

    const message = inputBox.value.trim();
    if (!message) return;

    addMessage("user", message);
    inputBox.value = "";
    loader.classList.remove("hidden");

    try {
        const response = await fetch("http://127.0.0.1:8000/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                session_id: "default-session"
            })
        });

        const data = await response.json();
        loader.classList.add("hidden");

        const formatted = formatBotMessage(data);

        // 🔥 FIRST: Type the bot message
        addTypingEffect(formatted, () => {
            // 🔥 AFTER typing completes, show conflict banner
            if (data.conflicts) {
                handleConflicts(data.conflicts);
            }
        });

    } catch (error) {
        loader.classList.add("hidden");
        addMessage("bot", "❌ Error: Could not reach server.");
    }
}

async function resetSession() {
    await fetch("http://127.0.0.1:8000/reset", {
        method: "POST"
    });
    document.getElementById("chat-box").innerHTML = "";
    addMessage("bot", "🔄 Session reset. How can I help?");
}

// ========= Format Account Plan =========
// ========= SAFE FORMATTER =========
function formatBotMessage(data) {
    if (!data.account_plan) return data.reply;

    let raw = data.account_plan.raw_output;

    // If plan is already JSON object (not raw_output)
    if (!raw && typeof data.account_plan === "object") {
        raw = JSON.stringify(data.account_plan);
    }

    let clean = raw.replace(/```json/gi, "").replace(/```/g, "").trim();

    let plan;
    try {
        plan = JSON.parse(clean);
    } catch (e) {
        return "<b>Account Plan (raw):</b><pre>" + clean + "</pre>";
    }

    return `
        <h3>📌 Account Plan for ${plan.company_name}</h3>

        <!-- 1. Snapshot -->
        <div class="section-block">
            <div class="section-header">
                <b>1. Company Snapshot</b>
                <button class="edit-btn" onclick="openEditor('snapshot', '${plan.snapshot.description.replace(/'/g, "\\'")}')">Edit</button>
            </div>
            <p>${plan.snapshot.description}</p>
            <ul>
                <li><b>HQ:</b> ${plan.snapshot.headquarters}</li>
                <li><b>Founded:</b> ${plan.snapshot.founded}</li>
                <li><b>Revenue:</b> ${plan.snapshot.revenue_estimate}</li>
                <li><b>Employees:</b> ${plan.snapshot.employees_estimate}</li>
                <li><b>Products:</b> ${plan.snapshot.primary_products.join(", ")}</li>
            </ul>
        </div>
        <br>

        <!-- 2. Market Opportunity -->
        <div class="section-block">
            <div class="section-header">
                <b>2. Market Opportunity</b>
                <button class="edit-btn" onclick="openEditor('market_opportunity', '${plan.market_opportunity.segment.replace(/'/g, "\\'")}')">Edit</button>
            </div>
            <ul>
                <li><b>Segment:</b> ${plan.market_opportunity.segment}</li>
                <li><b>TAM/SAM/SOM:</b> ${plan.market_opportunity.tams_sams_soms}</li>
                <li><b>Growth Drivers:</b> ${plan.market_opportunity.growth_drivers.join(", ")}</li>
            </ul>
        </div>
        <br>

        <!-- 3. Ideal Customer Profile -->
        <div class="section-block">
            <div class="section-header">
                <b>3. Ideal Customer Profile</b>
                <button class="edit-btn" onclick="openEditor('ideal_customer_profile', '${plan.ideal_customer_profile.industry.replace(/'/g, "\\'")}')">Edit</button>
            </div>
            <ul>
                <li><b>Industry:</b> ${plan.ideal_customer_profile.industry}</li>
                <li><b>Company Size:</b> ${plan.ideal_customer_profile.company_size}</li>
                <li><b>Revenues:</b> ${plan.ideal_customer_profile.revenues}</li>
                <li><b>Geography:</b> ${plan.ideal_customer_profile.geography}</li>
            </ul>
        </div>
        <br>

        <!-- 4. Stakeholders -->
        <div class="section-block">
            <div class="section-header">
                <b>4. Key Stakeholders</b>
                <button class="edit-btn" onclick="openEditor('key_stakeholders', '')">Edit</button>
            </div>
            <ul>
                ${plan.key_stakeholders.map(p => `<li>${p.role}: ${p.name}</li>`).join("")}
            </ul>
        </div>
        <br>

        <!-- 5. Recommended Next Steps -->
        <div class="section-block">
            <div class="section-header">
                <b>5. Recommended Next Steps</b>
                <button class="edit-btn" onclick="openEditor('recommended_next_steps', '')">Edit</button>
            </div>
            <ul>
                ${plan.recommended_next_steps.map(s => `<li>${s}</li>`).join("")}
            </ul>
        </div>
        <br>

        <b>Confidence:</b> ${plan.confidence}
    `;
}

// ========= Voice Recognition =========
const voiceBtn = document.getElementById("voice-btn");

if (
    voiceBtn &&
    ("webkitSpeechRecognition" in window || "SpeechRecognition" in window)
) {
    const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";

    recognition.onresult = (e) => {
        const text = e.results[0][0].transcript;
        document.getElementById("user-input").value = text;
        sendMessage();
    };

    voiceBtn.onclick = () => recognition.start();
} else if (voiceBtn) {
    voiceBtn.disabled = true;
}
