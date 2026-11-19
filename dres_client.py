"""Log in to DRES, read the current task and submit answers, following the official DRES v2 API."""
from dataclasses import dataclass, field

import requests

REQUEST_TIMEOUT_SECONDS = 10
RUNNING = "RUNNING"


@dataclass(frozen=True)
class TaskClue:
    kind: str  # "TEXT", "VIDEO" or "IMAGE"
    content: str  # the text itself, or a base64-encoded video or image
    shown_after_seconds: int


@dataclass(frozen=True)
class CurrentTask:
    name: str = ""
    task_type: str = ""
    status: str = "NO_TASK"
    seconds_left: int | None = None
    clues: list[TaskClue] = field(default_factory=list)


class DresClient:
    def __init__(self, server_url: str, username: str, password: str):
        self.server_url = server_url.rstrip("/")
        self.session_id = self._log_in(username, password)

    def current_task(self) -> CurrentTask:
        evaluation_id = self._active_evaluation_id()
        state = self._get(f"/api/v2/evaluation/{evaluation_id}/state")
        if state["taskStatus"] != RUNNING:
            return CurrentTask(status=state["taskStatus"])
        summary = self._get(f"/api/v2/client/evaluation/currentTask/{evaluation_id}")
        hint = self._get(
            f"/api/v2/evaluation/{evaluation_id}/template/task/{state['taskTemplateId']}/hint"
        )
        return CurrentTask(
            name=summary["name"],
            task_type=summary["taskType"],
            status=state["taskStatus"],
            seconds_left=state.get("timeLeft"),
            clues=clues_shown_so_far(hint["sequence"], state["timeElapsed"]),
        )

    def submit_segment(self, video_id: str, start_ms: int, end_ms: int) -> str:
        answer = {"mediaItemName": video_id, "start": start_ms, "end": end_ms}
        response = requests.post(
            f"{self.server_url}/api/v2/submit/{self._active_evaluation_id()}",
            params={"session": self.session_id},
            json={"answerSets": [{"answers": [answer]}]},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        result = response.json()
        return result.get("submission") or result.get("description", "")

    def _log_in(self, username: str, password: str) -> str:
        response = requests.post(
            f"{self.server_url}/api/v2/login",
            json={"username": username, "password": password},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["sessionId"]

    def _active_evaluation_id(self) -> str:
        evaluations = self._get("/api/v2/client/evaluation/list")
        active = [evaluation for evaluation in evaluations if evaluation["status"] == "ACTIVE"]
        if not active:
            raise RuntimeError("DRES has no active evaluation yet. Wait for the task to start.")
        return active[0]["id"]

    def _get(self, path: str):
        response = requests.get(
            f"{self.server_url}{path}",
            params={"session": self.session_id},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()


def clues_shown_so_far(sequence: list[dict], seconds_elapsed: int) -> list[TaskClue]:
    # DRES can reveal a task's clues over time. Only show the ones the projector
    # would already be showing, so we see exactly what every other team sees.
    return [
        TaskClue(element["contentType"], element["content"], element["offset"])
        for element in sequence
        if element.get("content") and element["offset"] <= seconds_elapsed
    ]
