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
function stopCamera() { if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null; } if ($("localVideo")) $("localVideo").srcObject = null; }
function setupRecognition() {
  if (recognition) return true;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { showToast("Live speech recognition is not supported. Try Chrome or Edge."); return false; }
  recognition = new SpeechRecognition(); recognition.continuous = true; recognition.interimResults = true; recognition.lang = "en-US";
  recognition.onresult = e => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const text = e.results[i][0].transcript.trim(); if (!text) continue;
      if (e.results[i].isFinal) committedTranscript = (committedTranscript + " " + text).replace(/\s+/g, " ").trim();
      else interim += (interim ? " " : "") + text;
    }
    $("transcript").value = (committedTranscript + (interim ? " " + interim : "")).trim();
  };
  recognition.onerror = e => { if (["aborted", "no-speech"].includes(e.error)) return; voiceListening = false; if ($("voiceButton")) $("voiceButton").textContent = "🎤 Start Listening"; if ($("voiceStatus")) $("voiceStatus").textContent = "Voice error: " + e.error + ". Check microphone permission."; };
  recognition.onend = () => { if (voiceListening) { try { recognition.start(); } catch {} } };
  return true;
}
function toggleVoiceRecognition() {
  if (voiceListening) return stopVoiceRecognition(); if (!setupRecognition()) return;
  committedTranscript = ($("transcript").value || "").trim(); voiceListening = true; $("voiceButton").textContent = "⏹ Stop Listening"; $("voiceStatus").textContent = "Listening… speak naturally.";
  try { recognition.start(); } catch { showToast("Voice recognition could not start. Please try again."); }
}
function stopVoiceRecognition() { voiceListening = false; if (recognition) try { recognition.stop(); } catch {} if ($("voiceButton")) $("voiceButton").textContent = "🎤 Start Listening"; if ($("voiceStatus")) $("voiceStatus").textContent = "Voice detection stopped."; if ($("transcript")) committedTranscript = $("transcript").value.trim(); }
async function saveTranscript() { if (!selectedMeeting) return; try { await api(`/api/meetings/${selectedMeeting.id}/transcript?` + query({ transcript: $("transcript").value }), { method: "PUT", headers: headers() }); selectedMeeting.notes = $("transcript").value; showToast("Transcript saved"); } catch (e) { showToast(e.message); } }
async function analyzeTranscript() { if (!selectedMeeting) return showToast("Open a meeting first"); if (!$("transcript").value.trim()) return showToast("Add some speech text first"); try { const d = await api(`/api/meetings/${selectedMeeting.id}/extract-tasks?` + query({ transcript: $("transcript").value }), { method: "POST", headers: headers() }); renderDetectedTasks(d.tasks); showToast(d.tasks.length ? "Task suggestions found. Review them before assigning." : "No clear assignments found. You can still assign manually."); } catch (e) { showToast(e.message); } }
function renderDetectedTasks(tasks) {
  const section = $("detectedTasks"), list = $("detectedTaskList"); section.classList.remove("hidden");
  if (!tasks.length) { list.innerHTML = "<p class='muted'>No clear task assignments detected.</p>"; return; }
  const options = selectedMeeting.participants.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
  list.innerHTML = tasks.map((t, i) => `<div class="task-card"><input id="ai-title-${i}" value="${escapeAttr(t.title)}"><select id="ai-user-${i}">${options}</select><input id="ai-deadline-${i}" value="${escapeAttr(t.deadline || "")}" placeholder="Due date"><p class="meta">Detected from: ${escapeHtml(t.source)}</p><button onclick="assignDetectedTask(${i})">Review & Assign</button></div>`).join("");
  tasks.forEach((t, i) => { const s = $("ai-user-" + i); if (s) s.value = String(t.assigned_to_id); });
}
async function assignDetectedTask(i) { $("taskTitle").value = $("ai-title-" + i).value; $("assignedUser").value = $("ai-user-" + i).value; $("taskDeadline").value = $("ai-deadline-" + i).value; await createTask(); }
async function createTask() { if (!selectedMeeting) return showToast("Open a meeting first"); try { await api("/api/tasks/?" + query({ title: $("taskTitle").value, assigned_to_id: $("assignedUser").value, deadline: $("taskDeadline").value, meeting_id: selectedMeeting.id }), { method: "POST", headers: headers() }); $("taskTitle").value = ""; $("taskDeadline").value = ""; showToast("Task assigned successfully"); } catch (e) { showToast(e.message); } }

