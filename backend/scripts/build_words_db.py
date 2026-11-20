"""
Build assets/words.sqlite from the CMU Pronouncing Dictionary (run at Docker build time and in local setup).
One row per pronunciation: word, phones, stresses, rhyme. On disk so the 512 MB server never holds the
135,000-word dictionary in memory; each lookup is one indexed query.

  venv/bin/python scripts/build_words_db.py
"""
from __future__ import annotations

import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "assets" / "words.sqlite"


def main() -> int:
    import cmudict

    from app.services.words.sound import rhyming_part, stresses

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute("CREATE TABLE words (word TEXT NOT NULL, rank INTEGER NOT NULL, phones TEXT NOT NULL, stresses TEXT NOT NULL, rhyme TEXT NOT NULL)")
    rows = []
    for word, prons in cmudict.dict().items():
        for rank, p in enumerate(prons):
            ph = " ".join(p)
            rows.append((word, rank, ph, stresses(ph), rhyming_part(ph)))
    db.executemany("INSERT INTO words VALUES (?,?,?,?,?)", rows)
    db.execute("CREATE INDEX idx_word ON words (word, rank)")
    db.execute("CREATE INDEX idx_rhyme ON words (rhyme)")
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(OUT)
    print(f"{OUT}: {len(rows)} pronunciations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
