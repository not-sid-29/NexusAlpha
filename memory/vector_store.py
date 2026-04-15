import logging
from typing import List, Dict, Any
try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger("nexus.memory.vector")

class VectorStore:
    """
    Manages semantic memory using ChromaDB.
    Enforces collection-level multi-tenant isolation.
    """
    def __init__(self, persist_directory: str = "nexus_vectors"):
        if chromadb is None:
            logger.warning("ChromaDB not installed. Vector storage will be disabled.")
            self.client = None
            return
            
        self.client = chromadb.PersistentClient(path=persist_directory)
        logger.info(f"VectorStore initialized at {persist_directory}")

    def _get_user_collection(self, user_id: str):
        if not self.client: return None
        collection_name = f"user_{user_id.replace('-', '_')}"
        return self.client.get_or_create_collection(name=collection_name)

    async def add_interaction(self, user_id: str, text: str, metadata: Dict[str, Any], doc_id: str):
        """
        Embed and store a session turn or summary.
        """
        collection = self._get_user_collection(user_id)
        if not collection: return
        
        collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.debug(f"[VECTOR] Stored document {doc_id} for user {user_id}")

    async def query_memory(self, user_id: str, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search within user's private collection.
        """
        collection = self._get_user_collection(user_id)
        if not collection: return []
        
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # Flatten results for easier use
        formatted = []
        if results['documents']:
            for i in range(len(results['documents'][0])):
                formatted.append({
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
        return formatted
