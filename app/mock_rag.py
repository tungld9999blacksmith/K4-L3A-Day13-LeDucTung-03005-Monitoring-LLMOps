from __future__ import annotations

import time

from .incidents import STATE
from .pii import summarize_text
from .tracing import get_langfuse_client

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, logs identify affected requests, traces localize the root cause."],
    "policy": ["Do not expose PII in logs. Use sanitized summaries only."],
}


def retrieve(message: str) -> list[str]:
    """Retrieve documents matching the query message.

    Instrumented as a child retriever observation under the current span.
    """
    langfuse_client = get_langfuse_client()

    with langfuse_client.start_as_current_observation(
        name="retrieval",
        as_type="retriever",
        input={"query": summarize_text(message)},
    ) as retriever_obs:
        try:
            if STATE["tool_fail"]:
                raise RuntimeError("Vector store timeout")
            if STATE["rag_slow"]:
                time.sleep(2.5)
            lowered = message.lower()
            for key, docs in CORPUS.items():
                if key in lowered:
                    retriever_obs.update(output=docs)
                    return docs
            result = ["No domain document matched. Use general fallback answer."]
            retriever_obs.update(output=result)
            return result
        except Exception as exc:
            retriever_obs.update(
                status_message=str(exc),
                level="ERROR",
            )
            raise
