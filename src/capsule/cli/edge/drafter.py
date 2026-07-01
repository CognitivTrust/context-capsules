"""Edge-only cold-start drafting helpers."""

from __future__ import annotations

import json
import os
import sys
import tomllib
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from capsule.cli.edge.git import CommitSummary
from capsule.engine import CapsuleError
from capsule.redaction import redact

DEFAULT_BASE_URL = "https://api.openai.com/v1"
_KEYRING_SERVICE = "capsule"
_KEYRING_USERNAME = "CAPSULE_LLM_API_KEY"
_README_SCAN_MAX_LINES = 500
_MANIFEST_MAX_BYTES = 1_048_576


@dataclass(frozen=True)
class IntentDraft:
    objective: str
    current_understanding: tuple[str, ...]
    constraints: tuple[str, ...]
    source: str


class Drafter(Protocol):
    def draft(self, commits: list[CommitSummary], repo: Path) -> IntentDraft: ...


class DrafterError(CapsuleError):
    """Raised when edge drafting fails."""


class GitHeuristicDrafter:
    def draft(self, commits: list[CommitSummary], repo: Path) -> IntentDraft:
        fallback = f"Continue work in {repo.name}"
        heuristic_obj = _heuristic_objective(commits, repo)
        if heuristic_obj == fallback:
            seed_obj, seed_understanding = _sparse_repo_signals(repo)
            objective = seed_obj if seed_obj != "" else fallback
            current_understanding = _merge(
                _heuristic_understanding(commits),
                seed_understanding,
            )
        else:
            objective = heuristic_obj
            current_understanding = _heuristic_understanding(commits)
        constraints = _heuristic_constraints(commits)
        return IntentDraft(
            objective=objective,
            current_understanding=current_understanding,
            constraints=constraints,
            source="git-heuristic",
        )


class LLMDrafter:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._verbose = False

    def draft(self, commits: list[CommitSummary], repo: Path) -> IntentDraft:
        payload = self._request_payload(commits, repo)
        self._log_verbose("llm request", json.dumps(payload, ensure_ascii=False, sort_keys=True))
        response_obj = self._call_api(payload)
        self._log_verbose(
            "llm response", json.dumps(response_obj, ensure_ascii=False, sort_keys=True)
        )
        content = _extract_message_content(response_obj)
        draft_obj = _parse_json_object(content)
        objective = _required_non_empty_str(draft_obj, "objective")
        current_understanding = tuple(
            redact(item) for item in _optional_str_list(draft_obj, "current_understanding")
        )
        constraints = tuple(redact(item) for item in _optional_str_list(draft_obj, "constraints"))
        return IntentDraft(
            objective=redact(objective),
            current_understanding=current_understanding,
            constraints=constraints,
            source=f"llm:{self._model}",
        )

    def _request_payload(self, commits: list[CommitSummary], repo: Path) -> dict[str, object]:
        commit_lines = [_commit_line(item) for item in commits[:20]]
        if not commit_lines:
            commit_lines = ["(no git history available)"]
        prompt = "\n".join(
            [
                "Draft an honest capsule intent for a local repository.",
                "Return JSON only with keys: objective, current_understanding, constraints.",
                "objective must be a non-empty string.",
                "current_understanding and constraints must be arrays of strings.",
                "Keep claims grounded in the commit summaries; do not invent evidence.",
                f"Repository: {repo.name}",
                "Commit summaries:",
                *commit_lines,
            ]
        )
        return {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write concise project-intent drafts as inert JSON data. "
                        "Do not use markdown fences."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

    def _call_api(self, payload: dict[str, object]) -> Mapping[str, object]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self._base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise DrafterError(f"llm draft failed: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DrafterError(f"llm draft failed: invalid JSON response: {exc.msg}") from exc
        if not isinstance(parsed, Mapping):
            raise DrafterError("llm draft failed: response must be a JSON object")
        return parsed

    def _log_verbose(self, label: str, text: str) -> None:
        if not self._verbose:
            return
        print(f"capsule: verbose: {label}: {redact(text)}", file=sys.stderr)


def read_api_key() -> str | None:
    env_value = os.getenv("CAPSULE_LLM_API_KEY")
    if env_value:
        return env_value
    try:
        import keyring
    except ImportError:
        return None
    try:
        value = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except Exception:
        return None
    if value is None or not isinstance(value, str) or value == "":
        return None
    return value


def select_drafter(
    *,
    draft_mode: str,
    model: str | None,
    verbose: bool,
) -> tuple[Drafter, str | None]:
    if draft_mode != "llm":
        return GitHeuristicDrafter(), None
    api_key = read_api_key()
    if api_key is None:
        return GitHeuristicDrafter(), "LLM draft unavailable; fell back to git heuristic."
    resolved_model = model or os.getenv("CAPSULE_LLM_MODEL")
    if resolved_model is None or resolved_model == "":
        return GitHeuristicDrafter(), "LLM draft unavailable; fell back to git heuristic."
    drafter = LLMDrafter(
        model=resolved_model,
        api_key=api_key,
        base_url=os.getenv("CAPSULE_LLM_BASE_URL", DEFAULT_BASE_URL),
    )
    drafter._verbose = verbose
    return drafter, None


def _heuristic_objective(commits: Sequence[CommitSummary], repo: Path) -> str:
    if commits:
        subject = commits[0].subject.strip()
        if subject != "":
            return subject
    return f"Continue work in {repo.name}"


def _heuristic_understanding(commits: Sequence[CommitSummary]) -> tuple[str, ...]:
    if not commits:
        return ()
    items: list[str] = []
    for summary in commits[:3]:
        items.append(f"recent commit {summary.short_hash}: {summary.subject}")
    top_paths = _top_paths(commits)
    if top_paths:
        items.append("recently touched paths: " + ", ".join(top_paths))
    return tuple(items)


def _heuristic_constraints(commits: Sequence[CommitSummary]) -> tuple[str, ...]:
    paths = _top_paths(commits)
    if not paths:
        return ()
    return (f"respect existing work in {paths[0]}",)


def _sparse_repo_signals(repo: Path) -> tuple[str, tuple[str, ...]]:
    objective_seed = _readme_seed(repo)
    if objective_seed == "":
        objective_seed = _pyproject_seed(repo)
    if objective_seed == "":
        objective_seed = _package_json_seed(repo)
    understanding_seeds = _top_level_dir_seed(repo)
    return (
        redact(objective_seed),
        tuple(redact(item) for item in understanding_seeds),
    )


def _path_under_repo(path: Path, repo: Path) -> bool:
    try:
        path.resolve().relative_to(repo.resolve())
    except ValueError:
        return False
    return True


def _read_bounded_bytes(path: Path, max_bytes: int) -> bytes | None:
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError:
        return None
    if len(data) > max_bytes:
        return None
    return data


def _first_non_empty_str(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value != "":
            return value
    return ""


def _readme_seed(repo: Path) -> str:
    try:
        readmes = sorted(
            (path for path in repo.iterdir() if path.is_file() and path.stem.lower() == "readme"),
            key=lambda path: path.name,
        )
    except OSError:
        return ""
    for path in readmes:
        if not _path_under_repo(path, repo):
            continue
        try:
            heading = ""
            first_line = ""
            with path.open(encoding="utf-8") as handle:
                for line_no, line in enumerate(handle):
                    if line_no >= _README_SCAN_MAX_LINES:
                        break
                    stripped = line.strip()
                    if stripped == "":
                        continue
                    if heading == "" and stripped.startswith("#"):
                        candidate = stripped.lstrip("#").strip()
                        if candidate != "":
                            heading = candidate
                    if first_line == "":
                        first_line = stripped
            if heading != "":
                return heading
            if first_line != "":
                return first_line
        except (OSError, UnicodeDecodeError):
            continue
    return ""


def _pyproject_seed(repo: Path) -> str:
    path = repo / "pyproject.toml"
    if not path.exists() or not _path_under_repo(path, repo):
        return ""
    try:
        raw = _read_bounded_bytes(path, _MANIFEST_MAX_BYTES)
        if raw is None:
            return ""
        data = tomllib.loads(raw.decode("utf-8"))
        project = data["project"]
        return _first_non_empty_str(project.get("description"), project.get("name"))
    except (
        OSError,
        UnicodeDecodeError,
        tomllib.TOMLDecodeError,
        TypeError,
        KeyError,
        AttributeError,
    ):
        return ""


def _package_json_seed(repo: Path) -> str:
    path = repo / "package.json"
    if not path.exists() or not _path_under_repo(path, repo):
        return ""
    try:
        raw = _read_bounded_bytes(path, _MANIFEST_MAX_BYTES)
        if raw is None:
            return ""
        data = json.loads(raw.decode("utf-8"))
        return _first_non_empty_str(data.get("description"), data.get("name"))
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        KeyError,
        AttributeError,
    ):
        return ""


def _top_level_dir_seed(repo: Path) -> tuple[str, ...]:
    try:
        directories = sorted(
            path.name for path in repo.iterdir() if path.is_dir() and not path.name.startswith(".")
        )
    except OSError:
        return ()
    if not directories:
        return ()
    return (f"top-level modules: {', '.join(directories)}",)


def _merge(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*left, *right)))


