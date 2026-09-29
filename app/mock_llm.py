from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .incidents import STATE
from .pii import summarize_text
from .tracing import get_langfuse_client


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str
    ttft_ms: int


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model

    def generate(self, prompt: str) -> FakeResponse:
        """Generate a response from the LLM.

        Instrumented as a child generation observation under the current span.
        Captures prompt, token usage, model, and timing information.
        """
        langfuse_client = get_langfuse_client()

        with langfuse_client.start_as_current_observation(
            name="llm-generation",
            as_type="generation",
            model=self.model,
            input={"prompt": summarize_text(prompt)},
        ) as gen_obs:
            started = time.perf_counter()
            time.sleep(0.05)  # mô phỏng thời điểm token đầu tiên sẵn sàng
            ttft_ms = int((time.perf_counter() - started) * 1000)
            time.sleep(0.10)
            input_tokens = max(20, len(prompt) // 4)
            output_tokens = random.randint(80, 180)
            if STATE["cost_spike"]:
                output_tokens *= 4
            answer = (
                "Starter answer. You should improve this output logic and add better quality checks. "
                "Use retrieved context and keep responses concise."
            )

            gen_obs.update(
                output=summarize_text(answer),
                usage_details={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )

            return FakeResponse(
                text=answer,
                usage=FakeUsage(input_tokens, output_tokens),
                model=self.model,
                ttft_ms=ttft_ms,
            )
