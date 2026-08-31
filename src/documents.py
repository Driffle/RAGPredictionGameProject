"""Turn calendar rows and catalog products into retrieval documents.

Persists a gzip JSONL corpus. TF-IDF is optional (`FLOORBRIEF_TRAIN_TFIDF`)
because the website uses keyword retrieve, not the 180MB joblib index.
"""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

from src.paths import DATA_PROCESSED

RAG_DIR = DATA_PROCESSED / "rag"
CORPUS_PATH = RAG_DIR / "corpus.jsonl"
INDEX_PATH = RAG_DIR / "tfidf_index.joblib"
META_PATH = RAG_DIR / "meta.json"


def event_document(row: dict) -> dict:
    text = "\n".join(
        [
            f"Industry event: {row.get('event', '')}",
            f"Dates: {row.get('start_date', '')} to {row.get('end_date', '')}",
            f"Category: {row.get('category', '')}",
            f"Event type: {row.get('event_type', '')}",
            f"Related games / franchises: {row.get('related_game', '')}",
            f"Status: {row.get('status', '')}",
            f"Attendance: {row.get('attendance_mode', '')}",
            f"Scope / location: {row.get('scope', '')} / {row.get('location', '')}",
            f"Source: {row.get('source', '')} {row.get('official_source', '')} {row.get('wikipedia_url', '')}",
            f"Entry date: {row.get('entry_date', '')}",
            f"Last checked: {row.get('last_checked', '')}",
        ]
    )
    return {
        "id": f"event:{row.get('event', '')}:{row.get('start_date', '')}",
        "kind": "event",
        "title": row.get("event", ""),
        "text": text,
        "metadata": {
            "start_date": row.get("start_date", ""),
            "end_date": row.get("end_date", ""),
            "related_game": row.get("related_game", ""),
            "status": row.get("status", ""),
            "attendance_mode": row.get("attendance_mode", ""),
            "scope": row.get("scope", ""),
            "location": row.get("location", ""),
            "source": row.get("source", ""),
            "entry_date": row.get("entry_date", ""),
            "last_checked": row.get("last_checked", ""),
        },
    }


def adaptation_document(row: dict) -> dict:
    text = "\n".join(
        [
            f"Media adaptation: {row.get('ip_adaptation', '')}",
            f"Related game: {row.get('related_game', '')}",
            f"Medium: {row.get('medium', '')}",
            f"Distributor: {row.get('distributor', '')}",
            f"Dates: {row.get('start_date', '')} to {row.get('end_date', '')}",
            f"Date status: {row.get('date_status', '')}",
            f"Entertainment format: {row.get('format') or row.get('medium', '')}",
            f"Release channel: {row.get('release_channel', '')}",
            f"Source: {row.get('source', '')} {row.get('wikipedia_url', '')}",
            f"Entry date: {row.get('entry_date', '')}",
            f"Last checked: {row.get('last_checked', '')}",
        ]
    )
    return {
        "id": f"adaptation:{row.get('ip_adaptation', '')}:{row.get('start_date', '')}",
        "kind": "adaptation",
        "title": row.get("ip_adaptation", ""),
        "text": text,
        "metadata": {
            "related_game": row.get("related_game", ""),
            "medium": row.get("medium", ""),
            "start_date": row.get("start_date", ""),
            "format": row.get("format") or row.get("medium", ""),
            "release_channel": row.get("release_channel", ""),
            "source": row.get("source", ""),
            "entry_date": row.get("entry_date", ""),
            "last_checked": row.get("last_checked", ""),
        },
    }


def product_document(row: dict) -> dict:
    release = row.get("release_date") or "unknown"
    text = "\n".join(
        [
            f"Game product: {row.get('canonical_title') or row.get('product_title', '')}",
            f"Full title: {row.get('product_title', '')}",
            f"Type: {row.get('product_type', '')}",
            f"Platform: {row.get('platform', '')}",
            f"Release date: {release}",
            f"Confirmation: {row.get('confirmation') or row.get('status', '')}",
            f"SKU: {row.get('product_sku', '')}",
            f"Status: {row.get('status', '')}",
            f"Source: {row.get('source', '')} {row.get('official_source', '')}",
            f"Entry date: {row.get('entry_date', '')}",
            f"Last checked: {row.get('last_checked', '')}",
        ]
    )
    return {
        "id": f"product:{row.get('product_id', '') or row.get('canonical_title', '')}",
        "kind": "product",
        "title": row.get("canonical_title") or row.get("product_title", ""),
        "text": text,
        "metadata": {
            "platform": row.get("platform", ""),
            "release_date": row.get("release_date", ""),
            "product_type": row.get("product_type", ""),
            "source": row.get("source", ""),
            "entry_date": row.get("entry_date", ""),
            "last_checked": row.get("last_checked", ""),
            "confirmation": row.get("confirmation") or row.get("status", ""),
        },
    }


