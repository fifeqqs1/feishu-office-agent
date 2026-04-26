from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings
from loguru import logger

from agentchat.core.models.manager import ModelManager
from agentchat.schema.search import SearchModel


class ChromaKnowledgeClient:
    def __init__(self) -> None:
        base_dir = Path(
            os.getenv(
                "OMNIAGENT_CHROMA_DIR",
                str(Path.home() / ".local-run" / "omniagent" / "chroma"),
            )
        )
        base_dir.mkdir(parents=True, exist_ok=True)

        settings = Settings(
            anonymized_telemetry=False,
            is_persistent=True,
            persist_directory=str(base_dir),
        )
        self.client = chromadb.Client(settings)
        self.collections: Dict[str, chromadb.Collection] = {}
        self.embedding_model = ModelManager.get_embedding_model()
        self.top_k = app_settings.rag.retrival.get("top_k", 5)

    def _get_collection(self, collection_name: str) -> Optional[chromadb.Collection]:
        if collection_name in self.collections:
            return self.collections[collection_name]

        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            return None

        self.collections[collection_name] = collection
        return collection

    async def create_collection(self, collection_name: str) -> chromadb.Collection:
        collection = self._get_collection(collection_name)
        if collection is not None:
            return collection

        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.collections[collection_name] = collection
        return collection

    async def insert(self, collection_name: str, chunks) -> bool:
        collection = await self.create_collection(collection_name)

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[dict] = []

        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.content)
            metadatas.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "file_id": chunk.file_id,
                    "file_name": chunk.file_name,
                    "knowledge_id": chunk.knowledge_id,
                    "update_time": chunk.update_time,
                    "summary": chunk.summary,
                    "is_summary": False,
                }
            )

            if chunk.summary:
                ids.append(f"{chunk.chunk_id}_summary")
                documents.append(chunk.summary)
                metadatas.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "file_id": chunk.file_id,
                        "file_name": chunk.file_name,
                        "knowledge_id": chunk.knowledge_id,
                        "update_time": chunk.update_time,
                        "summary": chunk.summary,
                        "is_summary": True,
                    }
                )

        if not documents:
            return True

        embeddings = await self.embedding_model.embed_async(documents)
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Inserted {len(chunks)} chunks into collection `{collection_name}`")
        return True

    async def search(
        self,
        query: str,
        collection_name: str,
        top_k: Optional[int] = None,
    ) -> List[SearchModel]:
        return await self._search(query, collection_name, is_summary=False, top_k=top_k)

    async def search_summary(
        self,
        query: str,
        collection_name: str,
        top_k: Optional[int] = None,
    ) -> List[SearchModel]:
        return await self._search(query, collection_name, is_summary=True, top_k=top_k)

    async def _search(
        self,
        query: str,
        collection_name: str,
        *,
        is_summary: bool,
        top_k: Optional[int],
    ) -> List[SearchModel]:
        collection = self._get_collection(collection_name)
        if collection is None:
            return []

        query_embedding = await self.embedding_model.embed_async(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k or self.top_k,
            include=["metadatas", "documents", "distances"],
            where={"is_summary": is_summary},
        )

        documents: List[SearchModel] = []
        for idx, chunk_id in enumerate(results.get("ids", [[]])[0]):
            metadata = results["metadatas"][0][idx]
            documents.append(
                SearchModel(
                    chunk_id=metadata.get("chunk_id", chunk_id),
                    content=results["documents"][0][idx],
                    score=results["distances"][0][idx],
                    file_id=metadata.get("file_id", ""),
                    file_name=metadata.get("file_name", ""),
                    update_time=metadata.get("update_time", ""),
                    knowledge_id=metadata.get("knowledge_id", ""),
                    summary=metadata.get("summary", ""),
                )
            )

        return documents

    async def delete_by_file_id(self, file_id: str, collection_name: str) -> bool:
        collection = self._get_collection(collection_name)
        if collection is None:
            return False

        collection.delete(where={"file_id": file_id})
        logger.info(f"Deleted Chroma documents for file_id `{file_id}` from `{collection_name}`")
        return True


from agentchat.settings import app_settings


milvus_client = ChromaKnowledgeClient()
