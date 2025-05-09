import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


def collect_assets(
    base_dir: str,
    filename_regex: str,
    key_fn: Callable[[re.Match], Any] = lambda m: m.group("id"),
    date_fn: Callable[[re.Match], Any] = lambda m: m.group("date"),
) -> Dict[str, List[Tuple[str, str]]]:
    """
    Scan base_dir for files whose names match filename_regex.
    filename_regex must contain named groups "id" and "date".
    Returns { id: [(date, str(path)), …], … } sorted by date.
    """
    pattern = re.compile(filename_regex)
    by_id: Dict[str, List[Tuple[str, str]]] = {}
    for p in Path(base_dir).glob("*"):
        m = pattern.match(p.name)
        if not m:
            continue
        pid = key_fn(m)
        date = date_fn(m)
        by_id.setdefault(str(pid), []).append((str(date), str(p)))
    for pid, lst in by_id.items():
        lst.sort(key=lambda x: x[0])
    return by_id