function taskProgress(status) { return ({ Pending: 25, Submitted: 75, Completed: 100, Rejected: 25 }[status] ?? 25); }
function progressHtml(status) { const p = taskProgress(status); return `<div class="progress-wrap"><div class="progress-label"><span>Progress</span><strong>${p}%</strong></div><div class="progress-track"><div class="progress-fill" style="width:${p}%"></div></div></div>`; }
function taskHtml(t, mine) {
  const person = mine ? `Assigned by: <strong>${escapeHtml(t.assigned_by.name)}</strong>` : `Assigned to: <strong>${escapeHtml(t.assigned_to.name)}</strong>`;
  const submittedFile = t.has_file ? `<p class="meta"><button class="secondary small-button" onclick="downloadSubmission(${t.id}, '${escapeAttr(t.submission_filename || 'submission')}')">📎 Download: ${escapeHtml(t.submission_filename || 'submission')}</button></p>` : "";
  const submit = mine && t.status !== "Completed" && t.status !== "Submitted" ? `<textarea id="submission-${t.id}" placeholder="Add a note, link, explanation, or result (optional if you attach a file)"></textarea><input id="submission-file-${t.id}" type="file"><p class="meta">You can submit any file type up to 25 MB.</p><button onclick="submitTask(${t.id})">Submit Work</button>` : "";
  const review = !mine && t.status === "Submitted" ? `<textarea id="review-${t.id}" placeholder="Optional approval note or rejection reason"></textarea><button class="success" onclick="approveTask(${t.id})">Approve & Complete</button><button class="danger" onclick="rejectTask(${t.id})">Reject & Resubmit</button>` : "";
  const wait = mine && t.status === "Submitted" ? `<p class="meta"><strong>Waiting for approval from ${escapeHtml(t.assigned_by.name)}.</strong></p>` : "";
  return `<div class="task-card"><div class="task-top"><div><h3>${escapeHtml(t.title)}</h3><p class="meta">${person}</p><p class="meta">Meeting: ${escapeHtml(t.meeting_title)}</p><p class="meta">Due date: <strong>${escapeHtml(t.deadline || "No deadline")}</strong></p></div><span class="badge status-${t.status}">${escapeHtml(t.status)}</span></div>${t.submission ? `<div class="submission-box"><strong>${mine ? "Your submission" : "Submitted work"}:</strong><br>${escapeHtml(t.submission)}</div>` : ""}${submittedFile}${t.approval_note ? `<div class="submission-box"><strong>Reviewer note:</strong><br>${escapeHtml(t.approval_note)}</div>` : ""}${submit}${review}${wait}${progressHtml(t.status)}${t.status === "Completed" ? "<p><strong>Approved and completed ✓</strong></p>" : ""}</div>`;
}
async function loadMyTasks() { const box = $("myTasks"); if (!box) return; try { const tasks = await api("/api/tasks/mine", { headers: headers() }); box.innerHTML = !tasks.length ? "<p class='muted'>No tasks assigned to you.</p>" : tasks.map(t => taskHtml(t, true)).join(""); } catch (e) { showToast(e.message); } }
async function loadAssignedTasks() { const box = $("assignedTasks"); if (!box) return; try { const tasks = await api("/api/tasks/assigned", { headers: headers() }); box.innerHTML = !tasks.length ? "<p class='muted'>You have not assigned any tasks yet.</p>" : tasks.map(t => taskHtml(t, false)).join(""); } catch (e) { showToast(e.message); } }
async function submitTask(id) {
  try {
    const form = new FormData();
    const note = $("submission-" + id)?.value || "";
    const file = $("submission-file-" + id)?.files?.[0];
    form.append("submission", note);
    if (file) form.append("file", file);
    await api(`/api/tasks/${id}/submit`, { method: "POST", headers: headers(), body: form });
    showToast("Work submitted. Waiting for approval."); loadMyTasks();
  } catch (e) { showToast(e.message); }
}
async function downloadSubmission(id, name) {
  try {
    const response = await fetch(`/api/tasks/${id}/download`, { headers: headers() });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || "Download failed"); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
  } catch (e) { showToast(e.message); }
}
async function approveTask(id) { try { const note = $("review-" + id).value; await api(`/api/tasks/${id}/approve?` + query({ note }), { method: "POST", headers: headers() }); showToast("Task approved and marked Completed"); loadAssignedTasks(); } catch (e) { showToast(e.message); } }
async function rejectTask(id) { try { const reason = $("review-" + id).value || "Please improve and submit again."; await api(`/api/tasks/${id}/reject?` + query({ reason }), { method: "POST", headers: headers() }); showToast("Task returned for resubmission"); loadAssignedTasks(); } catch (e) { showToast(e.message); } }

