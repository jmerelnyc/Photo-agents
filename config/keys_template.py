# =============================================================================
#  Photo Agents — credentials.py template
#
#  Quick start:
#    1. Copy this file to ``credentials.py`` at the project root.
#    2. Uncomment one of the configs below and fill in your provider apikey.
#    3. Run ``python -m photoagents`` (or any of the launchers in
#       ``photoagents/cli/``).
#
#  Photo Agents auto-detects any module-level variable whose name contains
#  ``api`` / ``config`` / ``cookie`` and picks the session class by keyword:
#
#      name contains 'native' + 'claude'  -> NativeClaudeSession  (Anthropic)
#      name contains 'native' + 'oai'     -> NativeOAISession     (OpenAI)
#      name contains 'mixin'              -> MixinSession         (failover)
#
#  Native sessions place tools in the provider's native ``tool`` field
#  (function calling). Recommended for GPT / Claude / Gemini.
#
#  Tip: runtime overrides via ``/session.<attr>=<val>`` in the REPL, e.g.::
#
#      /session.reasoning_effort=high
#      /session.thinking_type=adaptive
#      /session.temperature=0.3
#
#  This file is for the LLM provider credentials only. Your Photo Agents API
#  key (the one that gates the runtime) is read from the
#  ``PHOTOAGENTS_API_KEY`` env var or from ``~/.photoagents/config.json``.
# =============================================================================


# -- 1. NativeClaudeSession (Anthropic) ---------------------------------------
#  Official Anthropic endpoint. An apikey starting with ``sk-ant-`` is sent
#  as ``x-api-key``; any other prefix uses ``Authorization: Bearer``.
#  Model suffix ``[1m]`` enables the 1M-context beta (stripped before sending).
native_claude_config = {
    "name": "claude",
    "apikey": "sk-ant-<your-anthropic-key>",
    "apibase": "https://api.anthropic.com",
    "model": "claude-opus-4-7[1m]",
    "thinking_type": "adaptive",                # 'adaptive' | 'enabled' | 'disabled'
    # "thinking_budget_tokens": 32768,          # required when thinking_type='enabled'
    # "max_retries": 3,
    # "read_timeout": 180,
}


# -- 2. NativeOAISession (OpenAI) ---------------------------------------------
#  Standard OpenAI chat/completions endpoint. Also works for any
#  OpenAI-compatible provider that supports native function-calling tool fields.
native_oai_config = {
    "name": "gpt",
    "apikey": "sk-<your-openai-key>",
    "apibase": "https://api.openai.com/v1",
    "model": "gpt-5.4",
    "api_mode": "chat_completions",             # or 'responses' for /v1/responses
    # "reasoning_effort": "high",               # none|minimal|low|medium|high|xhigh
    # "max_retries": 3,
    # "read_timeout": 120,
}


# -- 3. Mixin failover (optional) ---------------------------------------------
#  List sessions by ``name``; if one fails the next is tried automatically.
#  All referenced sessions must be Native (mixing Native Claude and Native
#  OAI is fine; mixing Native with non-Native is not).
# mixin_config = {
#     "llm_nos": ["claude", "gpt"],
#     "max_retries": 5,
#     "base_delay": 0.5,
# }


# -- 4. Global HTTP proxy (optional) ------------------------------------------
#  Applies to every session that does not set its own ``proxy`` field.
# proxy = "http://127.0.0.1:7890"


# -- 5. Chat platform integrations (optional) ---------------------------------
# tg_bot_token = "..."
# tg_allowed_users = [123456789]


# -- 6. Observability (optional) ----------------------------------------------
# langfuse_config = {
#     "host": "https://cloud.langfuse.com",
#     "public_key": "pk-lf-...",
#     "secret_key": "sk-lf-...",
# }
