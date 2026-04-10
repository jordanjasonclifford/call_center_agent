// SalesNest - AI Call Agent Frontend
// Handles persona selection, browser mic recording, audio playback, and live transcript

let selectedPersona = null;
let mediaRecorder   = null;
let audioChunks     = [];
let isRecording     = false;
let isProcessing    = false;

const setupScreen  = document.getElementById("setup-screen");
const callScreen   = document.getElementById("call-screen");
const resultScreen = document.getElementById("result-screen");
const startBtn     = document.getElementById("start-btn");
const talkBtn      = document.getElementById("talk-btn");
const talkLabel    = document.getElementById("talk-label");
const transcript   = document.getElementById("transcript");
const avaAudio     = document.getElementById("ava-audio");


// Persona selection
document.querySelectorAll(".persona-card").forEach(card => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".persona-card").forEach(c => c.classList.remove("selected"));
    card.classList.add("selected");
    selectedPersona = JSON.parse(card.dataset.persona);
    startBtn.disabled = false;
  });
});


// Start the call
startBtn.addEventListener("click", async () => {
  if (!selectedPersona) return;

  avaAudio.onended = null;  // clear any handler left over from a previous call

  showScreen(callScreen);
  document.getElementById("call-persona-name").textContent = selectedPersona.name;

  const res  = await fetch("/start", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ persona: selectedPersona })
  });
  const data = await res.json();

  addMessage("ava", data.text);
  playAudio(data.audio_url);

  if (data.version) {
    document.getElementById("version-badge").textContent = `Script v${data.version}`;
  }
});


// Hold to talk — mousedown/mouseup for desktop, touchstart/touchend for mobile
talkBtn.addEventListener("mousedown",  startRecording);
talkBtn.addEventListener("mouseup",    stopRecording);
talkBtn.addEventListener("touchstart", e => { e.preventDefault(); startRecording(); });
talkBtn.addEventListener("touchend",   e => { e.preventDefault(); stopRecording(); });


async function startRecording() {
  if (isProcessing) return;

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioChunks  = [];
  mediaRecorder = new MediaRecorder(stream);

  mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
  mediaRecorder.start();

  isRecording = true;
  talkBtn.classList.add("recording");
  talkLabel.textContent = "Recording...";
}


async function stopRecording() {
  if (!isRecording || !mediaRecorder) return;

  isRecording  = false;
  isProcessing = true;
  talkBtn.classList.remove("recording");
  talkBtn.classList.add("processing");
  talkLabel.textContent = "Processing...";

  mediaRecorder.stop();
  mediaRecorder.onstop = async () => {
    // Stop all mic tracks
    mediaRecorder.stream.getTracks().forEach(t => t.stop());

    const blob     = new Blob(audioChunks, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", blob, "lead_audio.webm");

    const res  = await fetch("/respond", { method: "POST", body: formData });
    const data = await res.json();

    if (data.error) {
      console.error(data.error);
      resetTalkBtn();
      return;
    }

    // Show lead transcript line
    addMessage("lead", data.lead_text);

    // Show Ava's response and play audio
    addMessage("ava", data.ava_text);
    playAudio(data.audio_url);

    // Wait for audio to finish before re-enabling the button
    avaAudio.onended = () => {
      if (data.outcome) {
        endCall(data.outcome);
      } else {
        resetTalkBtn();
      }
    };
  };
}


function playAudio(url) {
  // Add cache-busting param so browser doesn't play the previous cached response
  avaAudio.src = url + "?t=" + Date.now();
  avaAudio.play();
}


function addMessage(speaker, text) {
  const msg = document.createElement("div");
  msg.className = `message ${speaker}`;
  msg.innerHTML = `
    <div class="message-label">${speaker === "ava" ? "Ava" : selectedPersona?.name || "Lead"}</div>
    <div class="message-bubble">${text}</div>
  `;
  transcript.appendChild(msg);
  transcript.scrollTop = transcript.scrollHeight;
}


function resetTalkBtn() {
  isProcessing = false;
  talkBtn.classList.remove("processing");
  talkLabel.textContent = "Hold to Talk";
}


async function endCall(outcome) {
  showScreen(resultScreen);

  const header = document.getElementById("result-header");
  header.className = `result-header ${outcome}`;
  document.getElementById("result-text").textContent = outcome === "success"
    ? "Call successful — Demo booked"
    : outcome === "failed"
    ? "Call ended — Lead did not convert"
    : "Call ended — Neutral outcome";

  // Show full transcript in result screen
  const res  = await fetch("/transcript");
  const data = await res.json();
  const rt   = document.getElementById("result-transcript");
  rt.innerHTML = data.map(m =>
    `<div><strong>${m.speaker}:</strong> ${m.text}</div>`
  ).join("");
}


function resetCall() {
  selectedPersona = null;
  isRecording  = false;
  isProcessing = false;
  transcript.innerHTML = "";
  talkBtn.classList.remove("recording", "processing");
  talkLabel.textContent = "Hold to Talk";
  avaAudio.onended = null;
  document.querySelectorAll(".persona-card").forEach(c => c.classList.remove("selected"));
  startBtn.disabled = true;
  showScreen(setupScreen);
}


function showScreen(screen) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  screen.classList.add("active");
}