async function boot() {
  const path = location.pathname;
  if (path === "/login") { if (currentUser) { location.href = "/dashboard"; return; } await setupGoogleLogin(); return; }
  if (!requireUser()) return;
  renderUserArea();
  document.querySelectorAll(".nav-links a").forEach(a => { if (a.getAttribute("href") === path) a.classList.add("active"); });
  if (path === "/dashboard") loadStats().catch(e => showToast(e.message));
  if (path === "/meetings") loadMeetings();
  if (path === "/meeting-room") openMeetingPage();
  if (path === "/my-tasks") loadMyTasks();
  if (path === "/assigned-tasks") loadAssignedTasks();
}
document.addEventListener("DOMContentLoaded", boot);

// ---------------------------------------------------------------------------
// Multi-participant WebRTC meeting (Zoom-style gallery for small/medium rooms)
// Uses deterministic negotiation to avoid offer collisions when cameras start.
// ---------------------------------------------------------------------------
let meetingSocket = null;
let meetingPeers = new Map();
let meetingClientId = null;
let localMediaStream = null;
let screenStream = null;
let screenSharing = false;
let meetingMicMuted = false;
const rtcConfig = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "stun:stun1.l.google.com:19302" },
    { urls: "stun:stun.cloudflare.com:3478" }
  ]
};

function getSenderForKind(pc, kind) {
  const transceiver = pc.getTransceivers().find(t => t.receiver?.track?.kind === kind || t.sender?.track?.kind === kind);
  return transceiver?.sender || pc.getSenders().find(sender => sender.track?.kind === kind) || null;
}

function makeMeetingClientId() { return window.crypto?.randomUUID ? crypto.randomUUID() : "client-" + Date.now() + "-" + Math.random().toString(16).slice(2); }
function socketUrl(path) { const scheme = location.protocol === "https:" ? "wss" : "ws"; return `${scheme}://${location.host}${path}`; }
function updateParticipantUi() {
  const peers = Array.from(meetingPeers.values()).map(p => p.name).filter(Boolean);
  const total = 1 + peers.length;
  if ($("participantCount")) $("participantCount").textContent = `${total} participant${total === 1 ? "" : "s"}`;
  if ($("participantNames")) $("participantNames").textContent = peers.length ? `Connected: ${peers.join(", ")}` : "Waiting for others to join";
  if ($("localName")) $("localName").textContent = currentUser?.name || "You";
}
function setMeetingConnectionStatus(text) { if ($("meetingConnectionStatus")) $("meetingConnectionStatus").textContent = text; }
function currentVideoTrack() { return screenSharing ? (screenStream?.getVideoTracks?.()[0] || null) : (localMediaStream?.getVideoTracks?.()[0] || null); }

