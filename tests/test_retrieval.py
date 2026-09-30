"""Offline tests with fixed embeddings; these do not measure model quality."""

import pytest

from backend.config import EmbeddingConfig, IngestionConfig
from backend.embeddings import SentenceTransformerEmbedder, passage_text
from backend.evaluation import evaluate_cases
from backend.indexing import read_manifest, rebuild_index
from backend.models import DocumentChunk, SearchResult
from backend.retrieval import Retriever
from backend.vector_store import ChromaStore


class FakeEmbedder:
    config = EmbeddingConfig(model_name="fake-test-only")

    def embed_passages(self, texts):
        return [[1.0, 0.0] if "Python" in text else [0.0, 1.0] for text in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


class FakeCollection:
    def __init__(self):
        self.rows = []

    def count(self):
        return len(self.rows)

    def add(self, ids, documents, embeddings, metadatas):
        self.rows.extend(zip(ids, documents, embeddings, metadatas, strict=True))

    def query(self, query_embeddings, n_results, include):
        query = query_embeddings[0]
        ranked = sorted(self.rows, key=lambda row: 1 - sum(a * b for a, b in zip(query, row[2])))[:n_results]
        return {
            "ids": [[row[0] for row in ranked]],
            "documents": [[row[1] for row in ranked]],
            "metadatas": [[row[3] for row in ranked]],
            "distances": [[1 - sum(a * b for a, b in zip(query, row[2])) for row in ranked]],
        }


class FakeStore:
    add = staticmethod(ChromaStore.add)
    query = staticmethod(ChromaStore.query)

    def __init__(self):
        self.collections = {}

    def create(self, name):
        collection = FakeCollection()
        self.collections[name] = collection
        return collection

    def get(self, name):
        return self.collections[name]

    def delete(self, name):
        del self.collections[name]


@pytest.fixture
def indexed(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "python.md").write_text("# Python project\nData processing.", encoding="utf-8")
    (data / "other.txt").write_text("Other project", encoding="utf-8")
    db = tmp_path / "db"
    store = FakeStore()
    embedder = FakeEmbedder()
    rebuild_index(IngestionConfig(data_dir=data), db, embedder, store=store)
    return data, db, store, embedder


def test_retrieval_ranking_top_k_and_metadata(indexed):
    _, db, store, embedder = indexed
    retriever = Retriever(db, store=store, embedder=embedder)
    results = retriever.search("Python experience", top_k=1)
    assert len(results) == 1
    assert results[0].chunk.source == "python.md"
    assert results[0].chunk.title == "Python project"
    assert results[0].chunk.section == "Python project"
    assert results[0].chunk.chunk_index == 0
    assert results[0].distance == 0.0
    assert len(retriever.search("Python", top_k=100)) == 2


@pytest.mark.parametrize("question,top_k", [(" ", 5), ("Python", 0), ("Python", -1)])
def test_invalid_search(indexed, question, top_k):
    _, db, store, embedder = indexed
    with pytest.raises(ValueError):
        Retriever(db, store=store, embedder=embedder).search(question, top_k)


def test_missing_index_does_not_create_database(tmp_path):
    db = tmp_path / "missing"
    with pytest.raises(ValueError, match="No index"):
        Retriever(db)
    assert not db.exists()


def test_rebuild_removes_deleted_and_changed_content(indexed):
    data, db, store, embedder = indexed
    (data / "python.md").unlink()
    (data / "other.txt").write_text("Updated Python evidence", encoding="utf-8")
    rebuild_index(IngestionConfig(data_dir=data), db, embedder, store=store)
    results = Retriever(db, store=store, embedder=embedder).search("Python")
    assert len(results) == 1
    assert results[0].chunk.source == "other.txt"
    assert results[0].chunk.text == "Updated Python evidence"


def test_empty_rebuild_publishes_empty_index_without_loading_model(indexed):
    data, db, store, embedder = indexed
    for path in data.iterdir():
        path.unlink()
    rebuild_index(IngestionConfig(data_dir=data), db, embedder, store=store)
    def unexpected_query(text):
        pytest.fail("Empty index should not invoke embeddings")
    embedder.embed_query = unexpected_query
    assert Retriever(db, store=store, embedder=embedder).search("Anything") == []


def test_failed_rebuild_preserves_active_index(indexed):
    data, db, store, embedder = indexed
    original = read_manifest(db)
    def fail(texts):
        raise RuntimeError("Simulated embedding failure")
    embedder.embed_passages = fail
    with pytest.raises(RuntimeError, match="Simulated"):
        rebuild_index(IngestionConfig(data_dir=data), db, embedder, store=store)
    assert read_manifest(db) == original
    assert len(store.collections) == 1
    assert len(Retriever(db, store=store, embedder=embedder).search("Python")) == 2


def test_embedding_configuration_mismatch_is_rejected(indexed):
    _, db, store, _ = indexed
    different = FakeEmbedder()
    different.config = EmbeddingConfig(model_name="different-test-model")
    with pytest.raises(ValueError, match="differs"):
        Retriever(db, store=store, embedder=different)


def test_passage_includes_heading_context():
    chunk = DocumentChunk("id", "project.md", "Project", "Project > Tools", 2, "Python")
    assert passage_text(chunk) == "Project\nProject > Tools\nPython"


def test_embedding_prefixes_and_normalization_without_model_download():
    class Array:
        def tolist(self):
            return [[1.0, 0.0]]
    class Model:
        max_seq_length = 512
        seen = []
        def tokenizer(self, texts, **kwargs):
            self.seen.append(texts)
            assert kwargs["truncation"] is False
            return {"input_ids": [[1, 2, 3] for _ in texts]}
        def encode(self, texts, **kwargs):
            assert kwargs["normalize_embeddings"] is True
            return Array()
    embedder = SentenceTransformerEmbedder()
    embedder._model = Model()
    assert embedder.embed_query("Kokemus?") == [1.0, 0.0]
    assert embedder.embed_passages(["Evidence"]) == [[1.0, 0.0]]
    assert embedder._model.seen == [["query: Kokemus?"], ["passage: Evidence"]]


def test_overlong_embedding_input_is_rejected_without_truncation():
    class Model:
        max_seq_length = 2
        def tokenizer(self, texts, **kwargs):
            return {"input_ids": [[1, 2, 3]]}
        def encode(self, *args, **kwargs):
            pytest.fail("Must reject before encoding")
    embedder = SentenceTransformerEmbedder()
    embedder._model = Model()
    with pytest.raises(ValueError, match="exceeds 2 tokens"):
        embedder.embed_query("Long question")


def test_evaluation_denominators_and_missing_evidence():
    chunk = DocumentChunk("id", "one.md", "One", None, 0, "Partial evidence")
    class Search:
        def search(self, question, top_k):
            assert question in {"Known?", "Unknown?"}
            return [SearchResult(chunk, 0.2)]
    report = evaluate_cases([
        {"id": "a", "question": "Known?", "answer_mode": "answer",
         "expected_sources": ["one.md", "two.md"],
         "evidence": [{"source": "one.md", "quote": "Full missing evidence"}]},
        {"id": "b", "question": "Unknown?", "answer_mode": "abstain",
         "expected_sources": [], "evidence": []},
    ], Search())
    assert report["mean_source_recall"] == 0.5
    assert report["all_sources_found_rate"] == 0.0
    assert report["mean_literal_evidence_recall"] == 0.0
    assert report["unscored_cases"] == 1
    assert report["cases"][1]["source_recall"] is None


def test_chroma_real_persistence_with_fixed_vectors(tmp_path):
    """Optional real Chroma integration; no model or network required."""
    pytest.importorskip("chromadb")
    store = ChromaStore(tmp_path / "chroma")
    collection = store.create("integration-test")
    chunks = [DocumentChunk("a", "a.md", "A", None, 0, "Python"),
              DocumentChunk("b", "b.md", "B", "Tools", 0, "SQL")]
    store.add(collection, chunks, [[1.0, 0.0], [0.0, 1.0]])
    reopened = ChromaStore(tmp_path / "chroma")
    results = reopened.query(reopened.get("integration-test"), [1.0, 0.0], 10)
    assert [result.chunk for result in results] == chunks
    assert results[0].distance == pytest.approx(0.0, abs=1e-5)
    assert results[1].distance == pytest.approx(1.0, abs=1e-5)
