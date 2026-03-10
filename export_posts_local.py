import os
import re
import sqlite3
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests


@dataclass(frozen=True)
class PostRow:
    id: int
    text: str
    date: str


def _state_path(out_root: Path) -> Path:
    return out_root / ".export_state.json"


def _load_state(out_root: Path) -> dict:
    p = _state_path(out_root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(out_root: Path, state: dict) -> None:
    p = _state_path(out_root)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_dirname(name: str) -> str:
    # Windows-safe folder name
    name = name.strip()
    name = name.replace(":", "-")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "post"


def _guess_ext_from_url(url: str) -> str:
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    if ext and len(ext) <= 10:
        return ext
    return ""


def _download_file(url: str, dest_path: Path, timeout_s: int = 30) -> bool:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=timeout_s) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception:
        return False


def _iter_posts(connection: sqlite3.Connection) -> Iterable[PostRow]:
    cursor = connection.cursor()
    cursor.execute("SELECT id, text, date FROM posts ORDER BY id DESC")
    for post_id, text, date in cursor.fetchall():
        yield PostRow(id=int(post_id), text=text or "", date=str(date or ""))


def _iter_posts_newer_than(connection: sqlite3.Connection, last_id: int) -> Iterable[PostRow]:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT id, text, date FROM posts WHERE id > ? ORDER BY id DESC",
        (int(last_id),),
    )
    for post_id, text, date in cursor.fetchall():
        yield PostRow(id=int(post_id), text=text or "", date=str(date or ""))


def _get_post_image_urls(connection: sqlite3.Connection, post_id: int) -> list[str]:
    cursor = connection.cursor()
    cursor.execute("SELECT url FROM images WHERE post_id = ? ORDER BY id ASC", (post_id,))
    return [str(row[0]) for row in cursor.fetchall() if row and row[0]]


def export_posts(
    db_path: str = "posts.db",
    output_dir: str = "posts",
    only_new: bool = True,
) -> tuple[int, int]:
    """
    Экспортирует посты из SQLite базы в локальную папку:
    posts/<дата-время поста>/{text.txt, images...}

    По умолчанию скачивает только новые посты (инкрементально).
    """
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        state = _load_state(out_root)
        last_exported_id = int(state.get("last_exported_id", 0) or 0)

        posts_iter = (
            _iter_posts_newer_than(connection, last_exported_id)
            if only_new and last_exported_id > 0
            else _iter_posts(connection)
        )

        max_exported_id = last_exported_id
        exported_count = 0
        skipped_count = 0

        for post in posts_iter:
            base_name = _safe_dirname(post.date)
            post_dir = out_root / base_name
            # Важно: не создаём дубликаты. Если папка уже есть — считаем пост экспортированным.
            if post_dir.exists():
                skipped_count += 1
                max_exported_id = max(max_exported_id, post.id)
                continue

            post_dir.mkdir(parents=True, exist_ok=True)

            text_path = post_dir / "text.txt"
            text_path.write_text(post.text, encoding="utf-8")

            urls = _get_post_image_urls(connection, post.id)
            for idx, url in enumerate(urls, start=1):
                ext = _guess_ext_from_url(url)
                if not ext:
                    ext = ".jpg"
                img_path = post_dir / f"image_{idx:02d}{ext}"
                ok = _download_file(url, img_path)
                if not ok:
                    # Keep a marker so it's visible what failed
                    with (post_dir / "download_errors.txt").open("a", encoding="utf-8") as f:
                        f.write(f"FAILED: {url}\n")

            # Метаданные помогают восстанавливать состояние при переносах/чистке state-файла
            (post_dir / "meta.json").write_text(
                json.dumps({"id": post.id, "date": post.date}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            exported_count += 1
            max_exported_id = max(max_exported_id, post.id)

        if only_new:
            state["last_exported_id"] = max_exported_id
            _save_state(out_root, state)

    print(f"Exported: {exported_count}, skipped(existing): {skipped_count}")
    return exported_count, skipped_count


def main(argv: Optional[list[str]] = None) -> int:
    exported, skipped = export_posts(only_new=True)
    print("Done. Exported updates to ./posts")
    print(f"Exported: {exported}, skipped(existing): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