function addLocalTracks(pc) {
  const videoTrack = currentVideoTrack();
  const audioTrack = localMediaStream?.getAudioTracks?.()[0] || null;
  const senders = pc.getSenders();
  const videoSender = senders.find(s => s.track?.kind === "video" || (!s.track && s.kind === "video"));
  const audioSender = senders.find(s => s.track?.kind === "audio" || (!s.track && s.kind === "audio"));
  if (videoTrack && !senders.some(s => s.track?.id === videoTrack.id)) {
    if (videoSender) videoSender.replaceTrack(videoTrack).catch(() => {});
    else pc.addTrack(videoTrack, screenSharing ? screenStream : localMediaStream);
  }
  if (audioTrack && !senders.some(s => s.track?.id === audioTrack.id)) {
    if (audioSender) audioSender.replaceTrack(audioTrack).catch(() => {});
    else pc.addTrack(audioTrack, localMediaStream);
  }
}

function ensureRemoteCard(peerId, name) {
  let card = $("remote-card-" + peerId);
  if (card) { const label = card.querySelector(".video-name"); if (label && name) label.textContent = name; return card; }
  const grid = $("videoGrid"); if (!grid) return null;
  card = document.createElement("div"); card.className = "video-card remote-card"; card.id = "remote-card-" + peerId;
  card.innerHTML = `<video id="remote-video-${peerId}" autoplay playsinline></video><div class="video-empty">Connecting video…</div><span class="video-name"></span>`;
  card.querySelector(".video-name").textContent = name || "Participant";
  grid.appendChild(card); return card;
}
function removeRemoteCard(peerId) { $("remote-card-" + peerId)?.remove(); }

// Perfect-negotiation WebRTC setup. This avoids offer collisions and, importantly,
// also renegotiates when the non-offerer turns their camera on or starts screen sharing.
function createPeer(peer) {
  if (!peer?.client_id || peer.client_id === meetingClientId) return null;
  const existing = meetingPeers.get(peer.client_id);
  if (existing) {
    if (peer.name) { existing.name = peer.name; ensureRemoteCard(peer.client_id, peer.name); }
    updateParticipantUi();
    return existing.pc;
  }

  const pc = new RTCPeerConnection(rtcConfig);
  try { pc.addTransceiver("audio", { direction: "sendrecv" }); } catch {}
  try { pc.addTransceiver("video", { direction: "sendrecv" }); } catch {}
  const state = {
    pc,
    name: peer.name || "Participant",
    pendingCandidates: [],
    makingOffer: false,
    ignoreOffer: false,
    isSettingRemoteAnswerPending: false,
    polite: String(meetingClientId) > String(peer.client_id),
    connectedAt: 0
  };
  meetingPeers.set(peer.client_id, state);
  ensureRemoteCard(peer.client_id, state.name);
  updateParticipantUi();
  addLocalTracks(pc);

  pc.onicecandidate = event => {
    if (event.candidate && meetingSocket?.readyState === WebSocket.OPEN) {
      meetingSocket.send(JSON.stringify({ type: "ice", to: peer.client_id, candidate: event.candidate }));
    }
  };
  pc.onicecandidateerror = event => {
    console.warn("ICE candidate error", event.errorCode, event.errorText || "");
  };
  pc.ontrack = event => {
    const video = $("remote-video-" + peer.client_id);
    const card = $("remote-card-" + peer.client_id);
    if (!video) return;
    if (event.streams?.[0]) video.srcObject = event.streams[0];
    else if (!video.srcObject) video.srcObject = new MediaStream([event.track]);
    video.autoplay = true;
    video.playsInline = true;
    video.muted = false;
    video.volume = 1;
    card?.classList.add("has-video");
    video.play().then(() => {
      $("enableAudioButton")?.classList.add("hidden");
    }).catch(() => {
      $("enableAudioButton")?.classList.remove("hidden");
    });
    setMeetingConnectionStatus(`${state.name} audio/video connected`);
  };
  pc.onconnectionstatechange = () => {
    const cs = pc.connectionState;
    if (cs === "connected") {
      state.connectedAt = Date.now();
      ensureRemoteCard(peer.client_id, state.name)?.classList.add("has-video");
      setMeetingConnectionStatus(`${state.name} connected`);
    } else if (cs === "connecting") {
      setMeetingConnectionStatus(`Connecting video to ${state.name}…`);
    } else if (["failed", "closed"].includes(cs)) {
      try { pc.close(); } catch {}
      meetingPeers.delete(peer.client_id);
      removeRemoteCard(peer.client_id);
      updateParticipantUi();
      setMeetingConnectionStatus(`${state.name} disconnected`);
    }
  };
  pc.oniceconnectionstatechange = () => {
    if (pc.iceConnectionState === "failed") {
      setMeetingConnectionStatus(`Video connection to ${state.name} failed. Check both browsers allow WebRTC.`);
      try { pc.restartIce(); } catch {}
    }
  };
  pc.onnegotiationneeded = async () => {
    try {
      state.makingOffer = true;
      await pc.setLocalDescription();
      if (meetingSocket?.readyState === WebSocket.OPEN && pc.localDescription) {
        meetingSocket.send(JSON.stringify({ type: "offer", to: peer.client_id, sdp: pc.localDescription }));
      }
    } catch (e) {
      console.warn("Negotiation failed", e);
    } finally {
      state.makingOffer = false;
    }
  };
  return pc;
}

