# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Throwaway probe for Discovery-Milestone: can this runner fetch a half-megabyte
# commit-pinned dataset under run_nondet, hash it, and count its records with
# validators agreeing on the bytes? Also: a Zenodo record file.

import genlayer as gl
from genlayer.types import *

import hashlib
import json


def _stats(url: str) -> dict:
    try:
        r = gl.nondet.web.get(url)
        body = r.body if r.body is not None else b""
        status = int(r.status)
    except Exception as e:
        return {"error": str(e)[:200]}
    segments = body.split(b'"')
    newlines = 0
    for i in range(0, len(segments), 2):
        newlines += segments[i].count(b"\n")
    header = body.split(b"\n", 1)[0][:200].decode("utf-8", "replace")
    return {
        "status": status,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "records_outside_quotes": newlines,
        "header": header,
    }


class Probe(gl.contract.Contract):
    last: str

    def __init__(self):
        self.last = ""

    @gl.public.write
    def fetch_stats(self, url: str) -> str:
        def leader():
            return json.dumps(_stats(url), sort_keys=True)

        def validator(res):
            if not isinstance(res, gl.vm.Return):
                return False
            mine = _stats(url)
            theirs = json.loads(str(res.calldata))
            return mine.get("sha256") == theirs.get("sha256") \
                and mine.get("status") == theirs.get("status") \
                and mine.get("records_outside_quotes") == theirs.get("records_outside_quotes")

        out = gl.vm.run_nondet(leader, validator)
        self.last = str(out)
        return self.last

    @gl.public.view
    def get_last(self) -> str:
        return self.last
