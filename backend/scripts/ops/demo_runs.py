"""
The three demo stories on the deployed URL (ship-it spec 13, requirement 3), each with a fresh account, recorded to
docs/demo-runs/<date>-demo<N>.md: steps, what Frank said, times, problems.

  demo 1  a feeling and lyrics become a sung, finished song   (voice first)
  demo 2  a phone hum becomes a produced song                 (tune first; the beat follows the hum)
  demo 3  "something feels wrong": directions, preview, use one, go back

  venv/bin/python scripts/ops/demo_runs.py [1 2 3]
"""
from __future__ import annotations

import datetime
import os
import pathlib
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))
import e2e  # noqa: E402

DOCS = pathlib.Path(__file__).resolve().parents[3] / "docs" / "demo-runs"


class Log:
    def __init__(self, title: str) -> None:
        self.title, self.lines, self.problems, self.t0 = title, [], [], time.time()

    def step(self, what: str, detail: str = "") -> None:
        line = f"- **{time.time() - self.t0:6.0f}s** {what}" + (f": {detail}" if detail else "")
        self.lines.append(line)
        print(line, flush=True)

    def problem(self, what: str) -> None:
        self.problems.append(what)
        print("PROBLEM:", what, flush=True)


def job(h: dict, log: Log, job_id: str, label: str) -> dict:
    t = time.time()
    while True:
        j = e2e.call(h, "GET", f"/jobs/{job_id}/status")
        if j["status"] == "complete":
            log.step(f"{label} done in {time.time() - t:.0f}s")
            return j["result"]
        if j["status"] == "failed":
            raise RuntimeError(f"{label} failed: {j.get('error')}")
        time.sleep(4)


LYRICS = ("Verse\nShe hummed by the window every night\nThe kettle sang along with her\n\n"
          "Chorus\nSing it back to me, grandmother\nThe porch light still on\nSing it back to me\n\n"
          "Verse\nI kept the old radio she loved\nIt only finds the static now\n\n"
          "Chorus\nSing it back to me, grandmother\nThe porch light still on\nSing it back to me")


def demo1(h: dict, log: Log) -> None:
    pid = e2e.call(h, "POST", "/projects", json={"title": "For my grandmother"})["id"]
    r = e2e.call(h, "POST", f"/projects/{pid}/intake/description", json={"text": "a song for my grandmother, who sang to me every night; warm, a little sad, like a kitchen at night"})
    log.step("described the feeling", r["message"])
    e2e.call(h, "POST", f"/projects/{pid}/lyrics", json={"content": LYRICS, "label": "v1"})
    r = e2e.call(h, "POST", f"/projects/{pid}/intake/lyrics", json={"content": LYRICS})
    log.step("Frank read the words", r["message"])
    fp = (e2e.call(h, "GET", f"/projects/{pid}/feel/fingerprint") or {}).get("fingerprint") or {}
    b = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/beat/generate", json={"fingerprint": fp})["job_id"], "beat built")
    g = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/voice/guide")["job_id"], "sing-along guide")
    log.step("guide", "ready" if g.get("guide_url") else g.get("message", ""))
    form = {"beat_version_id": b["beat_version_id"], "beat_offset_s": "0", "lead_in_s": "0.3", "headphones": "true"}
    takes = []
    for k in range(2):
        up = e2e.call(h, "POST", f"/projects/{pid}/voice/takes", files={"file": ("take.wav", e2e.sung_take(detune=0.3 * k), "audio/wav")}, data=form)
        a = job(h, log, up["analysis_job_id"], f"take {k + 1} listened to")
        log.step(f"engineer after take {k + 1}", a.get("engineer") or "(nothing to say)")
        takes.append(up["take"]["id"])
    t = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/voice/takes/{takes[1]}/correct", json={"mode": "moderate"})["job_id"], "tuned")
    log.step("Frank on tuning", t["message"])
    c = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/voice/comp", json={"take_ids": takes})["job_id"], "best-of version")
    log.step("Frank on the best-of", c["message"])
    hm = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/voice/harmony", json={"take_id": takes[0], "type": "above"})["job_id"], "harmony")
    log.step("harmony", hm.get("message", ""))
    m = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/mix/render", json={"mix_params": {}, "quality": "full"})["job_id"], "mix")
    it = e2e.call(h, "GET", f"/projects/{pid}/finish/intent")
    log.step("intent check", it["question"])
    if not it["intent"]:
        log.problem("the intent statement was not kept")
    e2e.call(h, "POST", f"/projects/{pid}/finish/intent", json={"yes": True})
    f = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/export", json={"mix_version_id": m["mix_version_id"], "apply_mastering": True})["job_id"], "finished")
    log.step("finishing", str(f.get("finish")))
    if not (f.get("finish") or {}).get("on_target"):
        log.problem("finishing missed the streaming loudness")
    dl = e2e.call(h, "GET", f"/projects/{pid}/export")[0]
    size = len(e2e.c.get(dl["audio_url"]).content)
    log.step("downloaded", f"{size} bytes, {dl['format']} {dl['quality']}")