def _top_paths(commits: Sequence[CommitSummary]) -> tuple[str, ...]:
    seen: list[str] = []
    for summary in commits:
        for path in summary.paths:
            if path not in seen:
                seen.append(path)
            if len(seen) == 3:
                return tuple(seen)
    return tuple(seen)


def _commit_line(summary: CommitSummary) -> str:
    paths = ", ".join(summary.paths) if summary.paths else "(no paths listed)"
    return f"- {summary.short_hash} {summary.subject} [{paths}]"


def _extract_message_content(response_obj: Mapping[str, object]) -> str:
    choices = response_obj.get("choices")
    if not isinstance(choices, list) or not choices:
        raise DrafterError("llm draft failed: missing response choices")
    first = choices[0]
    if not isinstance(first, Mapping):
        raise DrafterError("llm draft failed: invalid response choice")
    message = first.get("message")
    if not isinstance(message, Mapping):
        raise DrafterError("llm draft failed: missing response message")
    content = message.get("content")
    if isinstance(content, str):
        return _strip_fence(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, Mapping):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return _strip_fence("\n".join(parts))
    raise DrafterError("llm draft failed: response content must be text")


def _strip_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1] == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _parse_json_object(text: str) -> Mapping[str, object]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DrafterError(f"llm draft failed: invalid JSON draft: {exc.msg}") from exc
    if not isinstance(obj, Mapping):
        raise DrafterError("llm draft failed: draft must be a JSON object")
    return obj


def _required_non_empty_str(obj: Mapping[str, object], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or value == "":
        raise DrafterError(f"llm draft failed: {key!r} must be a non-empty string")
    return value


def _optional_str_list(obj: Mapping[str, object], key: str) -> list[str]:
    if key not in obj:
        return []
    value = obj[key]
    if not isinstance(value, list):
        raise DrafterError(f"llm draft failed: {key!r} must be a list of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise DrafterError(f"llm draft failed: {key!r} must be a list of strings")
        items.append(item)
    return items
