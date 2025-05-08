import os
from pathlib import Path
import imageio
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Union


def make_gif(
    images_dir: Union[str, Path],
    pattern: str,
    output_path: str,
    duration: float = 2,
    loop: int = 0,
) -> None:
    """
    Build an animated GIF from a directory of image files.

    Args:
        images_dir: Path to folder containing image files.
        pattern: filename glob to select frames (e.g. '*_NDVI_*.png').
        output_path: Path to write the resulting GIF.
        duration: seconds per frame.
        loop: how many times to loop (0 = infinite).
    """
    images_dir = Path(images_dir)
    files = sorted(images_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} in {images_dir}")

    # Annotate and collect frames
    frames: list[np.ndarray] = []
    for img_path in files:
        arr = imageio.imread(str(img_path))
        im = Image.fromarray(arr)
        draw = ImageDraw.Draw(im)
        date_text = img_path.stem.split("_")[-1]
        # Calculate default font size and load a TrueType font twice that size if possible
        default_font = ImageFont.load_default()
        # Determine default font height using font metrics
        ascent, descent = default_font.getmetrics()
        default_font_height = ascent + descent
        # Try to load larger TrueType font
        try:
            font = ImageFont.truetype("arial.ttf", default_font_height * 2)
        except Exception:
            font = default_font
        # Compute text bounding box to get width and height
        bbox = draw.textbbox((0, 0), date_text, font=font)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        # Draw black rectangle behind text
        draw.rectangle([5, 5, 5 + text_width, 5 + text_height], fill="black")
        # Draw white text
        draw.text((5, 5), date_text, fill="white", font_size=14)
        frames.append(np.array(im))

    # ensure parent folder exists
    os.makedirs(Path(output_path).parent, exist_ok=True)
    # Write GIF with correct duration and loop settings
    with imageio.get_writer(
        str(output_path), mode="I", duration=duration, loop=loop
    ) as writer:
        for frame in frames:
            writer.append_data(frame)


# New function: make_gifs_per_site
def make_gifs_per_site(
    images_dir: Union[str, Path],
    pattern: str,
    output_dir: str,
    duration: float = 2,
    loop: int = 0,
) -> None:
    """
    Scan images_dir for files matching pattern, group by site-ID (2nd token in filename),
    and generate one GIF per site, with the pattern included in the filename.
    """
    images_dir = Path(images_dir)
    files = sorted(images_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} in {images_dir}")

    # Group files by site ID (assumes filenames like any_<site>_<date>.<ext>)
    from collections import defaultdict

    groups: dict[str, list[Path]] = defaultdict(list)
    for p in files:
        parts = p.stem.split("_", 2)
        if len(parts) >= 2:
            site = parts[1]
            groups[site].append(p)

    # sanitize pattern for filenames (e.g. replace '*' with 'STAR')
    safe_pattern = re.sub(r"[^\w]+", "_", pattern)
    for site, paths in groups.items():
        out_name = f"{site}_{safe_pattern}.gif"
        out_path = Path(output_dir) / out_name
        # Annotate frames
        frames: list[np.ndarray] = []
        for p in paths:
            arr = imageio.imread(str(p))
            im = Image.fromarray(arr)
            draw = ImageDraw.Draw(im)
            date_text = p.stem.split("_")[-1]
            # Calculate default font size and load a TrueType font twice that size if possible
            default_font = ImageFont.load_default()
            # Determine default font height using font metrics
            ascent, descent = default_font.getmetrics()
            default_font_height = ascent + descent
            # Try to load larger TrueType font
            try:
                font = ImageFont.truetype("arial.ttf", default_font_height * 2)
            except Exception:
                font = default_font
            # Compute text bounding box to get width and height
            bbox = draw.textbbox((0, 0), date_text, font=font)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            # Draw black rectangle behind text
            draw.rectangle([3, 5, 45 + text_width, 20 + text_height], fill="black")
            # Draw white text
            draw.text((5, 5), date_text, fill="white", font_size=18)
            frames.append(np.array(im))
        # ensure output directory exists
        os.makedirs(Path(output_dir), exist_ok=True)
        # Write GIF
        with imageio.get_writer(
            str(out_path), mode="I", duration=duration, loop=loop
        ) as writer:
            for frame in frames:
                writer.append_data(frame)
        print(f"✅  Wrote GIF for site {site} → {out_path}")
