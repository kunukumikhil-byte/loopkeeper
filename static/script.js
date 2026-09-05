let currentUser = JSON.parse(localStorage.getItem("loopkeeper_user") || "null");
let selectedMeeting = null;
let cameraStream = null;
let recognition = null;
let voiceListening = false;
let committedTranscript = "";

const $ = (id) => document.getElementById(id);
function headers() { return { "x-user-id": currentUser?.id || "" }; }
function query(data) { return new URLSearchParams(data).toString(); }

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}
function showToast(message) {
  const t = $("toast"); if (!t) return alert(message);
  t.textContent = message; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3500);
}
function escapeHtml(v) { return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
function escapeAttr(v) { return escapeHtml(v).replaceAll("`", "&#096;"); }
function requireUser() { if (!currentUser) { location.href = "/login"; return false; } return true; }

function renderUserArea() {
  const area = $("userArea"); if (!area) return;
  if (!currentUser) { area.innerHTML = `<a class="login-link" href="/login">Login</a>`; return; }
  area.innerHTML = `<span class="user-name">${escapeHtml(currentUser.name)}</span><button class="logout-btn secondary" onclick="logout()">Logout</button>`;
}
function logout() {
  stopCamera(); stopVoiceRecognition(); localStorage.removeItem("loopkeeper_user"); currentUser = null; selectedMeeting = null; location.href = "/login";
}

function showAuth(which) {
  const login = $("loginForm"), register = $("registerForm");
  if (!login || !register) return;
  login.classList.toggle("hidden", which !== "login");
  register.classList.toggle("hidden", which !== "register");
  $("loginTab")?.classList.toggle("active", which === "login");
  $("registerTab")?.classList.toggle("active", which === "register");
}
async function setupGoogleLogin() {
  const box = $("googleLogin"); if (!box) return;
  try {
    const config = await api("/api/auth/google/config");
    if (!config.enabled) {
      box.innerHTML = `<p class="muted">${escapeHtml(config.message || "Google Sign-In is not configured.")}</p>`;
      return;
    }
    const wait = () => {
      if (!window.google?.accounts?.id) return setTimeout(wait, 150);
      try {
        google.accounts.id.initialize({ client_id: config.client_id, callback: handleGoogleCredential });
        google.accounts.id.renderButton(box, { theme: "outline", size: "large", width: 320 });
      } catch (e) {
        box.innerHTML = "<p class='muted'>Google Sign-In could not start. Check the Client ID and authorized JavaScript origins.</p>";
      }
    };
    wait();
  } catch {
    box.innerHTML = "<p class='muted'>Google Login unavailable.</p>";
  }
}
async function handleGoogleCredential(response) {
  try {
    if (!response?.credential) throw new Error("Google did not return a credential. Please try again.");
    const d = await api("/api/auth/google", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ credential: response.credential })
    });
    finishLogin(d.user);
  } catch (e) {
    showToast(e.message || "Google Sign-In failed");
  }
}
function finishLogin(user) { currentUser = user; localStorage.setItem("loopkeeper_user", JSON.stringify(user)); location.href = "/dashboard"; }
async function register() {
  try { const d = await api("/api/auth/register?" + query({ name: $("registerName").value, email: $("registerEmail").value, password: $("registerPassword").value }), { method: "POST" }); finishLogin(d.user); }
  catch (e) { showToast(e.message); }
}
async function login() {
  try { const d = await api("/api/auth/login?" + query({ email: $("loginEmail").value, password: $("loginPassword").value }), { method: "POST" }); finishLogin(d.user); }
  catch (e) { showToast(e.message); }
}

async function loadStats() {
  const s = await api("/api/tasks/stats", { headers: headers() });
  if ($("totalStat")) $("totalStat").textContent = s.total;
  if ($("completedStat")) $("completedStat").textContent = s.completed;
  if ($("pendingStat")) $("pendingStat").textContent = s.pending;
  if ($("submittedStat")) $("submittedStat").textContent = s.submitted;
}

async function createMeeting() {
  try {
    const d = await api("/api/meetings/?" + query({ title: $("meetingTitle").value, notes: $("meetingNotes").value }), { method: "POST", headers: headers() });
    showToast("Meeting created. Code: " + d.meeting.code);
    location.href = "/meeting-room?meeting_id=" + d.meeting.id;
  } catch (e) { showToast(e.message); }
}
async function joinMeeting() {
  try {
    const d = await api("/api/meetings/join?" + query({ code: $("joinCode").value }), { method: "POST", headers: headers() });
    showToast("Joined meeting"); location.href = "/meeting-room?meeting_id=" + d.meeting.id;
  } catch (e) { showToast(e.message); }
}
async function loadMeetings() {
  const list = $("meetingList"); if (!list) return;
  try {
    const meetings = await api("/api/meetings/", { headers: headers() });
    list.innerHTML = !meetings.length ? "<p class='muted'>No meetings yet.</p>" : meetings.map(m => `<div class="meeting-card"><div class="task-top"><div><h3>${escapeHtml(m.title)}</h3><p class="meta">Code: <strong>${escapeHtml(m.code)}</strong></p><p class="meta">Creator: ${escapeHtml(m.creator)}</p><p class="meta">Participants: ${m.participants.map(p => escapeHtml(p.name)).join(", ")}</p></div><a class="button-link" href="/meeting-room?meeting_id=${m.id}">Open Meeting</a></div></div>`).join("");
  } catch (e) { showToast(e.message); }
}
async function openMeetingPage() {
  const root = $("meetingRoomPage"); if (!root) return;
  const id = Number(root.dataset.meetingId || new URLSearchParams(location.search).get("meeting_id"));
  if (!id) { showToast("No meeting selected"); location.href = "/meetings"; return; }
  try {
    selectedMeeting = await api("/api/meetings/" + id, { headers: headers() });
    $("roomTitle").textContent = selectedMeeting.title;
    $("roomCode").textContent = "Share this meeting code: " + selectedMeeting.code;
    $("transcript").value = selectedMeeting.notes || "";
    $("assignedUser").innerHTML = selectedMeeting.participants.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
  } catch (e) { showToast(e.message); setTimeout(() => location.href = "/meetings", 900); }
}

