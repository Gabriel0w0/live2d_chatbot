let model = null;
let isWaiting = false;
let lastAudioUrl = null;
let currentAudio = null;
let userHasInteracted = false;

// 親密度
let intimacyLevel = Number(localStorage.getItem("intimacyLevel")) || 50; // 優先讀取 localStorage，沒有則預設50

window.addEventListener("DOMContentLoaded", () => {
  updateIntimacyDisplay();
});

function updateIntimacyDisplay() {
  let levelName = "冷淡";
  if (intimacyLevel >= 90) levelName = "羈絆";
  else if (intimacyLevel >= 60) levelName = "親密";
  else if (intimacyLevel >= 30) levelName = "普通";

  document.getElementById("intimacy-text").textContent =
    `親密度：${intimacyLevel} (${levelName})`;

  const barFill = document.getElementById("intimacy-bar-fill");
  const percent = Math.min(100, Math.max(0, intimacyLevel));

  barFill.style.width = percent + "%";
}
updateIntimacyDisplay();

const app = new PIXI.Application({
  autoStart: true,
  resizeTo: window,
  backgroundAlpha: 0
});
document.body.appendChild(app.view);

// 載入 Live2D 模型
PIXI.live2d.Live2DModel.from("/static/model/hiyori/runtime/hiyori_pro_t11.model3.json")
  .then(m => {
    model = m;
    const scale = 0.17;
    model.scale.set(scale);
    model.anchor.set(0.5, 0.5);
    model.x = app.renderer.width / 2;
    model.y = app.renderer.height / 2;
    app.stage.addChild(model);
    app.renderer.render(app.stage);

    window.addEventListener("resize", () => {
      model.x = app.renderer.width / 2;
      model.y = app.renderer.height / 2;
      app.renderer.render(app.stage);
    });
  })
  .catch(err => console.error("載入模型失敗:", err));

function playMotion(groupName) {
  if (!model) return;
  const motions = model.internalModel.motionManager.definitions;
  if (!motions[groupName]) return;
  const index = Math.floor(Math.random() * motions[groupName].length);
  model.motion(groupName, index);
}

function getMotionByEmotionTag(text) {
  const emotionMatch = text.match(/\[emotion:(\w+)\]/i);
  if (!emotionMatch) return null;
  const emotion = emotionMatch[1].toLowerCase();
  switch (emotion) {
    case "joy":
    case "happy":
    case "excited":
      return "FlickUp";       // 開心

    case "sad":
    case "cry":
    case "lonely":
      return "Flick@Body";    // 悲傷

    case "angry":
    case "mad":
      return "Tap@Body";      // 生氣

    case "shy":
    case "embarrassed":
      return "FlickDown";     // 害羞

    case "cute":
    case "surprised":
    case "amazed":
      return "Tap";           // 驚訝

    case "neutral":
    case "idle":
    default:
      return "Idle";          // 待機
  }
}

function getMotionByText(text) {
  text = text.toLowerCase();
  if (text.includes("喜歡") || text.includes("開心") || text.includes("耶")) return "FlickUp";
  if (text.includes("嗚") || text.includes("哭") || text.includes("難過")) return "FlickDown";
  if (text.includes("氣氣") || text.includes("生氣")) return "Flick";
  if (text.includes("謝謝") || text.includes("感謝")) return "Idle";
  return "Tap";
}

function removeEmotionTag(text) {
  return text.replace(/\[emotion:\w+\]/gi, "").trim();
}

function disableInput() {
  const input = document.getElementById("chatInput");
  const button = input.nextElementSibling;
  input.disabled = true;
  button.disabled = true;
}

function enableInput() {
  const input = document.getElementById("chatInput");
  const button = input.nextElementSibling;
  input.disabled = false;
  button.disabled = false;
}

function showThinking() {
  document.getElementById("thinking-indicator").style.display = "block";
}
function hideThinking() {
  document.getElementById("thinking-indicator").style.display = "none";
}

function addMessage(text, sender = "bot") {
  const chatMessages = document.getElementById("chat-messages");
  const messageElem = document.createElement("div");
  messageElem.classList.add("chat-message", sender === "user" ? "user" : "bot");

  if (sender === "bot") {
    const fullText = document.createElement("div");
    fullText.className = "full-text";
    messageElem.appendChild(fullText);
    chatMessages.appendChild(messageElem);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    typeWriterEffect(fullText, text, 30, () => {
      enableInput();
    });

    messageElem.addEventListener("click", () => {
      messageElem.classList.toggle("collapsed");
    });
  } else {
    messageElem.textContent = text;
    chatMessages.appendChild(messageElem);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    enableInput();
  }
}