def demo2(h: dict, log: Log) -> None:
    pid = e2e.call(h, "POST", "/projects", json={"title": "Phone hum"})["id"]
    rec = e2e.call(h, "POST", f"/projects/{pid}/intake/recording", files={"file": ("hum.wav", e2e.sung_take(), "audio/wav")})
    log.step("recorded a hum (one way in)", f"Frank took the {rec['kind']} path")
    if rec["kind"] != "hum":
        log.problem("a hum was taken as speech")
        return
    hum = job(h, log, rec["job_id"], "tune found")
    log.step("Frank on the tune", hum.get("description") or hum.get("reason", ""))
    if not hum.get("ok"):
        log.problem("the hum was turned away")
        return
    conf = e2e.call(h, "POST", f"/projects/{pid}/intake/melody/{hum['version_id']}/confirm")
    hints = conf.get("fingerprint_hints") or {}
    log.step("confirmed 'yes, that's my tune'", conf.get("question") or "")
    fp = {"energy_level": 0.55, "density": 0.5, "warmth": 0.6, "brightness": 0.45, **hints}
    e2e.call(h, "POST", f"/projects/{pid}/feel/fingerprint", json={"fingerprint": fp, "conversation_summary": "from a hum"})
    b = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/beat/generate", json={"fingerprint": fp})["job_id"], "beat built around the hum")
    log.step("the beat plays the hum", str(b.get("lead_used")))
    if not b.get("lead_used"):
        log.problem("the beat does not play the person's tune")
    op = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/beat/operations", json={"operations": [{"op": "sparser", "part": "drums", "section": 1}]})["job_id"], "a change: simpler drums in the first verse")
    log.step("Frank on the change", " ".join(op.get("changes") or []))
    up = e2e.call(h, "POST", f"/projects/{pid}/voice/takes", files={"file": ("take.wav", e2e.sung_take(), "audio/wav")})
    job(h, log, up["analysis_job_id"], "take listened to")
    m = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/mix/render", json={"mix_params": {}, "quality": "full"})["job_id"], "mix")
    f = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/export", json={"mix_version_id": m["mix_version_id"], "apply_mastering": True})["job_id"], "finished")
    dl = e2e.call(h, "GET", f"/projects/{pid}/export")[0]
    log.step("downloaded", f"{len(e2e.c.get(dl['audio_url']).content)} bytes; loudness {(f.get('finish') or {}).get('loudness')}")


def demo3(h: dict, log: Log) -> None:
    pid = e2e.call(h, "POST", "/projects", json={"title": "Something feels wrong"})["id"]
    fp = {"tempo_bpm": 96, "key": "A minor", "mode": "minor", "energy_level": 0.6, "density": 0.5, "brightness": 0.4, "warmth": 0.6}
    e2e.call(h, "POST", f"/projects/{pid}/feel/fingerprint", json={"fingerprint": fp, "conversation_summary": "moody"})
    job(h, log, e2e.call(h, "POST", f"/projects/{pid}/beat/generate", json={"fingerprint": fp})["job_id"], "beat built")
    said = e2e.call(h, "POST", f"/projects/{pid}/beat/conversation", json={"message": "something feels off with the chorus but I don't know what", "beat_state": {}, "history": []})
    log.step("person: 'something feels off with the chorus'", said["message"])
    acts = [a["type"] for a in said.get("actions", [])]
    log.step("Frank's action", ", ".join(acts) or "(none)")
    if "refine" not in acts:
        log.problem("the conversation did not hand over to the refine loop (the page would start it from 'Something feels off')")
    prop = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/refine", json={"concern": "something feels off with the chorus"})["job_id"], "listened and thought")
    log.step("Frank says", prop["message"])
    for d in prop["directions"]:
        log.step(f"direction: {d['title']}", " ".join(d["changes"]))
    if not 2 <= len(prop["directions"]) <= 3:
        log.problem("not two or three directions")
    pv = job(h, log, e2e.call(h, "POST", f"/projects/{pid}/refine/{prop['proposal_id']}/preview/0")["job_id"], "preview of the first")
    log.step("preview", f"new {bool(pv.get('preview_url'))}, as it is now {bool(pv.get('before_url'))}")
    ch = e2e.call(h, "POST", f"/projects/{pid}/refine/{prop['proposal_id']}/choose/0")
    log.step("used it", ch["message"])
    made = job(h, log, ch["job_id"], "new version")
    log.step("what changed", " ".join(made.get("changes") or []))
    back = e2e.call(h, "POST", f"/projects/{pid}/beat/conversation", json={"message": "actually give me the first version back", "beat_state": {}, "history": []})
    log.step("person: 'give me the first version back'", back["message"])
    if not any(a["type"] == "restore_version" for a in back.get("actions", [])):
        log.problem("the earlier version was not found")


DEMOS = {1: ("Demo 1: a feeling and lyrics become a sung, finished song", demo1),
         2: ("Demo 2: a phone hum becomes a produced song", demo2),
         3: ("Demo 3: something feels wrong", demo3)}


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    wanted = [int(x) for x in sys.argv[1:]] or [1, 2, 3]
    failed = 0
    for n in wanted:
        title, fn = DEMOS[n]
        log = Log(title)
        print(f"\n== {title}", flush=True)
        uid, h = e2e.login()
        try:
            fn(h, log)
        except Exception as exc:  # noqa: BLE001
            log.problem(f"stopped: {exc}")
            traceback.print_exc()
        finally:
            e2e.c.delete(f"{e2e.SB}/auth/v1/admin/users/{uid}", headers=e2e.ADMIN)
        failed += bool(log.problems)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        body = [f"# {title}", "", f"Run {stamp} against {e2e.API} with a fresh account (deleted afterwards).",
                f"Total {time.time() - log.t0:.0f} s. Result: {'PASS' if not log.problems else 'PROBLEMS'}", "", "## Steps", *log.lines,
                "", "## Problems", *([f"- {p}" for p in log.problems] or ["- none"]), "",
                "Audio is synthetic (a generated sung line); the founder's own run with a real voice is still to come."]
        (DOCS / f"{datetime.date.today()}-demo{n}.md").write_text("\n".join(body) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
