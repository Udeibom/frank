"""Call frank-hands /sing directly with gradio_client and print the raw result or error (debugging aid)."""
import json
import os
import sys
import time

from gradio_client import Client

c = Client("Udeibom/frank-hands", hf_token=os.environ["SPACES_TOKEN"], verbose=False)
notes = [{"note": n, "start": i * 1.0, "duration": 0.9} for i, n in enumerate([60, 62, 64, 65])]
payload = json.dumps({"notes": notes, "phonemes": [["l", "ah"]] * 4, "bpm": 90, "lead_s": 0.0})
t = time.time()
try:
    job = c.submit(payload, api_name="/sing")
    while not job.done() and time.time() - t < 600:
        st = job.status()
        print(round(time.time() - t), st.code, getattr(st, "progress_data", None), flush=True)
        time.sleep(15)
    print("result", job.result(timeout=5))
except Exception as e:  # noqa: BLE001
    print("ERROR", type(e).__name__, repr(e)[:2000])
sys.exit(0)
