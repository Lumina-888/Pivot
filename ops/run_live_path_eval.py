#!/usr/bin/env python3
"""Live Golden Set evaluation of the default LlamaIndex retrieval path.

Opt-in only: talks to the SiliconFlow API through the Muse connector
surrogate, so no API key ever appears in this process. The embedder is
the production HttpQueryEmbedder (BAAI/bge-m3) and the optional
reranker is the production HttpBgeReranker (BAAI/bge-reranker-v2-m3),
wired into the same default-path assembly the controlled harness uses.

Corpus embeddings are cached on disk by text hash under the cache dir
so re-runs do not re-bill the corpus. Query embeddings and rerank
calls are always live. Prints a JSON summary. Does not mark GATE-P0
verified and does not freeze TBD-P0 values: policy sizes are the
test values of the controlled harness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "tests" / "integration" / "pipeline"
API_SRC = ROOT / "api" / "src"
AUTH_BIN = Path("/opt/muse/skills/custom-connector-setup/bin")
DEFAULT_CACHE = Path.home() / "workspace" / "pivot-maintenance" / "live-eval-cache"

HOST = "api.siliconflow.cn"
EMBED_ENDPOINT = f"https://{HOST}/v1/embeddings"
RERANK_ENDPOINT = f"https://{HOST}/v1/rerank"
EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
DIMENSION = 1024
BATCH = 32


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


class SurrogateJsonHttpClient:
    """JsonHttpClient that lets the connector surrogate carry the key.

    The Authorization header supplied by the production providers is
    dropped; dynamic_credentials attaches the surrogate instead and the
    runtime swaps in the real key on egress to the registered host.
    """

    def __init__(self) -> None:
        sys.path.insert(0, str(AUTH_BIN))
        from dynamic_credentials import add_surrogate_to_request, read_json_response

        self._add_surrogate = add_surrogate_to_request
        self._read_json = read_json_response
        self.usage = {"embedding_tokens": 0, "rerank_tokens": 0, "calls": 0}

    def post_json(self, url, payload, headers, timeout=None):
        from pivot.retrieval.providers import InvalidJsonResponseError, JsonHttpError

        request = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), method="POST"
        )
        request.add_header("Content-Type", "application/json")
        self._add_surrogate(request, "custom.siliconflow", allowed_hosts=[HOST])
        try:
            with urllib.request.build_opener(_NoRedirect()).open(
                request, timeout=timeout or 120
            ) as response:
                parsed = self._read_json(response)
        except urllib.error.HTTPError as exc:
            raise JsonHttpError("http request failed", status=exc.code) from exc
        except TimeoutError as exc:
            raise JsonHttpError("http request timed out", timeout=True) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise JsonHttpError("http transport failed") from exc
        if not isinstance(parsed, dict):
            raise InvalidJsonResponseError("http response is not an object")
        self.usage["calls"] += 1
        usage = parsed.get("usage")
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
            self.usage["embedding_tokens"] += usage["total_tokens"]
        meta = parsed.get("meta")
        if isinstance(meta, dict) and isinstance(meta.get("tokens"), dict):
            tokens = meta["tokens"].get("input_tokens")
            if isinstance(tokens, int):
                self.usage["rerank_tokens"] += tokens
        return parsed


class CachingEmbedder:
    """QueryEmbedder wrapper caching vectors by text hash on disk."""

    def __init__(self, inner, cache_path: Path) -> None:
        self._inner = inner
        self._path = cache_path
        self._cache: dict[str, list[float]] = {}
        if cache_path.exists():
            self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self.hits = 0
        self.misses = 0

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._cache), encoding="utf-8")
        tmp.replace(self._path)

    def embed(self, texts):
        keys = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts]
        missing = [key for key in keys if key not in self._cache]
        self.hits += len(keys) - len(missing)
        self.misses += len(missing)
        by_key = {key: text for key, text in zip(keys, texts, strict=True)}
        for start in range(0, len(missing), BATCH):
            batch_keys = missing[start : start + BATCH]
            vectors = self._inner.embed([by_key[key] for key in batch_keys])
            for key, vector in zip(batch_keys, vectors, strict=True):
                self._cache[key] = vector
            self._save()
        return [self._cache[key] for key in keys]


def main() -> int:
    sys.path[:0] = [str(PIPELINE), str(API_SRC)]
    try:
        from default_path_eval import evaluate_default_path
        from golden_set import load_dataset, load_enterprise_dataset
        from pivot.retrieval.llama_embeddings import PivotEmbedding
        from pivot.retrieval.policy import RetrievalPolicy
        from pivot.retrieval.providers import HttpBgeReranker, HttpQueryEmbedder
    except ImportError as exc:
        print(f"missing dependency: {exc}", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser()
    parser.add_argument("--enterprise", action="store_true")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--limit-cases", type=int, default=None)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    dataset = load_enterprise_dataset() if args.enterprise else load_dataset()
    if args.limit_cases is not None:
        dataset = {**dataset, "cases": dataset["cases"][: args.limit_cases]}

    client = SurrogateJsonHttpClient()
    embedder = CachingEmbedder(
        HttpQueryEmbedder(
            client,
            endpoint=EMBED_ENDPOINT,
            model=EMBED_MODEL,
            api_key="surrogate-managed",
            timeout_seconds=120,
            expected_dimension=DIMENSION,
        ),
        args.cache_dir / "bge-m3-vectors.json",
    )
    embed_model = PivotEmbedding(
        embedder, model_name=EMBED_MODEL, dimension=DIMENSION
    )
    reranker = None
    if args.rerank:
        reranker = HttpBgeReranker(
            client,
            endpoint=RERANK_ENDPOINT,
            model=RERANK_MODEL,
            api_key="surrogate-managed",
            timeout_seconds=120,
        )
    policy = RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)
    report = evaluate_default_path(
        dataset,
        policy=policy,
        embed_model=embed_model,
        vector_size=DIMENSION,
        reranker=reranker,
    )
    summary = {
        "dataset_version": report["dataset_version"],
        "rerank": bool(args.rerank),
        "case_count": report["case_count"],
        "passed_count": report["passed_count"],
        "labeled_hit_rate": report["labeled_hit_rate"],
        "forbidden_leaks": report["forbidden_leaks"],
        "strata": report["strata"],
        "usage": client.usage,
        "cache": {"hits": embedder.hits, "misses": embedder.misses},
    }
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"summary": summary, "report": report}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        "GATE-P0-002 unverified: live provider, test policy values",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
