import os
import shutil
from typing import List, Dict

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "2"

import chromadb
from sentence_transformers import SentenceTransformer


class RAGEngine:
    """RAG engine using ChromaDB for vector storage and local Sentence Transformers for embeddings."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.collection_name = "telepsicologia_kb"
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.reset_due_to_mismatch = False
        self._embeddings_cache = {}
        self._search_cache = {}
        self._init_chroma()
        self._check_dimension_compatibility()

    def _init_chroma(self):
        """Initialize ChromaDB client and collection with auto-recovery on index corruption."""
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            if any(term in str(e).lower() for term in ["compaction", "hnsw", "segment", "log", "corrupt", "failed to apply"]):
                self._wipe_and_reinit()
            else:
                # Intento de recuperacion generica
                self._wipe_and_reinit()

    def _wipe_and_reinit(self):
        """Intenta limpiar la coleccion o recrearla si el indice HNSW se corrompio."""
        try:
            if hasattr(self, "chroma_client"):
                try:
                    self.chroma_client.delete_collection(self.collection_name)
                except Exception:
                    pass
            self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self.reset_due_to_mismatch = True
            self._search_cache.clear()
        except Exception:
            pass

    def _check_dimension_compatibility(self):
        """Verifica la compatibilidad de dimensiones en ChromaDB."""
        try:
            if not hasattr(self, "collection") or self.collection.count() == 0:
                return
            expected_dim = self.model.get_sentence_embedding_dimension()
            sample = self.collection.get(limit=1, include=["embeddings"])
            stored = sample.get("embeddings")
            if stored is not None and len(stored) > 0 and len(stored[0]) != expected_dim:
                self.reset_collection()
                self.reset_due_to_mismatch = True
        except Exception:
            # Manejo silencioso en caso de indice en proceso de compactacion
            pass

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local Sentence Transformers model with caching."""
        results = []
        texts_to_compute = []
        compute_indices = []

        for idx, text in enumerate(texts):
            clean_text = text.strip()
            if clean_text in self._embeddings_cache:
                results.append(self._embeddings_cache[clean_text])
            else:
                results.append(None)
                texts_to_compute.append(clean_text)
                compute_indices.append(idx)

        if texts_to_compute:
            encoded = self.model.encode(texts_to_compute, show_progress_bar=False).tolist()
            for text, emb, orig_idx in zip(texts_to_compute, encoded, compute_indices):
                self._embeddings_cache[text] = emb
                results[orig_idx] = emb

        return results

    def index_chunks(self, chunks: List[Dict]) -> int:
        """Index text chunks into ChromaDB. Returns number of chunks indexed."""
        if not chunks:
            return 0

        self._search_cache.clear()
        batch_size = 100
        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            ids = [c["id"] for c in batch]
            metadatas = [c.get("metadata", {}) for c in batch]

            embeddings = self._get_embeddings(texts)

            try:
                self.collection.upsert(
                    ids=ids,
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
            except Exception as e:
                err_msg = str(e).lower()
                if "dimension" in err_msg or "compaction" in err_msg or "hnsw" in err_msg or "segment" in err_msg:
                    self.reset_collection()
                    self.reset_due_to_mismatch = True
                    try:
                        self.collection.upsert(
                            ids=ids,
                            documents=texts,
                            embeddings=embeddings,
                            metadatas=metadatas,
                        )
                    except Exception:
                        pass
                else:
                    raise
            total_indexed += len(batch)

        return total_indexed

    def search(self, query: str, n_results: int = 3) -> List[Dict]:
        """Search for relevant chunks given a query, with caching for fast retrieval."""
        clean_query = query.strip().lower()
        cache_key = f"{clean_query}_{n_results}"

        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        try:
            if not hasattr(self, "collection") or self.collection.count() == 0:
                return []

            query_embedding = self._get_embeddings([query])[0]

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, self.collection.count()),
            )

            search_results = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    search_results.append({
                        "text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })

            self._search_cache[cache_key] = search_results
            return search_results
        except Exception as e:
            if any(term in str(e).lower() for term in ["compaction", "hnsw", "segment", "log", "corrupt"]):
                self._wipe_and_reinit()
                return []
            return []

    def get_context_for_query(self, query: str, n_results: int = 3) -> str:
        """Get formatted context string from RAG for injection into the prompt."""
        try:
            results = self.search(query, n_results)

            if not results:
                return ""

            context_parts = ["=== BASE DE CONOCIMIENTO DE SALUD MENTAL ===\n"]
            for i, r in enumerate(results, 1):
                context_parts.append(f"[Fuente {i}]:\n{r['text']}\n")

            return "\n".join(context_parts)
        except Exception:
            return ""

    def get_stats(self) -> Dict:
        """Return statistics about the knowledge base."""
        try:
            count = self.collection.count() if hasattr(self, "collection") else 0
        except Exception:
            count = 0
        return {
            "total_chunks": count,
            "collection_name": self.collection_name,
            "persist_dir": self.persist_dir,
        }

    def reset_collection(self):
        """Delete and recreate the collection."""
        try:
            self.chroma_client.delete_collection(self.collection_name)
        except Exception:
            try:
                # Eliminar todos los registros de la coleccion si la coleccion no puede borrarse directamente
                all_ids = self.collection.get()["ids"]
                if all_ids:
                    self.collection.delete(ids=all_ids)
            except Exception:
                pass
        self._init_chroma()
