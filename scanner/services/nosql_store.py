"""
NoSQL storage layer for DefexVision.

Rich image-analysis metadata (preprocessing telemetry, detection JSON,
confidence histograms, stage timings) is stored as documents so it can be
queried flexibly.

Uses MongoDB when available (via pymongo). If MongoDB is not running, it
gracefully falls back to a local JSON-file document store so the app keeps
working in development / preview.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from threading import Lock

from django.conf import settings


class NoSqlStore:
    """Thin document store with an identical API whether backed by Mongo or JSON."""

    def __init__(self, uri: str | None = None, db_name: str | None = None):
        cfg = getattr(settings, "DEFEXVISION", {})
        self.uri = uri or cfg.get("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = db_name or cfg.get("MONGO_DB", "defexvision")
        self._client = None
        self._lock = Lock()
        self._fallback_dir = os.path.join(
            os.path.dirname(__file__), "nosql_store_data"
        )
        self.backend = "json"
        self._connect()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def _connect(self):
        try:
            from pymongo import MongoClient

            client = MongoClient(self.uri, serverSelectionTimeoutMS=1500)
            # forces a connection attempt
            client.admin.command("ping")
            self._client = client
            self.backend = "mongodb"
        except Exception:
            self._client = None
            self.backend = "json"
            os.makedirs(self._fallback_dir, exist_ok=True)

    @property
    def collection(self):
        if self._client is not None:
            return self._client[self.db_name]["analysis"]
        return None

    # ------------------------------------------------------------------
    # JSON fallback helpers
    # ------------------------------------------------------------------
    def _json_path(self, doc_id: str) -> str:
        return os.path.join(self._fallback_dir, f"{doc_id}.json")

    def _json_insert(self, document: dict) -> str:
        doc_id = document.get("_id") or uuid.uuid4().hex
        document["_id"] = doc_id
        path = self._json_path(doc_id)
        with self._lock:
            with open(path, "w") as f:
                json.dump(document, f, indent=2, default=str)
        return doc_id

    def _json_find(self, query: dict | None = None, limit: int = 50):
        query = query or {}
        results = []
        with self._lock:
            if not os.path.isdir(self._fallback_dir):
                return results
            for name in sorted(os.listdir(self._fallback_dir), reverse=True):
                if not name.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(self._fallback_dir, name)) as f:
                        doc = json.load(f)
                except Exception:
                    continue
                if all(doc.get(k) == v for k, v in query.items()):
                    results.append(doc)
                if len(results) >= limit:
                    break
        return results

    def _json_count(self, query: dict | None = None) -> int:
        return len(self._json_find(query, limit=100000))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def insert_analysis(self, record_id, image_name, pipeline, detections,
                        summary, extra=None) -> str:
        """Persist one inspection analysis document."""
        document = {
            "record_id": str(record_id),
            "image_name": image_name,
            "pipeline": pipeline,
            "detections": detections,
            "summary": summary,
            "extra": extra or {},
            "created_at": time.time(),
            "backend": self.backend,
        }
        if self.collection is not None:
            result = self.collection.insert_one(document)
            return str(result.inserted_id)
        return self._json_insert(document)

    def get_analysis(self, record_id) -> dict | None:
        query = {"record_id": str(record_id)}
        if self.collection is not None:
            doc = self.collection.find_one(query)
            if doc:
                doc["_id"] = str(doc["_id"])
                return doc
            return None
        docs = self._json_find(query, limit=1)
        return docs[0] if docs else None

    def list_analyses(self, limit: int = 50) -> list:
        if self.collection is not None:
            docs = self.collection.find().sort("created_at", -1).limit(limit)
            out = []
            for d in docs:
                d["_id"] = str(d["_id"])
                out.append(d)
            return out
        return self._json_find(limit=limit)

    def count_analyses(self) -> int:
        if self.collection is not None:
            return self.collection.count_documents({})
        return self._json_count()

    def clear(self):
        if self.collection is not None:
            self.collection.delete_many({})
        else:
            with self._lock:
                for name in os.listdir(self._fallback_dir):
                    if name.endswith(".json"):
                        os.remove(os.path.join(self._fallback_dir, name))

    def ping(self) -> dict:
        return {"backend": self.backend}


# module-level singleton (reused across requests)
_store: NoSqlStore | None = None


def get_store() -> NoSqlStore:
    global _store
    if _store is None:
        _store = NoSqlStore()
    return _store
