// script.js
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const letterEl = document.getElementById("letter");
const wordEl = document.getElementById("word");
const clearBtn = document.getElementById("clearBtn");
const autoSpeakCheckbox = document.getElementById("autoSpeak");

let sending = false;

// Start webcam
navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => { video.srcObject = stream; })
  .catch(err => console.error("Camera error:", err));

// Helper to POST frame
async function sendFrame() {
  if (sending) return;
  if (video.videoWidth === 0) return;
  sending = true;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  const dataURL = canvas.toDataURL("image/jpeg", 0.7);
  try {
    const res = await fetch("/predict", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ image: dataURL })
    });
    const json = await res.json();

    letterEl.textContent = "Current letter: " + (json.letter || "");
    wordEl.textContent = "Word: " + (json.word || "");

    // Server returns speak text when a word completes
    if (json.speak && json.speak.length > 0 && autoSpeakCheckbox.checked) {
      speakText(json.speak);
    }
  } catch (err) {
    console.error("Error sending frame:", err);
  } finally {
    sending = false;
  }
}

// Browser speech
function speakText(text) {
  if (!('speechSynthesis' in window)) {
    alert("Speech Synthesis not supported in this browser.");
    return;
  }
  const ut = new SpeechSynthesisUtterance(text);
  // optionally set voice/rate/pitch: ut.rate = 1.0;
  window.speechSynthesis.cancel();  // cancel any current speech
  window.speechSynthesis.speak(ut);
}

// Clear server buffer
clearBtn.addEventListener("click", async () => {
  await fetch("/clear", { method: "POST" });
  letterEl.textContent = "Current letter: ";
  wordEl.textContent = "Word: ";
});

// Send frames every 300 ms (~3 FPS)
setInterval(sendFrame, 300);
