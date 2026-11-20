# Shot Search: interactive video retrieval (Search Technologies, Assignment 2)

A local web app for searching the 1,000-video V3C1 sample, playing a shot to check it,
and submitting it to DRES.

- **Picture search:** OpenCLIP text → thumbnail similarity (one thumbnail per official shot).
- **Screenshot search (KIS-V):** upload, paste (Ctrl+V), or grab a frame from the DRES clip.
- **More like this:** re-search with any result's own CLIP vector.
- **Speech / title search:** SQLite FTS5 (BM25) over Whisper transcripts plus video title and tags.
- **Both:** picture and speech rankings fused with reciprocal rank fusion.
- **AVS diversity:** optional cap of 3 shots per video. Tick results to submit many at once.
- **DRES:** choose the run (evaluation) to work on, follow its current task (text, image or video clue
  plus countdown) and submit to that run with a confirm step. Every submission is logged to
  `submissions.jsonl`. Several runs can be active at once, so the app never guesses which one.

All commands below run from this `project/` folder in a Windows terminal.

## 1. Set up (once per machine)

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**GPU machine:** install the CUDA build of torch *before* the line above. Take the
exact command from https://pytorch.org/get-started/locally/ (pip, Windows, CUDA). Check it with
`.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"`, which should print `True`.

**Windows Smart App Control:** if importing `open_clip` fails with "An Application Control policy has
blocked this file", Windows is blocking a brand-new `regex` DLL. `requirements.txt` pins an older
`regex` for this reason, so don't upgrade it.

## 2. Get the data (once per machine)

The code expects `assignment2_data/{msb,thumbnails,videos_480p}/` and
`assignment2_data/videos_metadata.json`, plus `transcripts/<v3cId>.srt`.

- Course data: the `.tar` files from the Onedata web share have a broken first header (Explorer shows
  one empty file). Unpack them, and `msb.zip`, with:
  ```
  python unpack_data.py ../videos_480p.tar ../thumbnails.tar ../msb.zip ../videos_metadata.json
  ```
  Files fetched with `student_download.py` are already in the right layout.
  Set `--dest assignment2_data` and run it from this folder.
- Transcripts: download `V3C1.zip` from https://zenodo.org/records/7383303 and copy the `.srt` files
  for our 1,000 ids into `transcripts/`.

## 3. Build the indexes

```
.venv\Scripts\python.exe build_text_index.py      # about 5 s
.venv\Scripts\python.exe build_image_index.py     # CLIP; time depends on machine and model
```

`build_image_index.py` saves after every video, so if it stops, run it again and it resumes.
Pick the model with environment variables (the default is `ViT-B-32` / `laion2b_s34b_b79k`):

```
$env:CLIP_MODEL = "ViT-L-14"                 # cmd: set CLIP_MODEL=ViT-L-14
$env:CLIP_WEIGHTS = "laion2b_s32b_b82k"      # cmd: set CLIP_WEIGHTS=laion2b_s32b_b82k
.venv\Scripts\python.exe build_image_index.py
```

Measured so far: ViT-B-32 on a 4-core laptop CPU (i7-8665U) encodes about 20 thumbnails/s,
roughly 2 h for all 141,156 shots. A gaming GPU is far faster, so build bigger models there.
`bench_clip.py` measures the speed on any machine.

**Moving an index to another machine:** copy the whole `index/` folder.
`image_index_model.txt` records which model built it, and the app always encodes queries with
that same model. The first start on the new machine downloads that model's weights (internet needed).

## 4. Run the app

PowerShell (the default terminal in VS Code on Windows):

```
$env:DRES_URL = "https://..."      # from the team email
$env:DRES_USER = "..."
$env:DRES_PASSWORD = "..."
.venv\Scripts\python.exe app.py
```

In Command Prompt (cmd), use `set DRES_URL=https://...` instead. The settings last only for that
terminal window, so they never end up in a file or in git.

From a WSL terminal, run the same Windows venv. WSL passes variables to Windows programs only when
they are listed in `WSLENV`:

```bash
cd "/mnt/c/Users/User/Documents/Y4S1/search tech assignment 2/project"
export DRES_URL="https://..." DRES_USER="..." DRES_PASSWORD="..."
export WSLENV="DRES_URL:DRES_USER:DRES_PASSWORD"
.venv/Scripts/python.exe app.py
```

Open http://localhost:5000 in **Chrome or Edge**. The videos are H.265/HEVC, which Firefox can't play.
The DRES settings are only needed for "Connect to DRES" and for submitting. Without them,
searching and playback still work. Without CLIP or an image index, the app starts with speech/title
search only and says why.

At the event, once the model weights are downloaded, `$env:HF_HUB_OFFLINE = "1"` stops the app
from contacting the Hugging Face Hub on start-up.

## Using it

| Want to | Do |
|---|---|
| Start a session | "Connect to DRES", then choose the run from the dropdown. That run is followed and submitted to |
| Describe the shot (KIS-T, AVS) | Type in the box, "What it looks like", Enter |
| Find the clip's shot (KIS-V) | "Search with this frame" on the task clip, or Win+Shift+S then Ctrl+V |
| Check a result | Click the thumbnail: the right panel plays exactly that shot |
| Refine | ≈ on a thumbnail (or "More like this" under the player) |
| Submit one shot (KIS) | "Submit this shot" under the player, then confirm |
| Submit many (AVS) | Tick "Max 3 per video", ✓ the good ones, "Submit selected", confirm |

Green border = already submitted this session, orange = selected.
The history list under the player shows every DRES verdict.

## Files

| File | Role |
|---|---|
| `config.py` | Paths and settings |
| `shots.py` | Official shot list from `msb/*.tsv` (seconds → ms) |
| `unpack_data.py` | Unpacks the course downloads |
| `clip_encoder.py` | OpenCLIP wrapper (unit-length vectors, cosine via dot product) |
| `build_image_index.py` | CLIP vector per shot thumbnail → `index/image_vectors.npy` |
| `build_text_index.py` | Transcript plus title/tags per shot → `index/text_index.sqlite` |
| `search.py` | All ranking: CLIP, BM25, rank fusion, per-video cap |
| `dres_client.py` | DRES v2 client API: login, current task, submit |
| `app.py`, `templates/`, `static/` | Flask web UI |
| `bench_clip.py` | Measures CLIP encoding speed |

## External resources (disclose in the report)

- V3C1 sample (Schoeffmann et al., MMM 2019) and its master shot boundaries
- OpenCLIP (Ilharco et al.) with LAION-2B-trained weights, downloaded from the Hugging Face Hub
- Whisper "small" transcripts of V3C1, Zenodo record 7383303 (CC-BY-4.0)
- DRES (dres.dev) client API
