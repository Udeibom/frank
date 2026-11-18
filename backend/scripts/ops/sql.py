"""Run SQL (a file or a string) on the live database through the Supabase Management API.
Needs SUPABASE_ACCESS_TOKEN in the environment (a personal access token; never stored in the repo)."""
import json, os, pathlib, sys
import httpx
REF = "xbaimepgehkqdpozmpfi"
arg = sys.argv[1]
sql = pathlib.Path(arg).read_text() if pathlib.Path(arg).exists() else arg
r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
               headers={"Authorization": f"Bearer {os.environ['SUPABASE_ACCESS_TOKEN']}"}, json={"query": sql}, timeout=60)
print(r.status_code, r.text[:800])
