"""
Module `visualization._chips_config` defines `ChipsConfig`, a container for CLI parameters
needed to generate per-AOI image chips.
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

from verdesat.core.config import ConfigManager


@dataclass
class ChipsConfig:
    """Holds all parameters needed to generate per‐AOI chips."""

    collection_id: str
    start: str
    end: str
    period: str
    chip_type: str
    scale: int
    buffer: int
    buffer_percent: Optional[float]
    min_val: Optional[float]
    max_val: Optional[float]
    gamma: Optional[float]
    percentile_low: Optional[float]
    percentile_high: Optional[float]
    palette: Optional[Tuple[str, ...]] = field(default=None)
    fmt: str = "png"
    out_dir: str = "chips"
    mask_clouds: bool = True

    def __post_init__(self) -> None:
        self.palette = tuple(self.palette) if self.palette is not None else None
        self.fmt = self.fmt.lower()

    @classmethod
    def from_cli(
        cls,
        collection: str,
        start: str,
        end: str,
        period: str,
        chip_type: str,
        scale: int,
        buffer: int,
        buffer_percent: Optional[float],
        min_val: Optional[float],
        max_val: Optional[float],
        gamma: Optional[float],
        percentile_low: Optional[float],
        percentile_high: Optional[float],
        palette_arg: Optional[str],
        fmt: str,
        out_dir: str,
        mask_clouds: bool,
    ):
        """
        Helper to parse palette_arg into a list of colors and then forward to init.
        """
        palette = None
        if palette_arg:
            if palette_arg in ConfigManager.PRESET_PALETTES:
                palette = ConfigManager.PRESET_PALETTES[palette_arg]
            else:
                palette = tuple(c.strip() for c in palette_arg.split(",") if c.strip())

        return cls(
            collection_id=collection,
            start=start,
            end=end,
            period=period,
            chip_type=chip_type,
            scale=scale,
            buffer=buffer,
            buffer_percent=buffer_percent,
            min_val=min_val,
            max_val=max_val,
            gamma=gamma,
            percentile_low=percentile_low,
            percentile_high=percentile_high,
            palette=palette,
            fmt=fmt,
            out_dir=out_dir,
            mask_clouds=mask_clouds,
        )
