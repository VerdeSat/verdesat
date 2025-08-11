"""Central store for versioned prompts used by :mod:`ai_report` services."""

from __future__ import annotations

from dataclasses import dataclass

PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class PromptBundle:
    """Container for the different prompt roles."""

    system: str
    developer: str
    user: str


_PROMPTS: dict[str, PromptBundle] = {
    "v1": PromptBundle(
        system=(
            "You are an environmental analyst producing screening-grade reports. "
            "Stay objective and cite numeric keys (e.g., ndvi_mean=0.57)."
        ),
        developer=(
            "Output must comply with ai_report.v1 schema. Use metric units, no legal"
            " or species claims. Round values to two decimals."
        ),
        user=(
            "AOI {aoi_id} ({project_id})\n"
            "WINDOW: {window_start} → {window_end}\n"
            "METRICS ROW:\n{metrics_row}\n"
            "TIME SERIES (ndvi; YYYY-MM, value):\n{timeseries}\n"
            "CONTEXT: {context}\n"
            "Produce JSON conforming to schema ai_report.v1 only."
        ),
    )
}


def get_prompts(version: str = PROMPT_VERSION) -> PromptBundle:
    """Return prompts for *version*.

    Parameters
    ----------
    version:
        Prompt version identifier. Defaults to :data:`PROMPT_VERSION`.
    """

    try:
        return _PROMPTS[version]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown prompt version: {version}") from exc
