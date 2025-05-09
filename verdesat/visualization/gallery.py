# in verdesat/visualization/gallery.py

import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from jinja2 import Environment, FileSystemLoader


def collect_gallery(chips_dir: str) -> Dict[int, List[Tuple[str, str]]]:
    """
    Scan a directory of chips named like "{id}_{YYYY-MM-DD}.png"
    and return a dict mapping id → list of (date_str, rel_path).
    """
    gallery: Dict[int, List[Tuple[str, str]]] = {}
    p = Path(chips_dir)
    for img in sorted(p.glob("*.png")):
        name = img.stem  # e.g. "3_2021-06-01"
        parts = name.split("_", 1)
        pid = int(parts[0])
        date = parts[1]
        gallery.setdefault(pid, []).append((date, str(img)))
    return gallery


def build_gallery(
    chips_dir: str,
    output_html: str,
    title: Optional[str] = None,
    template_path: Optional[str] = None,
) -> None:
    """
    Build a simple HTML gallery of image chips.

    Args:
        chip_dir: Directory containing image files named like "<site>_<YYYY-MM-DD>.<ext>"
        output_html: Path to write the generated HTML file.
        title: Optional page title.
        template_path: Optional directory containing the Jinja2 template (defaults to built-in templates).
    """
    chip_path = Path(chips_dir)
    if not chip_path.is_dir():
        raise ValueError(f"{chips_dir!r} is not a directory")

    # Gather image files
    gallery: Dict[str, List[Tuple[str, str]]] = {}
    for file in sorted(chip_path.iterdir()):
        if not file.is_file():
            continue
        if file.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif"):
            continue

        name = file.stem  # filename without extension
        parts = name.split("_")
        if len(parts) >= 2:
            date = parts[-1]
            site = "_".join(parts[:-1])
        else:
            site = parts[0]
            date = ""

        gallery.setdefault(site, []).append((date, file.name))

    # Sort each site's images by date
    for images in gallery.values():
        images.sort(key=lambda x: x[0])

    # Determine which template directory to use
    if template_path:
        template_dir = Path(template_path)
    else:
        template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )
    template = env.get_template("gallery.html.j2")

    html = template.render(title=title, gallery=gallery)

    # Write out
    output_path = Path(os.path.join(chip_path, output_html))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
