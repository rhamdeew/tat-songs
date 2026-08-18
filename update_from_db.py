#!/usr/bin/env python3
"""Sync translated/*.md lyrics with the source-of-truth sqlite3 DB.

Source of truth: /Users/rail/Work/python/tat-songs-lyrics/data/db.sqlite3
(songs_song.original / songs_song.ru_translate / songs_song.name / songs_song.ru_name)

Matches DB rows to local .md files by slug == filename (without .md),
falling back to a normalized match (strip everything but [a-z0-9_-])
for the handful of slugs that drifted due to diacritics cleanup on
the DB side.

Only the lyrics body and the song-name portion of the title lines are
updated; the "Artist / Artist2" prefix already present in each .md file
is preserved as-is, since reconstructing it from writer/producer/artist
tables is unnecessary risk for content that hasn't changed.
"""
import argparse
import re
import sqlite3
from pathlib import Path

DB_PATH = Path("/Users/rail/Work/python/tat-songs-lyrics/data/db.sqlite3")
TRANSLATED_DIR = Path(__file__).resolve().parent / "translated"

TITLE_RE = re.compile(
    r"(# Оригинал\s*\n\s*###\s*)([^\n]+)(\n\n```\n)(.*?)(\n```\n*\n*-+\n*\n*"
    r"# Перевод\s*\n\s*###\s*)([^\n]+)(\n\n```\n)(.*?)(\n```\n*)$",
    re.DOTALL,
)


def normalize(slug: str) -> str:
    return re.sub(r"[^a-z0-9_\-]", "", slug.lower())


def split_title(title: str) -> tuple[str, str]:
    """Split 'Artist - Song Name' into (artist_prefix, song_name)."""
    if " - " in title:
        artist, name = title.rsplit(" - ", 1)
        return artist, name
    return "", title


def load_db_rows(db_path: Path) -> dict[str, dict]:
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("select slug, name, ru_name, original, ru_translate from songs_song")
    rows = {}
    for slug, name, ru_name, original, ru_translate in cur.fetchall():
        rows[slug] = {
            "name": name,
            "ru_name": ru_name,
            "original": original.strip(),
            "ru_translate": ru_translate.strip(),
        }
    con.close()
    return rows


def build_content(orig_artist, name, original_lyrics, trans_artist, ru_name, translated_lyrics) -> str:
    orig_title = f"{orig_artist} - {name}" if orig_artist else name
    trans_title = f"{trans_artist} - {ru_name}" if trans_artist else ru_name
    return (
        "# Оригинал\n\n"
        f"### {orig_title}\n\n"
        "```\n"
        f"{original_lyrics}\n"
        "```\n\n"
        "------\n\n"
        "# Перевод\n\n"
        f"### {trans_title}\n\n"
        "```\n"
        f"{translated_lyrics}\n"
        "```\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N files (debugging)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    db_rows = load_db_rows(DB_PATH)
    db_by_norm = {}
    for slug, row in db_rows.items():
        db_by_norm.setdefault(normalize(slug), slug)

    md_files = sorted(TRANSLATED_DIR.rglob("*.md"))
    if args.limit:
        md_files = md_files[: args.limit]

    updated = 0
    unchanged = 0
    not_found = []
    parse_failed = []

    for path in md_files:
        slug = path.stem
        row = db_rows.get(slug)
        if row is None:
            norm_slug = db_by_norm.get(normalize(slug))
            row = db_rows.get(norm_slug) if norm_slug else None
        if row is None:
            not_found.append(slug)
            continue

        content = path.read_text(encoding="utf-8")
        m = TITLE_RE.match(content)
        if not m:
            parse_failed.append(slug)
            continue

        orig_artist, _old_name = split_title(m.group(2).strip())
        trans_artist, _old_ru_name = split_title(m.group(6).strip())

        new_content = build_content(
            orig_artist, row["name"], row["original"],
            trans_artist, row["ru_name"], row["ru_translate"],
        )

        if new_content != content:
            updated += 1
            if not args.dry_run:
                path.write_text(new_content, encoding="utf-8")
        else:
            unchanged += 1

    print(f"Total .md files:   {len(md_files)}")
    print(f"Updated:           {updated}{' (dry-run, not written)' if args.dry_run else ''}")
    print(f"Unchanged:         {unchanged}")
    print(f"No DB match:       {len(not_found)}")
    print(f"Title parse fail:  {len(parse_failed)}")

    if not_found:
        print("\n-- files with no DB match --")
        for s in not_found:
            print(" ", s)
    if parse_failed:
        print("\n-- files with unexpected structure (skipped) --")
        for s in parse_failed:
            print(" ", s)


if __name__ == "__main__":
    main()