async function handleMeetingSignal(message) {
  if (message.type === "peers") {
    for (const peer of message.peers || []) createPeer(peer);
    setMeetingConnectionStatus((message.peers || []).length ? "Negotiating participant video…" : "Connected. Waiting for participants…");
    return;
  }
  if (message.type === "peer-joined") {
    createPeer(message.peer);
    setMeetingConnectionStatus(`${message.peer?.name || "A participant"} joined. Connecting video…`);
    return;
  }
  if (message.type === "peer-left") {
    const state = meetingPeers.get(message.client_id);
    if (state) { try { state.pc.close(); } catch {} meetingPeers.delete(message.client_id); }
    removeRemoteCard(message.client_id);
    updateParticipantUi();
    return;
  }
  if (message.type === "offer") {
    const pc = createPeer({ client_id: message.from, name: meetingPeers.get(message.from)?.name || "Participant" });
    const state = meetingPeers.get(message.from);
    if (!pc || !state) return;
    try {
      const readyForOffer = !state.makingOffer && (pc.signalingState === "stable" || state.isSettingRemoteAnswerPending);
      const offerCollision = !readyForOffer;
      state.ignoreOffer = !state.polite && offerCollision;
      if (state.ignoreOffer) return;
      if (offerCollision && state.polite && pc.signalingState !== "stable") {
        await pc.setLocalDescription({ type: "rollback" });
      }
      await pc.setRemoteDescription(new RTCSessionDescription(message.sdp));
      for (const candidate of state.pendingCandidates.splice(0)) await pc.addIceCandidate(candidate);
      if (message.sdp.type === "offer") {
        await pc.setLocalDescription();
        if (meetingSocket?.readyState === WebSocket.OPEN) meetingSocket.send(JSON.stringify({ type: "answer", to: message.from, sdp: pc.localDescription }));
      }
    } catch (e) {
      console.warn("Offer handling failed", e);
    }
    return;
  }
  if (message.type === "answer") {
    const state = meetingPeers.get(message.from);
    if (!state) return;
    try {
      state.isSettingRemoteAnswerPending = true;
      await state.pc.setRemoteDescription(new RTCSessionDescription(message.sdp));
    } catch (e) {
      console.warn("Answer handling failed", e);
    } finally {
      state.isSettingRemoteAnswerPending = false;
    }
    return;
  }
  if (message.type === "ice") {
    const pc = createPeer({ client_id: message.from, name: meetingPeers.get(message.from)?.name || "Participant" });
    const state = meetingPeers.get(message.from);
    if (!pc || !state) return;
    try {
      const candidate = new RTCIceCandidate(message.candidate);
      if (pc.remoteDescription) await pc.addIceCandidate(candidate);
      else state.pendingCandidates.push(candidate);
    } catch (e) {
      if (!state.ignoreOffer) console.warn("ICE candidate failed", e);
    }
  }
}

