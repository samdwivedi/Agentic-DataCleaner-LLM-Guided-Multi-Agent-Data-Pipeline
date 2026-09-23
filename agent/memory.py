"""
Conversation Memory Module
──────────────────────────
Short-term: LangChain ConversationBufferWindowMemory (sliding window)
Long-term:  FAISS vector store with sentence-transformers embeddings
            (optional, activates only if faiss-cpu & sentence-transformers installed)
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MEMORY_MAX_HISTORY
from agent.logger import get_logger

logger = get_logger(__name__)


class AgentMemory:
    """
    Manages both short-term and optional long-term memory for the agent.
    """

    def __init__(self, max_history: int = MEMORY_MAX_HISTORY):
        self.max_history = max_history

        # Short-term: sliding window buffer
        self._buffer = ConversationBufferWindowMemory(
            k=max_history,
            memory_key="chat_history",
            return_messages=True,
            output_key="output",
        )

        # Simple list for UI display
        self._history: List[Tuple[str, str]] = []  # (human, ai)

        # Long-term FAISS memory (optional)
        self._vector_store = None
        self._embedder = None
        self._try_init_vector_store()

    def _try_init_vector_store(self) -> None:
        """Initialize FAISS + sentence-transformers if available."""
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            import numpy as np

            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            dim = 384  # MiniLM embedding dimension
            self._faiss_index = faiss.IndexFlatL2(dim)
            self._faiss_texts: List[str] = []
            logger.info("Long-term FAISS memory initialized.")
        except ImportError:
            logger.info("FAISS / sentence-transformers not available – using short-term memory only.")

    def add_interaction(self, human_msg: str, ai_msg: str) -> None:
        """Record a human-AI exchange."""
        self._history.append((human_msg, ai_msg))

        # Add to LangChain buffer
        self._buffer.save_context(
            {"input": human_msg},
            {"output": ai_msg},
        )

        # Optionally index into FAISS
        if self._embedder is not None:
            try:
                import numpy as np
                full_text = f"Q: {human_msg}\nA: {ai_msg}"
                vec = self._embedder.encode([full_text]).astype("float32")
                self._faiss_index.add(vec)
                self._faiss_texts.append(full_text)
            except Exception as exc:
                logger.warning("FAISS indexing failed: %s", exc)

    def search_memory(self, query: str, top_k: int = 3) -> List[str]:
        """Search long-term memory for relevant past exchanges."""
        if self._embedder is None or not self._faiss_texts:
            return []
        try:
            import numpy as np
            q_vec = self._embedder.encode([query]).astype("float32")
            distances, indices = self._faiss_index.search(q_vec, top_k)
            results = []
            for idx in indices[0]:
                if 0 <= idx < len(self._faiss_texts):
                    results.append(self._faiss_texts[idx])
            return results
        except Exception:
            return []

    @property
    def langchain_memory(self) -> ConversationBufferWindowMemory:
        return self._buffer

    @property
    def history(self) -> List[Tuple[str, str]]:
        return self._history

    def get_recent_context(self, n: int = 5) -> str:
        """Return the last N exchanges as a formatted string."""
        recent = self._history[-n:]
        lines = []
        for human, ai in recent:
            lines.append(f"🧑 **User:** {human}")
            lines.append(f"🤖 **Agent:** {ai[:200]}...")
        return "\n".join(lines) if lines else "No previous context."

    def clear(self) -> None:
        """Reset all memory."""
        self._history.clear()
        self._buffer.clear()
        if self._embedder is not None:
            import faiss
            dim = 384
            self._faiss_index = faiss.IndexFlatL2(dim)
            self._faiss_texts.clear()
