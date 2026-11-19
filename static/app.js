const MS_PER_SECOND = 1000;
const results = document.getElementById("results");
const player = document.getElementById("player");
const video = document.getElementById("video");
let selectedShot = null;

function showResults(shots) {
  results.replaceChildren(...shots.map(createThumbnail));
}

function createThumbnail(shot) {
  const image = document.createElement("img");
  image.src = `/thumbnail/${shot.shot_id}`;
  image.title = shot.shot_id;
  image.loading = "lazy";
  image.addEventListener("click", () => playShot(shot));
  return image;
}

function playShot(shot) {
  selectedShot = shot;
  const startSeconds = shot.start_ms / MS_PER_SECOND;
  const endSeconds = shot.end_ms / MS_PER_SECOND;
  video.src = `/video/${shot.video_id}#t=${startSeconds},${endSeconds}`;
  document.getElementById("shot-label").textContent =
    `${shot.shot_id}: ${shot.start_ms} to ${shot.end_ms} ms`;
  document.getElementById("verdict").textContent = "";
  player.hidden = false;
  video.play();
}

async function searchByText(event) {
  event.preventDefault();
  const params = new URLSearchParams({
    query: document.getElementById("query").value,
    mode: document.getElementById("mode").value,
    varied: document.getElementById("varied").checked ? "yes" : "no",
  });
  const response = await fetch(`/search?${params}`);
  showResults(await response.json());
}

async function searchByImage(event) {
  event.preventDefault();
  await sendImageSearch(document.getElementById("image").files[0]);
}

async function sendImageSearch(image) {
  const upload = new FormData();
  upload.append("image", image);
  const response = await fetch("/search-by-image", { method: "POST", body: upload });
  showResults(await response.json());
}

function searchWithVideoFrame(videoElement) {
  const canvas = document.createElement("canvas");
  canvas.width = videoElement.videoWidth;
  canvas.height = videoElement.videoHeight;
  canvas.getContext("2d").drawImage(videoElement, 0, 0);
  canvas.toBlob(sendImageSearch, "image/png");
}

async function showCurrentTask() {
  const summary = document.getElementById("task-summary");
  summary.textContent = "Asking DRES…";
  const response = await fetch("/current-task");
  const task = await response.json();
  if (!response.ok) {
    summary.textContent = task.error;
    return;
  }
  summary.textContent = task.status === "RUNNING"
    ? `${task.name} (${task.task_type}), ${task.seconds_left ?? "?"} s left`
    : `No task running right now (${task.status})`;
  document.getElementById("task-clues").replaceChildren(...task.clues.map(createClue));
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

async function submitSelectedShot() {
  const response = await fetch("/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shot_id: selectedShot.shot_id }),
  });
  const answer = await response.json();
  document.getElementById("verdict").textContent = response.ok
    ? `DRES says: ${answer.verdict}`
    : answer.error;
}

document.getElementById("text-search").addEventListener("submit", searchByText);
document.getElementById("image-search").addEventListener("submit", searchByImage);
document.getElementById("submit").addEventListener("click", submitSelectedShot);
document.getElementById("show-task").addEventListener("click", showCurrentTask);