function connectMeetingSocket() {
  if (!selectedMeeting || !currentUser || meetingSocket?.readyState === WebSocket.OPEN) return;
  meetingClientId = makeMeetingClientId();
  setMeetingConnectionStatus("Connecting participants…");
  meetingSocket = new WebSocket(socketUrl(`/ws/meeting/${selectedMeeting.id}`));
  meetingSocket.onopen = () => {
    meetingSocket.send(JSON.stringify({ type: "join", client_id: meetingClientId, name: currentUser.name || "Participant", user_id: currentUser.id }));
  };
  meetingSocket.onmessage = event => { try { handleMeetingSignal(JSON.parse(event.data)); } catch (e) { console.warn(e); } };
  meetingSocket.onerror = () => setMeetingConnectionStatus("Participant connection error. Check WebSocket support.");
  meetingSocket.onclose = () => { if ($("meetingRoomPage")) setMeetingConnectionStatus("Disconnected from participant room"); };
}
function disconnectMeetingSocket() {
  try { meetingSocket?.close(); } catch {}
  meetingSocket = null;
  meetingPeers.forEach(state => { try { state.pc.close(); } catch {} });
  meetingPeers.clear();
  updateParticipantUi();
}

async function renegotiateAllPeers() {
  // With perfect negotiation, adding/replacing tracks triggers negotiationneeded.
  // This helper only nudges peers whose browser did not emit it automatically.
  for (const [peerId, state] of meetingPeers) {
    try {
      if (state.pc.signalingState === "stable") {
        await state.pc.setLocalDescription();
        if (meetingSocket?.readyState === WebSocket.OPEN && state.pc.localDescription) {
          meetingSocket.send(JSON.stringify({ type: "offer", to: peerId, sdp: state.pc.localDescription }));
        }
      }
    } catch (e) { console.warn("Renegotiation failed", e); }
  }
}

async function startCamera() {
  try {
    if (localMediaStream) return showToast("Camera is already on.");
    localMediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    cameraStream = localMediaStream;
    if (!screenSharing) {
      const video = $("localVideo");
      if (video) { video.srcObject = localMediaStream; $("localVideoCard")?.classList.add("has-video"); await video.play().catch(() => {}); }
    }
    $("cameraButton") && ($("cameraButton").textContent = "📹 Camera On");
    $("localVideoEmpty") && ($("localVideoEmpty").textContent = "Camera is off");
    for (const state of meetingPeers.values()) addLocalTracks(state.pc);
    await renegotiateAllPeers();
    showToast("Camera and microphone are on");
  } catch (e) { console.warn(e); showToast("Camera/microphone permission was denied or unavailable. Please allow access and try again."); }
}
function stopCamera() {
  if (screenSharing) stopScreenShare();
  if (localMediaStream) localMediaStream.getTracks().forEach(track => track.stop());
  localMediaStream = null; cameraStream = null;
  if ($("localVideo")) $("localVideo").srcObject = null;
  $("localVideoCard")?.classList.remove("has-video");
  $("cameraButton") && ($("cameraButton").textContent = "📹 Start Camera");
  $("micButton") && ($("micButton").textContent = "🎙 Mute");
  meetingMicMuted = false;
}
function toggleMeetingMicrophone() {
  if (!localMediaStream) return showToast("Start the camera first to enable the microphone.");
  const tracks = localMediaStream.getAudioTracks(); if (!tracks.length) return;
  meetingMicMuted = !meetingMicMuted;
  tracks.forEach(track => track.enabled = !meetingMicMuted);
  if ($("micButton")) $("micButton").textContent = meetingMicMuted ? "🔇 Unmute" : "🎙 Mute";
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
async function enableRemoteAudio() {
  const videos = document.querySelectorAll("#videoGrid video:not(#localVideo)");
  let played = false;
  for (const video of videos) {
    try { video.muted = false; video.volume = 1; await video.play(); played = true; } catch {}
  }
  if (played) {
    $("enableAudioButton")?.classList.add("hidden");
    showToast("Remote audio enabled");
  } else {
    showToast("No remote audio is available yet. Ask the other participant to start their microphone.");
  }
}

async function toggleMeetingFullscreen() {
  const stage = $("meetingStage");
  if (!stage) return;
  try {
    if (!document.fullscreenElement) await stage.requestFullscreen();
    else await document.exitFullscreen();
  } catch { showToast("Full screen could not be enabled. Try the browser full-screen button."); }
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