async function startCamera() { try { stopCamera(); cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true }); $("localVideo").srcObject = cameraStream; } catch { showToast("Camera/microphone permission was denied or unavailable."); } }
function stopCamera() {
  if (screenSharing) stopScreenShare();
  if (localMediaStream) localMediaStream.getTracks().forEach(track => track.stop());
  localMediaStream = null; cameraStream = null;
  if ($("localVideo")) $("localVideo").srcObject = null;
  $("localVideoCard")?.classList.remove("has-video");
  $("cameraButton") && ($("cameraButton").textContent = "📹 Start Camera");
  $("micButton") && ($("micButton").textContent = "🎙 Start Mic");
  meetingMicMuted = false;
  for (const state of meetingPeers.values()) {
    getSenderForKind(state.pc, "audio")?.replaceTrack(null).catch(() => {});
    getSenderForKind(state.pc, "video")?.replaceTrack(null).catch(() => {});
  }
  renegotiateAllPeers();
}
function toggleMeetingMicrophone() {
  if (!localMediaStream) return showToast("Start the camera first to enable the microphone.");
  const tracks = localMediaStream.getAudioTracks();
  if (!tracks.length) return showToast("No microphone track is available.");
  meetingMicMuted = !meetingMicMuted;
  tracks.forEach(track => track.enabled = !meetingMicMuted);
  $("micButton") && ($("micButton").textContent = meetingMicMuted ? "🔇 Unmute" : "🎙 Mute");
}
async function toggleScreenShare() {
  if (screenSharing) return stopScreenShare();
  if (!navigator.mediaDevices?.getDisplayMedia) return showToast("Screen sharing is not supported by this browser.");
  try {
    screenStream = await navigator.mediaDevices.getDisplayMedia({ video: { cursor: "always" }, audio: false });
    const screenTrack = screenStream.getVideoTracks()[0];
    if (!screenTrack) throw new Error("No screen track was created.");
    screenSharing = true;
    screenTrack.onended = () => stopScreenShare();
    const localVideo = $("localVideo");
    if (localVideo) { localVideo.srcObject = new MediaStream([screenTrack, ...(localMediaStream?.getAudioTracks?.() || [])]); $("localVideoCard")?.classList.add("has-video"); await localVideo.play().catch(() => {}); }
    for (const state of meetingPeers.values()) {
      const sender = getSenderForKind(state.pc, "video");
      if (sender) await sender.replaceTrack(screenTrack);
      else state.pc.addTrack(screenTrack, screenStream);
    }
    await renegotiateAllPeers();
    $("screenShareButton") && ($("screenShareButton").textContent = "⏹ Stop Sharing");
    showToast("You are sharing your screen");
  } catch (e) {
    screenStream?.getTracks().forEach(t => t.stop()); screenStream = null; screenSharing = false;
    if (e?.name !== "NotAllowedError") showToast("Screen sharing could not start.");
  }
}
function stopScreenShare() {
  if (!screenSharing && !screenStream) return;
  const cameraTrack = localMediaStream?.getVideoTracks?.()[0] || null;
  screenStream?.getTracks().forEach(track => track.stop()); screenStream = null; screenSharing = false;
  const localVideo = $("localVideo");
  if (localVideo) { localVideo.srcObject = localMediaStream || null; if (localMediaStream) $("localVideoCard")?.classList.add("has-video"); else $("localVideoCard")?.classList.remove("has-video"); localVideo.play().catch(() => {}); }
  for (const state of meetingPeers.values()) {
    const sender = getSenderForKind(state.pc, "video");
    if (sender) sender.replaceTrack(cameraTrack).catch(() => {});
    else if (cameraTrack) state.pc.addTrack(cameraTrack, localMediaStream);
  }
  renegotiateAllPeers();
  $("screenShareButton") && ($("screenShareButton").textContent = "🖥️ Share Screen");
  showToast(cameraTrack ? "Screen sharing stopped. Camera restored." : "Screen sharing stopped.");
}
function leaveMeeting() {
  if (!confirm("Leave this meeting?")) return;
  try { if (meetingSocket?.readyState === WebSocket.OPEN) meetingSocket.send(JSON.stringify({ type: "leave" })); } catch {}
  stopVoiceRecognition(); stopCamera(); disconnectMeetingSocket();
  selectedMeeting = null;
  location.href = "/meetings";
}

async function openMeetingPage() {
  const root = $("meetingRoomPage"); if (!root) return;
  const id = Number(root.dataset.meetingId || new URLSearchParams(location.search).get("meeting_id"));
  if (!id) { showToast("No meeting selected"); location.href = "/meetings"; return; }
  try {
    selectedMeeting = await api("/api/meetings/" + id, { headers: headers() });
    $("roomTitle").textContent = selectedMeeting.title;
    $("roomCode").textContent = "Share this meeting code: " + selectedMeeting.code;
    $("transcript").value = selectedMeeting.notes || "";
    $("assignedUser").innerHTML = selectedMeeting.participants.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
    updateParticipantUi();
    connectMeetingSocket();
  } catch (e) { showToast(e.message); setTimeout(() => location.href = "/meetings", 900); }
}
window.addEventListener("beforeunload", () => { disconnectMeetingSocket(); stopCamera(); });
