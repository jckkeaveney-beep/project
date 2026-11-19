"""The web interface: search, look at results, play a shot, submit it."""
import io
import os
import zipfile
from dataclasses import asdict
from functools import cache

import requests
from flask import Flask, abort, jsonify, render_template, request, send_file
from PIL import Image

from config import MAX_SHOTS_PER_VIDEO_FOR_AVS, THUMBNAIL_FOLDER, VIDEO_FOLDER
from dres_client import DresClient
from search import ShotSearcher, limit_shots_per_video
from shots import Shot, load_all_shots, shot_id_in_file_name

app = Flask(__name__)
shots_by_id = load_all_shots()
searcher = ShotSearcher()

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
def explain_dres_not_ready(error: RuntimeError):
    return jsonify({"error": str(error)}), 503


@app.errorhandler(requests.RequestException)
def explain_dres_unreachable(error: requests.RequestException):
    return jsonify({"error": f"DRES did not answer properly: {error}"}), 502


def find_shot(shot_id: str) -> Shot:
    if shot_id not in shots_by_id:
        abort(404)
    return shots_by_id[shot_id]


def describe_shots(shot_ids: list[str]) -> list[dict]:
    return [asdict(find_shot(shot_id)) | {"shot_id": shot_id} for shot_id in shot_ids]


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/search")
def search_by_text():
    shot_ids = SEARCH_MODES[request.args["mode"]](request.args["query"])
    if request.args.get("varied") == "yes":
        shot_ids = limit_shots_per_video(shot_ids, MAX_SHOTS_PER_VIDEO_FOR_AVS)
    return jsonify(describe_shots(shot_ids))


@app.post("/search-by-image")
def search_by_image():
    image = Image.open(request.files["image"].stream).convert("RGB")
    return jsonify(describe_shots(searcher.by_example_image(image)))


@app.get("/thumbnail/<shot_id>")
def thumbnail(shot_id: str):
    shot = find_shot(shot_id)
    with zipfile.ZipFile(THUMBNAIL_FOLDER / f"{shot.video_id}.zip") as archive:
        for file_name in archive.namelist():
            if shot_id_in_file_name(file_name) == shot_id:
                return send_file(io.BytesIO(archive.read(file_name)), download_name=file_name)
    abort(404)


@app.get("/video/<video_id>")
def video(video_id: str):
    return send_file(VIDEO_FOLDER / f"{video_id}.mp4", conditional=True)


@app.get("/current-task")
def current_task():
    return jsonify(asdict(dres_client().current_task()))


@app.post("/submit")
def submit():
    shot = find_shot(request.json["shot_id"])
    verdict = dres_client().submit_segment(shot.video_id, shot.start_ms, shot.end_ms)
    return jsonify({"verdict": verdict})


if __name__ == "__main__":
    app.run(port=5000)
