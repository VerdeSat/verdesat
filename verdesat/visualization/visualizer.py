from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import imageio
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageDraw, ImageFont
from statsmodels.tsa.seasonal import DecomposeResult
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger


class Visualizer:
    """Utility class for all visualization helpers."""

    def __init__(self, logger=None) -> None:
        self.logger = logger or Logger.get_logger(__name__)

    # ------------------------------------------------------------------
    # Time-series plotting
    # ------------------------------------------------------------------
    def plot_timeseries_html(
        self,
        df: pd.DataFrame,
        index_col: str,
        output_path: str,
        agg_freq: Optional[str] = None,
    ) -> None:
        """Create an interactive HTML time-series plot."""

        if agg_freq and agg_freq != "D":
            df = (
                df.set_index("date")
                .groupby("id")[index_col]
                .resample(agg_freq)
                .mean()
                .reset_index()
            )

        fig = px.line(
            df,
            x="date",
            y=index_col,
            color="id",
            title=f"Interactive {index_col.capitalize()} Time Series",
            labels={index_col: index_col, "date": "Date", "id": "Polygon ID"},
            markers=True,
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.write_html(output_path, include_plotlyjs="cdn")

    def plot_time_series(
        self,
        df: pd.DataFrame,
        index_col: str,
        output_path: str,
        agg_freq: str = "D",
    ) -> None:
        """Plot raw or aggregated time series for each polygon and save as PNG."""

        if agg_freq and agg_freq != "D":
            df = (
                df.set_index("date")
                .groupby("id")[index_col]
                .resample(agg_freq)
                .mean()
                .reset_index()
            )

        plt.figure(figsize=(10, 5))
        for pid, group in df.groupby("id"):
            plt.plot(
                group["date"], group[index_col], marker="o", label=f"Polygon {pid}"
            )
        plt.xlabel("Date")
        plt.ylabel(index_col)
        plt.title(f"{index_col} Time Series ({agg_freq})")
        plt.legend()
        plt.grid(True)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

    def plot_decomposition(self, result: DecomposeResult, output_path: str) -> None:
        """Save seasonal decomposition components as a PNG."""

        fig = result.plot()
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path)
        plt.close(fig)

    # ------------------------------------------------------------------
    # Animated GIF helpers
    # ------------------------------------------------------------------
    def make_gif(
        self,
        images_dir: Union[str, Path],
        pattern: str,
        output_path: str,
        duration: float = 2,
        loop: int = 0,
    ) -> None:
        """Build an animated GIF from a directory of image files."""

        images_dir = Path(images_dir)
        files = sorted(images_dir.glob(pattern))
        if not files:
            raise FileNotFoundError(f"No files matching {pattern!r} in {images_dir}")

        frames: List[Image.Image] = []
        for img_path in files:
            arr = imageio.imread(str(img_path))
            im = Image.fromarray(arr)
            draw = ImageDraw.Draw(im)
            date_text = img_path.stem.split("_")[-1]

            default_font = ImageFont.load_default()
            ascent, descent = default_font.getmetrics()
            default_font_height = ascent + descent
            try:
                font = ImageFont.truetype("arial.ttf", default_font_height * 2)
            except Exception:
                font = default_font
            bbox = draw.textbbox((0, 0), date_text, font=font)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.rectangle([5, 5, 5 + text_width, 5 + text_height], fill="black")
            draw.text((5, 5), date_text, fill="white", font_size=14)
            frames.append(im.copy())

        os.makedirs(Path(output_path).parent, exist_ok=True)
        if frames:
            frames[0].save(
                str(output_path),
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=int(duration * 1000),
                loop=loop,
            )

    def make_gifs_per_site(
        self,
        images_dir: Union[str, Path],
        pattern: str,
        output_dir: str,
        duration: float = 2,
        loop: int = 0,
    ) -> None:
        """Generate one GIF per site, grouping files by site ID."""

        images_dir = Path(images_dir)
        files = sorted(images_dir.glob(pattern))
        if not files:
            raise FileNotFoundError(f"No files matching {pattern!r} in {images_dir}")

        from collections import defaultdict

        groups: Dict[str, List[Path]] = defaultdict(list)
        for p in files:
            parts = p.stem.split("_", 2)
            if len(parts) >= 2:
                site = parts[1]
                groups[site].append(p)

        safe_pattern = re.sub(r"[^\w]+", "_", pattern)
        for site, paths in groups.items():
            out_name = f"{site}_{safe_pattern}.gif"
            out_path = Path(output_dir) / out_name

            frames: List[Image.Image] = []
            for p in paths:
                arr = imageio.imread(str(p))
                im = Image.fromarray(arr)
                draw = ImageDraw.Draw(im)
                date_text = p.stem.split("_")[-1]
                default_font = ImageFont.load_default()
                ascent, descent = default_font.getmetrics()
                default_font_height = ascent + descent
                try:
                    font = ImageFont.truetype("arial.ttf", default_font_height * 2)
                except Exception:
                    font = default_font
                bbox = draw.textbbox((0, 0), date_text, font=font)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.rectangle([3, 5, 45 + text_width, 20 + text_height], fill="black")
                draw.text((5, 5), date_text, fill="white", font_size=18)
                frames.append(im.copy())

            os.makedirs(Path(output_dir), exist_ok=True)
            if frames:
                frames[0].save(
                    str(out_path),
                    format="GIF",
                    save_all=True,
                    append_images=frames[1:],
                    duration=int(duration * 1000),
                    loop=loop,
                )
            self.logger.info("Wrote GIF for site %s → %s", site, out_path)

    # ------------------------------------------------------------------
    # Gallery helpers
    # ------------------------------------------------------------------
    def collect_gallery(self, chips_dir: str) -> Dict[int, List[Tuple[str, str]]]:
        """Scan a directory of chips and build a gallery mapping."""

        gallery: Dict[int, List[Tuple[str, str]]] = {}
        p = Path(chips_dir)
        for img in sorted(p.glob("*.png")):
            name = img.stem
            parts = name.split("_", 1)
            pid = int(parts[0])
            date = parts[1]
            gallery.setdefault(pid, []).append((date, str(img)))
        return gallery

    def build_gallery(
        self,
        chips_dir: str,
        output_html: str,
        title: Optional[str] = None,
        template_path: Optional[str] = None,
    ) -> None:
        """Build a simple HTML gallery of image chips."""

        chip_path = Path(chips_dir)
        if not chip_path.is_dir():
            raise ValueError(f"{chips_dir!r} is not a directory")

        gallery: Dict[str, List[Tuple[str, str]]] = {}
        for file in sorted(chip_path.iterdir()):
            if not file.is_file():
                continue
            if file.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif"):
                continue

            name = file.stem
            parts = name.split("_")
            if len(parts) >= 2:
                date = parts[-1]
                site = "_".join(parts[:-1])
            else:
                site = parts[0]
                date = ""

            gallery.setdefault(site, []).append((date, file.name))

        for images in gallery.values():
            images.sort(key=lambda x: x[0])

        if template_path:
            template_dir = Path(template_path)
        else:
            template_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        template = env.get_template("gallery.html.j2")

        html = template.render(title=title, gallery=gallery)

        output_path = Path(os.path.join(chip_path, output_html))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

    # ------------------------------------------------------------------
    def generate_report(
        self,
        output_dir: str,
        title: str,
        map_png: Optional[str] = None,
        timeseries_csv: Optional[str] = None,
        index_name: str | None = None,
    ) -> str:  # pragma: no cover - thin wrapper
        """Generate a report and return its path."""

        from .report import build_report

        output_path = os.path.join(output_dir, "report.html")
        csv_path = timeseries_csv or os.path.join(output_dir, "timeseries.csv")
        build_report(
            geojson_path=os.path.join(output_dir, "aoi.geojson"),
            timeseries_csv=csv_path,
            timeseries_html=os.path.join(output_dir, "timeseries.html"),
            gifs_dir=os.path.join(output_dir, "gifs"),
            decomposition_dir=os.path.join(output_dir, "decomp"),
            chips_dir=os.path.join(output_dir, "chips"),
            map_png=map_png,
            output_path=output_path,
            title=title,
            index_name=index_name or ConfigManager.DEFAULT_INDEX,
        )
        return output_path