function typeWriterEffect(element, text, delay = 30, callback) {
  let i = 0;
  element.textContent = "";
  const chatMessages = document.getElementById("chat-messages");

  function type() {
    if (i < text.length) {
      element.textContent += text.charAt(i);
      chatMessages.scrollTop = chatMessages.scrollHeight; // 每輸出一個字就捲到底
      i++;
      setTimeout(type, delay);
    } else if (callback) {
      callback();
    }
  }
  type();
}

// 互動後才能播放音訊
function safePlayAudio(url) {
  if (!userHasInteracted) {
    console.warn("尚未有使用者互動，音訊播放被跳過");
    return;
  }

  currentAudio = new Audio(url);
  currentAudio.addEventListener("canplaythrough", () => {
    currentAudio.play().catch(err => {
      console.warn("播放語音失敗：", err);
    });
  });
}

function replayLastAudio() {
  if (!lastAudioUrl) {
    alert("還沒有語音可以重播喔～");
    return;
  }
  if (!userHasInteracted) {
    alert("請先點擊或輸入一次，才能播放語音喔！");
    return;
  }

  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
  }
  safePlayAudio(lastAudioUrl);
}

async function handleChat() {
  if (isWaiting) return;
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message) return;

  disableInput();
  addMessage(message, "user");
  input.value = "";
  input.focus();
  input.setSelectionRange(0, 0);
  input.scrollTop = 0;
  isWaiting = true;
  showThinking();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });
    const data = await res.json();

    if (data.reply) {
      const cleanReply = removeEmotionTag(data.reply);
      addMessage(cleanReply, "bot");
      const motion = getMotionByEmotionTag(data.reply) || getMotionByText(data.reply);
      playMotion(motion);

      if (data.audio_url) {
        lastAudioUrl = data.audio_url;
        safePlayAudio(lastAudioUrl);
      }

      // 回傳親密度更新前端，並存於 localStorage
      if (typeof data.intimacy === "number") {
        intimacyLevel = data.intimacy;
        updateIntimacyDisplay();
        localStorage.setItem("intimacyLevel", intimacyLevel);
      }

    } else {
      addMessage("嗯嗯？月讀醬想不到要說什麼了～", "bot");
      playMotion("Idle");
      enableInput();
    }
  } catch (err) {
    console.error("發生錯誤:", err);
    addMessage("出錯了喔嗚嗚～ (>﹏<)", "bot");
    enableInput();
  } finally {
    isWaiting = false;
    hideThinking();
  }
}

function clearSession() {
  if (!confirm("確定要清除短期記憶嗎？這會讓她忘記剛剛聊的內容喔！")) return;
  fetch("/clear_session", { method: "POST" })
    .then(res => res.json())
    .then(data => alert(data.message))
    .catch(err => alert("清除短期記憶時出錯了QQ"));
}

function clearAllMemory() {
  if (!confirm("確定要清除所有記憶嗎？她會忘記所有過去的事情喔！")) return;
  fetch("/clear_memory", { method: "POST" })
    .then(res => res.json())
    .then(data => alert(data.message))
    .catch(err => alert("清除全部記憶時出錯了QQ"));
}

// 鍵盤事件
document.getElementById("chatInput").addEventListener("keydown", function (event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    handleChat();
  }
});

// 搜尋過往訊息
document.getElementById("chat-search")?.addEventListener("input", function () {
  const keyword = this.value.trim().toLowerCase();
  const messages = document.querySelectorAll("#chat-messages .chat-message");
  messages.forEach(msg => {
    const text = msg.textContent.toLowerCase();
    msg.style.display = text.includes(keyword) ? "" : "none";
  });
});

// 第一次互動後才允許音訊播放
document.addEventListener("click", () => userHasInteracted = true, { once: true });
document.addEventListener("keydown", () => userHasInteracted = true, { once: true });

function initAudioPermission() {
  currentAudio = new Audio(); // 建立空 audio 解鎖播放
  currentAudio.play().catch(() => {}); 
  document.getElementById("audio-permission-overlay").style.display = "none";
}
function showTerms() {
  document.getElementById("termsModal").style.display = "block";
}
function closeTerms() {
  document.getElementById("termsModal").style.display = "none";
}

app.view.addEventListener("click", (e) => {
  if (!model) return;

  const hit = model.hitTest("Body", e.offsetX, e.offsetY);
  if (hit) {
    model.motion("Tap", 0);
  }
});
