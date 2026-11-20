const MS_PER_SECOND = 1000;
const TASK_REFRESH_MS = 5000;
const results = document.getElementById("results");
const player = document.getElementById("player");
const video = document.getElementById("video");
let playingShot = null;
const selectedShots = new Map(); // shot_id -> shot, for submitting many at once (AVS)
const submittedShotIds = new Set();

// ---------- results grid ----------

function showResults(shots) {
  results.replaceChildren(...shots.map(createTile));
}

async function showSearchResponse(response) {
  const answer = await response.json();
  const message = document.getElementById("search-message");
  if (!response.ok) {
    message.textContent = answer.error;
    results.replaceChildren();
    return;
  }
  message.textContent = `${answer.length} shots in ${response.headers.get("X-Search-Ms")} ms`;
  showResults(answer);
}

function createTile(shot) {
  const tile = document.createElement("div");
  tile.className = "tile";
  tile.dataset.shotId = shot.shot_id;
  tile.classList.toggle("selected", selectedShots.has(shot.shot_id));
  tile.classList.toggle("submitted", submittedShotIds.has(shot.shot_id));

  const image = document.createElement("img");
  image.src = `/thumbnail/${shot.shot_id}`;
  image.title = `${shot.title}\n${shot.shot_id}`;
  image.loading = "lazy";
  image.addEventListener("click", () => playShot(shot));

  const label = document.createElement("span");
  label.className = "label";
  label.textContent = shot.video_id;

  const similar = tileButton("≈", "More like this", () => searchSimilarTo(shot));
  const select = tileButton("✓", "Select for submitting (AVS)", () => toggleSelected(shot));
  tile.append(image, label, similar, select);
  return tile;
}

function tileButton(text, title, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = text;
  button.title = title;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick();
  });
  return button;
}

function markTiles(shotId, className, on) {
  for (const tile of results.querySelectorAll(`[data-shot-id="${shotId}"]`)) {
    tile.classList.toggle(className, on);
  }
}

// ---------- searching ----------

async function searchByText(event) {
  event.preventDefault();
  const params = new URLSearchParams({
    query: document.getElementById("query").value,
    mode: document.getElementById("mode").value,
    varied: variedWanted(),
  });
  await showSearchResponse(await fetch(`/search?${params}`));
}

function variedWanted() {
  return document.getElementById("varied").checked ? "yes" : "no";
}

async function searchByImage(event) {
  event.preventDefault();
  await sendImageSearch(document.getElementById("image").files[0]);
}

async function sendImageSearch(image) {
  document.getElementById("search-message").textContent = "Searching with the image…";
  const upload = new FormData();
  upload.append("image", image);
  await showSearchResponse(await fetch("/search-by-image", { method: "POST", body: upload }));
}

async function searchSimilarTo(shot) {
  document.getElementById("search-message").textContent = `Shots like ${shot.shot_id}…`;
  await showSearchResponse(await fetch(`/similar/${shot.shot_id}?varied=${variedWanted()}`));
}

function searchWithPastedImage(event) {
  const imageItem = [...event.clipboardData.items].find((item) => item.type.startsWith("image/"));
  if (imageItem) {
    event.preventDefault();
    sendImageSearch(imageItem.getAsFile());
  }
}

function searchWithVideoFrame(videoElement) {
  const canvas = document.createElement("canvas");
  canvas.width = videoElement.videoWidth;
  canvas.height = videoElement.videoHeight;
  canvas.getContext("2d").drawImage(videoElement, 0, 0);
  canvas.toBlob(sendImageSearch, "image/png");
}

// ---------- playing (temporal verification) ----------

function playShot(shot) {
  playingShot = shot;
  video.src = `/video/${shot.video_id}#t=${shot.start_ms / MS_PER_SECOND},${shot.end_ms / MS_PER_SECOND}`;
  document.getElementById("shot-label").textContent =
    `${shot.title} | ${shot.shot_id} | ${formatTime(shot.start_ms)} to ${formatTime(shot.end_ms)}`;
  document.getElementById("verdict").textContent = "";
  player.hidden = false;
  video.play();
}

function replayShot() {
  video.currentTime = playingShot.start_ms / MS_PER_SECOND;
  video.play();
}

function formatTime(ms) {
  const totalSeconds = ms / MS_PER_SECOND;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = (totalSeconds % 60).toFixed(1).padStart(4, "0");
  return `${minutes}:${seconds}`;
}

// ---------- submitting ----------

function describeForConfirm(shot) {
  const warning = submittedShotIds.has(shot.shot_id) ? "  (ALREADY SUBMITTED)" : "";
  return `${shot.shot_id}  ${formatTime(shot.start_ms)}-${formatTime(shot.end_ms)}${warning}`;
}

function runChosen() {
  if (chosenRun) return true;
  alert("Connect to DRES and choose a run in the task panel first.");
  return false;
}

async function submitShot(shot) {
  const response = await fetch("/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      shot_id: shot.shot_id,
      evaluation_id: chosenRun.id,
      evaluation_name: chosenRun.name,
    }),
  });
  const answer = await response.json();
  const verdict = response.ok ? answer.verdict : `Not sent: ${answer.error}`;
  if (response.ok) {
    submittedShotIds.add(shot.shot_id);
    markTiles(shot.shot_id, "submitted", true);
  }
  addToHistory(shot, verdict);
  return verdict;
}

async function submitPlayingShot() {
  if (!runChosen()) return;
  const question = `Submit this shot to DRES run "${chosenRun.name}"?`;
  if (!confirm(`${question}\n\n${describeForConfirm(playingShot)}`)) return;
  document.getElementById("verdict").textContent = "Sending…";
  document.getElementById("verdict").textContent = `DRES says: ${await submitShot(playingShot)}`;
}

