# -*- coding: utf-8 -*-
"""S5-2：统一的大模型调用层（只用标准库，避免额外依赖）。

支持两种后端：
  * ollama:  http://127.0.0.1:11434/api/chat   （模型名不含冒号也可，如 qwen2.5:7b-instruct）
  * openai:  {base_url}/chat/completions       （vLLM / DeepSeek / 通义等兼容接口）

用法（自测）：
    python src/llm/client.py --model qwen2.5:7b-instruct --prompt "Return JSON {\"ok\":true}"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OPENAI_BASE = os.environ.get("OPENAI_BASE", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

DEFAULT_PARAMS = {"temperature": 0, "top_p": 1.0, "max_tokens": 3072, "seed": 42}


class LLMError(RuntimeError):
    pass


def _post(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OllamaClient:
    def __init__(self, model: str, params: dict | None = None, timeout: int = 300,
                 retries: int = 3):
        self.model = model
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.timeout = timeout
        self.retries = retries

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.params["temperature"],
                "top_p": self.params["top_p"],
                "num_predict": self.params["max_tokens"],
                "seed": self.params["seed"],
                "num_ctx": 16384,
            },
        }
        last = None
        for attempt in range(self.retries):
            try:
                resp = _post(f"{OLLAMA_URL}/api/chat", payload,
                             {"Content-Type": "application/json"}, self.timeout)
                msg = resp.get("message") or {}
                text = msg.get("content", "")
                if not text:
                    raise LLMError(f"empty content: {str(resp)[:200]}")
                return text
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 ** attempt)
        raise LLMError(f"ollama failed after {self.retries} tries: {last}")


class OpenAICompatClient:
    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None,
                 params: dict | None = None, timeout: int = 300, retries: int = 3):
        self.model = model
        self.base = (base_url or OPENAI_BASE).rstrip("/")
        self.key = api_key or OPENAI_KEY
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.timeout = timeout
        self.retries = retries
        if not self.base:
            raise LLMError("缺少 OPENAI_BASE 环境变量")

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.params["temperature"],
            "top_p": self.params["top_p"],
            "max_tokens": self.params["max_tokens"],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        last = None
        for attempt in range(self.retries):
            try:
                resp = _post(f"{self.base}/chat/completions", payload, headers, self.timeout)
                return resp["choices"][0]["message"]["content"]
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 ** attempt)
        raise LLMError(f"openai-compatible failed after {self.retries} tries: {last}")


def make_client(model: str, **kwargs):
    if model.startswith("openai:") or (not model.startswith("ollama:") and OPENAI_BASE
                                       and ":" not in model.split(":")[0]):
        return OpenAICompatClient(model, **kwargs)
    if model.startswith("ollama:"):
        model = model.split(":", 1)[1]
    return OllamaClient(model, **kwargs)


def main():
    ap = argparse.ArgumentParser(description="调用层自测")
    ap.add_argument("--model", default="qwen2.5:7b-instruct")
    ap.add_argument("--prompt", default='Return JSON only: {"ok": true}')
    args = ap.parse_args()
    client = make_client(args.model)
    t0 = time.time()
    out = client.generate(args.prompt)
    print(f"[{time.time() - t0:.1f}s] {out[:500]}")


if __name__ == "__main__":
    main()