def keyword_retrieve(documents: list[dict], query: str, *, limit: int = 8) -> list[tuple[float, dict]]:
    """Tiny token-overlap retriever used as a fallback when the TF-IDF index is absent."""
    tokens = {token for token in query.lower().split() if len(token) > 2}
    if not tokens:
        return []
    scored: list[tuple[float, dict]] = []
    for doc in documents:
        haystack = f"{doc.get('title', '')} {doc.get('text', '')}".lower()
        overlap = sum(1 for token in tokens if token in haystack)
        if overlap:
            scored.append((overlap / len(tokens), doc))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:limit]


def build_retrieval_corpus(
    events: list[dict],
    adaptations: list[dict],
    products: list[dict],
    plans: list[dict] | None = None,
) -> list[dict]:
    """Event, adaptation, product, and promotion-plan chunks for RAG."""
    from src.promote import promotion_document

    documents = (
        [event_document(row) for row in events]
        + [adaptation_document(row) for row in adaptations]
        + [product_document(row) for row in products]
    )
    if plans:
        documents.extend(promotion_document(plan) for plan in plans)
    return documents


def persist_corpus(documents: list[dict], path: Path | None = None) -> Path:
    target = path or CORPUS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    gz = target if str(target).endswith(".gz") else Path(str(target) + ".gz")
    plain = Path(str(gz)[:-3]) if str(gz).endswith(".gz") else target
    with gzip.open(gz, "wt", encoding="utf-8") as handle:
        for doc in documents:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")
    if plain.exists() and plain != gz:
        plain.unlink()
    return gz


def retrain_rag_index(
    events: list[dict],
    adaptations: list[dict],
    products: list[dict],
    plans: list[dict] | None = None,
) -> dict:
    """Rebuild the gzip JSONL corpus. TF-IDF is optional; the app uses keyword retrieve."""
    import os

    documents = build_retrieval_corpus(events, adaptations, products, plans)
    corpus_path = persist_corpus(documents)
    kinds = {
        kind: sum(1 for doc in documents if doc.get("kind") == kind)
        for kind in sorted({doc.get("kind") or "other" for doc in documents})
    }
    meta = {
        "document_count": len(documents),
        "trained": bool(documents),
        "as_of": date.today().isoformat(),
        "corpus_path": str(corpus_path),
        "retriever": "keyword",
        "kinds": kinds,
    }
    if documents and os.environ.get("FLOORBRIEF_TRAIN_TFIDF"):
        from joblib import dump
        from sklearn.feature_extraction.text import TfidfVectorizer

        texts = [f"{doc.get('title', '')}\n{doc.get('text', '')}" for doc in documents]
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            max_features=50000,
        )
        matrix = vectorizer.fit_transform(texts)
        dump({"vectorizer": vectorizer, "matrix": matrix, "documents": documents}, INDEX_PATH)
        meta["index_path"] = str(INDEX_PATH)
        meta["retriever"] = "tfidf"
    elif INDEX_PATH.exists():
        INDEX_PATH.unlink()
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_rag_meta() -> dict:
    if not META_PATH.exists():
        return {}
    return json.loads(META_PATH.read_text(encoding="utf-8"))


def retrieve(query: str, *, limit: int = 8) -> list[tuple[float, dict]]:
    """Retrieve against the persisted TF-IDF index, falling back to keyword overlap."""
    if INDEX_PATH.exists():
        try:
            from joblib import load
            from sklearn.metrics.pairwise import cosine_similarity

            payload = load(INDEX_PATH)
            vectorizer = payload["vectorizer"]
            matrix = payload["matrix"]
            documents = payload["documents"]
            query_vec = vectorizer.transform([query])
            scores = cosine_similarity(query_vec, matrix).ravel()
            ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
            hits: list[tuple[float, dict]] = []
            for index, score in ranked[:limit]:
                if score <= 0:
                    continue
                hits.append((float(score), documents[index]))
            if hits:
                return hits
        except Exception:
            pass
    gz = Path(str(CORPUS_PATH) + ".gz")
    if gz.exists() or CORPUS_PATH.exists():
        if gz.exists():
            with gzip.open(gz, "rt", encoding="utf-8") as handle:
                documents = [json.loads(line) for line in handle if line.strip()]
        else:
            documents = [
                json.loads(line)
                for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        return keyword_retrieve(documents, query, limit=limit)
    return []


def upcoming_products(catalog: list[dict], *, after: date | None = None) -> list[dict]:
    cutoff = after or date.today()
    rows = [
        row
        for row in catalog
        if isinstance(row.get("release_date_parsed"), date) and row["release_date_parsed"] >= cutoff
    ]
    rows.sort(key=lambda row: row["release_date_parsed"])
    return rows
