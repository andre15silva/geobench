"""Model backends. Neither one gives the model any tools, so no web search is possible.

* ``api`` - Anthropic Messages API (needs ANTHROPIC_API_KEY). No ``tools`` are sent.
* ``cli`` - the Claude Code CLI in print mode with ``--tools ""`` (no built-in tools),
  ``--strict-mcp-config`` (no MCP servers), our own system prompt replacing Claude
  Code's, and a throw-away working directory. Uses whatever account the CLI is logged in as.
"""
import json
import os
import subprocess
import tempfile

from .prompts import SYSTEM


class APIBackend:
    def __init__(self, model: str, max_tokens: int = 16000, thinking: int | None = None):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model, self.max_tokens, self.thinking = model, max_tokens, thinking

    def __call__(self, prompt: str) -> dict:
        kw = {}
        if self.thinking:
            kw["thinking"] = {"type": "enabled", "budget_tokens": self.thinking}
        msg = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}], **kw)
        text = "".join(b.text for b in msg.content if b.type == "text")
        return {"text": text, "usage": msg.usage.model_dump()}


class CLIBackend:
    def __init__(self, model: str, effort: str | None = None, timeout: int = 900):
        self.model, self.effort, self.timeout = model, effort, timeout
        self.cwd = tempfile.mkdtemp(prefix="geobench-")

    def __call__(self, prompt: str) -> dict:
        cmd = ["claude", "-p", "--model", self.model, "--tools", "", "--strict-mcp-config",
               "--system-prompt", SYSTEM, "--output-format", "json", "--setting-sources", ""]
        if self.effort:
            cmd += ["--effort", self.effort]
        env = {k: v for k, v in os.environ.items() if k != "MAX_THINKING_TOKENS"}
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           timeout=self.timeout, cwd=self.cwd, env=env)
        try:
            d = json.loads(p.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"claude CLI failed ({p.returncode}): {p.stderr[-500:] or p.stdout[-500:]}")
        if d.get("is_error"):
            raise RuntimeError(f"claude CLI error: {d.get('result')}")
        if d.get("num_turns", 1) != 1 or d.get("permission_denials"):
            raise RuntimeError("model attempted tool use")
        return {"text": d["result"], "usage": d.get("usage"), "cost_usd": d.get("total_cost_usd")}


def make(backend: str, model: str, **kw):
    return {"api": APIBackend, "cli": CLIBackend}[backend](model, **kw)
