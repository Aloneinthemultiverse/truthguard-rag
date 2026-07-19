"""Anthropic-compatible LLM client with a per-query call budget (hard cap 6)."""
import json
import re

from . import config


class BudgetExceeded(Exception):
    pass


class LLM:
    def __init__(self):
        # LLM_PROVIDER: "anthropic" (default) or "openai" (NVIDIA NIM, OpenAI, any
        # OpenAI-compatible /v1/chat/completions endpoint).
        self.provider = getattr(config, "LLM_PROVIDER", "anthropic").lower()
        if self.provider in ("openai", "nim", "nvidia"):
            import openai
            self.client = openai.OpenAI(
                base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
            self.provider = "openai"
        else:
            import anthropic
            self.client = anthropic.Anthropic(
                base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
        self.calls = 0

    def reset_budget(self):
        self.calls = 0

    def complete(self, prompt: str, max_tokens: int = 800, temperature: float = 0.0) -> str:
        if self.calls >= config.MAX_LLM_CALLS_PER_QUERY:
            raise BudgetExceeded(f"LLM call budget ({config.MAX_LLM_CALLS_PER_QUERY}) exhausted")
        self.calls += 1
        max_tokens = max(max_tokens * 4, 3000)
        for attempt in range(3):
            if self.provider == "openai":
                import time
                for backoff in (0, 20, 45, 90):        # ride out 429 rate limits
                    if backoff:
                        time.sleep(backoff)
                    try:
                        resp = self.client.chat.completions.create(
                            model=config.LLM_MODEL, max_tokens=max_tokens, temperature=temperature,
                            messages=[{"role": "user", "content": prompt}])
                        break
                    except Exception as e:
                        if "429" not in str(e) or backoff == 90:
                            raise
                text = (resp.choices[0].message.content or "").strip()
                truncated = resp.choices[0].finish_reason == "length"
            else:
                # proxied thinking models (gemini) consume max_tokens on internal
                # reasoning before emitting text — retry with doubled budget on empty.
                resp = self.client.messages.create(
                    model=config.LLM_MODEL, max_tokens=max_tokens, temperature=temperature,
                    messages=[{"role": "user", "content": prompt}])
                text = "".join(b.text for b in resp.content if b.type == "text").strip()
                truncated = getattr(resp, "stop_reason", None) == "max_tokens"
            if text and not truncated:
                return text
            max_tokens = min(max_tokens * 2, 16000)
        return text

    def complete_json(self, prompt: str, max_tokens: int = 800):
        """Complete and parse the first JSON object/array in the response."""
        raw = self.complete(prompt + "\nReturn ONLY valid JSON, no markdown.", max_tokens)
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M)
        m = re.search(r"[\[{].*[\]}]", raw, re.DOTALL)
        if not m:
            return None
        candidate = m.group(0)
        candidate = re.sub(r"//[^\n\"]*$", "", candidate, flags=re.M)   # strip // comments
        candidate = re.sub(r",\s*([\]}])", r"\1", candidate)            # trailing commas
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            import sys
            print(f"  [llm] JSON parse failed: {e} :: {candidate[:150]!r}", file=sys.stderr)
            return None
