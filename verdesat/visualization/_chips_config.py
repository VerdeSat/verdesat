# verdesat/visualization/chips_config.py

from typing import Optional, Sequence


class ChipsConfig:
    """
    Holds all parameters needed to generate per‐AOI chips.

    Attributes:
      collection_id: Earth Engine ImageCollection ID
      start: "YYYY-MM-DD" string
      end: "YYYY-MM-DD" string
      period: "M" or "Y"
      chip_type: either a comma‐separated list of band aliases, or an index name
      scale: integer (meters)
      buffer: absolute buffer in meters
      buffer_percent: optional percent of AOI for buffer
      min_val / max_val: optional stretch overrides
      gamma: optional gamma value
      percentile_low / percentile_high: optional percentiles for auto‐stretch
      palette: optional list of color strings (hex or named)
      fmt: "png" or "geotiff"
      out_dir: output directory path
      mask_clouds: bool
    """

    def __init__(
        self,
        collection_id: str,
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
        palette: Optional[Sequence[str]],
        fmt: str,
        out_dir: str,
        mask_clouds: bool,
    ):
        self.collection_id = collection_id
        self.start = start
        self.end = end
        self.period = period
        self.chip_type = chip_type
        self.scale = scale
        self.buffer = buffer
        self.buffer_percent = buffer_percent
        self.min_val = min_val
        self.max_val = max_val
        self.gamma = gamma
        self.percentile_low = percentile_low
        self.percentile_high = percentile_high
        self.palette = list(palette) if palette is not None else None
        self.fmt = fmt.lower()
        self.out_dir = out_dir
        self.mask_clouds = mask_clouds

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

            from verdesat.core.config import PRESET_PALETTES

            if palette_arg in PRESET_PALETTES:
                palette = PRESET_PALETTES[palette_arg]
            else:
                palette = [c.strip() for c in palette_arg.split(",") if c.strip()]

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