async function submitSelectedShots() {
  if (!runChosen()) return;
  const shots = [...selectedShots.values()];
  const list = shots.map(describeForConfirm).join("\n");
  const question = `Submit these ${shots.length} shots to DRES run "${chosenRun.name}"?`;
  if (!confirm(`${question}\n\n${list}`)) return;
  for (const shot of shots) {
    await submitShot(shot);
    toggleSelected(shot);
  }
}

function addToHistory(shot, verdict) {
  const item = document.createElement("li");
  item.textContent = `${new Date().toLocaleTimeString()}  ${shot.shot_id}  ${verdict}`;
  item.addEventListener("click", () => playShot(shot));
  document.getElementById("history-list").prepend(item);
}

function toggleSelected(shot) {
  if (selectedShots.has(shot.shot_id)) selectedShots.delete(shot.shot_id);
  else selectedShots.set(shot.shot_id, shot);
  markTiles(shot.shot_id, "selected", selectedShots.has(shot.shot_id));
  document.getElementById("selection-bar").hidden = selectedShots.size === 0;
  document.getElementById("selection-count").textContent = `${selectedShots.size} selected`;
}

function clearSelection() {
  for (const shot of [...selectedShots.values()]) toggleSelected(shot);
}

// ---------- current DRES task ----------

let chosenRun = null; // {id, name}: the DRES run (evaluation) we follow and submit to
let taskTimer = null;
let secondsLeft = null;
let shownCluesKey = "";

async function loadRuns() {
  // Logs in and lists the active runs. Reading only; nothing is submitted.
  const summary = document.getElementById("task-summary");
  summary.textContent = "Asking DRES for active runs…";
  const response = await fetch("/evaluations");
  const runs = await response.json();
  if (!response.ok) {
    summary.textContent = runs.error;
    return;
  }
  const choice = document.getElementById("run-choice");
  choice.replaceChildren(choice.options[0]);
  for (const run of runs) choice.add(new Option(run.name, run.id));
  choice.hidden = false;
  summary.textContent = runs.length ? `${runs.length} active run(s). Choose one.` : "No active runs.";
}

function chooseRun(event) {
  const option = event.target.selectedOptions[0];
  chosenRun = option.value ? { id: option.value, name: option.text } : null;
  shownCluesKey = "";
  secondsLeft = null;
  document.getElementById("task-clues").replaceChildren();
  document.getElementById("task-summary").textContent = chosenRun ? "Loading task…" : "";
  if (!chosenRun) return;
  refreshCurrentTask();
  if (!taskTimer) {
    taskTimer = setInterval(refreshCurrentTask, TASK_REFRESH_MS);
    setInterval(tickCountdown, MS_PER_SECOND);
  }
}

async function refreshCurrentTask() {
  if (!chosenRun) return;
  const run = chosenRun;
  const summary = document.getElementById("task-summary");
  const response = await fetch(`/current-task/${run.id}`);
  if (run !== chosenRun) return; // the operator switched runs while this was loading
  const task = await response.json();
  if (!response.ok) {
    summary.textContent = task.error;
    return;
  }
  if (task.status !== "RUNNING") {
    secondsLeft = null;
    summary.textContent = `No task running right now (${task.status})`;
    return;
  }
  secondsLeft = task.seconds_left;
  summary.dataset.name = `${task.name} (${task.task_type})`;
  tickCountdown(0);
  // Only rebuild clues when they change, so a playing clip is not restarted.
  const cluesKey = `${task.name}:${task.clues.length}`;
  if (cluesKey !== shownCluesKey) {
    shownCluesKey = cluesKey;
    document.getElementById("task-clues").replaceChildren(...task.clues.map(createClue));
  }
}

function tickCountdown(step = 1) {
  if (secondsLeft === null) return;
  secondsLeft = Math.max(0, secondsLeft - step);
  const summary = document.getElementById("task-summary");
  summary.textContent = `${summary.dataset.name}: ${secondsLeft ?? "?"} s left`;
}

function createClue(clue) {
  if (clue.kind === "TEXT") {
    const text = document.createElement("p");
    text.textContent = clue.content;
    return text;
  }
  if (clue.kind === "IMAGE") {
    const image = document.createElement("img");
    image.src = `data:image/jpeg;base64,${clue.content}`;
    return image;
  }
  return createVideoClue(clue.content);
}

function createVideoClue(base64Video) {
  const wrapper = document.createElement("div");
  const clip = document.createElement("video");
  clip.src = `data:video/mp4;base64,${base64Video}`;
  clip.controls = true;
  clip.loop = true;
  clip.muted = true;
  clip.autoplay = true;
  const searchButton = document.createElement("button");
  searchButton.type = "button";
  searchButton.textContent = "Search with this frame";
  searchButton.addEventListener("click", () => searchWithVideoFrame(clip));
  wrapper.append(clip, searchButton);
  return wrapper;
}

// ---------- wiring ----------

document.getElementById("text-search").addEventListener("submit", searchByText);
document.getElementById("image-search").addEventListener("submit", searchByImage);
document.getElementById("submit").addEventListener("click", submitPlayingShot);
document.getElementById("similar-to-playing").addEventListener("click", () => searchSimilarTo(playingShot));
document.getElementById("play-from-start").addEventListener("click", replayShot);
document.getElementById("submit-selected").addEventListener("click", submitSelectedShots);
document.getElementById("clear-selection").addEventListener("click", clearSelection);
document.getElementById("load-runs").addEventListener("click", loadRuns);
document.getElementById("run-choice").addEventListener("change", chooseRun);
document.addEventListener("paste", searchWithPastedImage);
