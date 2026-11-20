"""The web interface: search, look at results, play a shot, submit it."""
import io
import json
import os
import time
import zipfile
from dataclasses import asdict
from datetime import datetime
from functools import cache

import requests
from flask import Flask, abort, jsonify, render_template, request, send_file
from PIL import Image

from config import MAX_SHOTS_PER_VIDEO_FOR_AVS, METADATA_FILE, THUMBNAIL_FOLDER, VIDEO_FOLDER
from dres_client import DresClient
from search import ShotSearcher, limit_shots_per_video
from shots import Shot, load_all_shots

# Every submission and DRES's verdict, one JSON object per line. Useful to check
# what was already sent, and as practice-run evidence for the report.
SUBMISSION_LOG = "submissions.jsonl"
THUMBNAIL_CACHE_SECONDS = 24 * 60 * 60

app = Flask(__name__)
shots_by_id = load_all_shots()
searcher = ShotSearcher()
video_titles = {
    video["v3cId"]: video["title"]
    for video in json.loads(METADATA_FILE.read_text(encoding="utf-8"))
}

SEARCH_MODES = {
    "picture": searcher.by_description,
    "speech": searcher.by_spoken_words,
    "both": searcher.by_description_and_words,
}


DRES_SETTINGS = ("DRES_URL", "DRES_USER", "DRES_PASSWORD")


@cache
def dres_client() -> DresClient:
    # Logs in on first use, so the app runs before you have DRES details.
    missing = [name for name in DRES_SETTINGS if name not in os.environ]
    if missing:
        raise RuntimeError(f"Set {', '.join(missing)} in the terminal before starting the app.")
    return DresClient(*(os.environ[name] for name in DRES_SETTINGS))


@app.errorhandler(RuntimeError)
def explain_not_ready(error: RuntimeError):
    return jsonify({"error": str(error)}), 503


@app.errorhandler(requests.RequestException)
def explain_dres_unreachable(error: requests.RequestException):
    return jsonify({"error": f"DRES did not answer properly: {error}"}), 502


def find_shot(shot_id: str) -> Shot:
    if shot_id not in shots_by_id:
        abort(404)
    return shots_by_id[shot_id]


def describe_shots(shot_ids: list[str]) -> list[dict]:
    return [
        asdict(shot) | {"shot_id": shot_id, "title": video_titles.get(shot.video_id, "")}
        for shot_id in shot_ids
        for shot in [find_shot(shot_id)]
    ]


def timed_results(search, *arguments) -> tuple:
    start = time.perf_counter()
    shot_ids = search(*arguments)
    milliseconds = round((time.perf_counter() - start) * 1000)
    print(f"{search.__name__}: {len(shot_ids)} results in {milliseconds} ms")
    return shot_ids, milliseconds


def results_response(shot_ids: list[str], milliseconds: int):
    response = jsonify(describe_shots(shot_ids))
    response.headers["X-Search-Ms"] = str(milliseconds)
    return response


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/search")
def search_by_text():
    shot_ids, milliseconds = timed_results(SEARCH_MODES[request.args["mode"]], request.args["query"])
    if request.args.get("varied") == "yes":
        shot_ids = limit_shots_per_video(shot_ids, MAX_SHOTS_PER_VIDEO_FOR_AVS)
    return results_response(shot_ids, milliseconds)


@app.post("/search-by-image")
def search_by_image():
    image = Image.open(request.files["image"].stream).convert("RGB")
    return results_response(*timed_results(searcher.by_example_image, image))


@app.get("/similar/<shot_id>")
def search_by_similar_shot(shot_id: str):
    find_shot(shot_id)
    shot_ids, milliseconds = timed_results(searcher.by_similar_shot, shot_id)
    if request.args.get("varied") == "yes":
        shot_ids = limit_shots_per_video(shot_ids, MAX_SHOTS_PER_VIDEO_FOR_AVS)
    return results_response(shot_ids, milliseconds)


@cache
def thumbnail_archive(video_id: str) -> zipfile.ZipFile:
    # Kept open: reopening a zip for each of 200 thumbnails is slow.
    return zipfile.ZipFile(THUMBNAIL_FOLDER / f"{video_id}.zip")


@app.get("/thumbnail/<shot_id>")
def thumbnail(shot_id: str):
    shot = find_shot(shot_id)
    file_name = f"{shot_id}.png"  # name inside the zip, see videos_metadata.md
    try:
        image = thumbnail_archive(shot.video_id).read(file_name)
    except KeyError:
        abort(404)
    return send_file(io.BytesIO(image), download_name=file_name, max_age=THUMBNAIL_CACHE_SECONDS)


@app.get("/video/<video_id>")
def video(video_id: str):
    return send_file(VIDEO_FOLDER / f"{video_id}.mp4", conditional=True)


@app.get("/evaluations")
def evaluations():
    return jsonify(dres_client().active_evaluations())


@app.get("/current-task/<evaluation_id>")
def current_task(evaluation_id: str):
    return jsonify(asdict(dres_client().current_task(evaluation_id)))


@app.post("/submit")
def submit():
    shot = find_shot(request.json["shot_id"])
    evaluation_id = request.json.get("evaluation_id")
    if not evaluation_id:
        raise RuntimeError("Choose a DRES run in the task panel before submitting.")
    verdict = dres_client().submit_segment(evaluation_id, shot.video_id, shot.start_ms, shot.end_ms)
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "evaluation_id": evaluation_id,
        "evaluation_name": request.json.get("evaluation_name", ""),
        "shot_id": shot.shot_id,
        "video_id": shot.video_id,
        "start_ms": shot.start_ms,
        "end_ms": shot.end_ms,
        "verdict": verdict,
    }
    with open(SUBMISSION_LOG, "a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")
    return jsonify({"verdict": verdict})


if __name__ == "__main__":
    app.run(port=5000, threaded=True)
