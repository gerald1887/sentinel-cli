# Provider Adapters

Sentinel delegates all LLM invocations to *provider adapters*. The adapter
boundary is defined in `sentinel/providers/base.py` and follows a minimal
Protocol.

## ProviderAdapter Protocol

```python
class ProviderAdapter(Protocol):
    def invoke(
        self,
        request: ProviderRequest,
    ) -> ProviderResponseNormalized | SentinelError:
        ...
```

`invoke` must never raise. All error conditions are expressed as
`SentinelError` return values using one of the standardized provider-layer
categories defined in `sentinel/providers/base.py` (e.g.
`PROVIDER_AUTH_ERROR`, `PROVIDER_TIMEOUT`).

## Implementing a new adapter

Adding a provider requires two files:

1. **The adapter module** — `sentinel/providers/<name>.py`.  
   Implement `ProviderAdapter.invoke`. Import the provider SDK lazily
   inside `invoke` so the base install remains SDK-free. Return
   `SENTINEL_PROVIDER_SDK_IMPORT_ERROR` if the import fails.

2. **Resolver entry** — update `sentinel/providers/__init__.py` to map
   the provider's string name to your adapter class inside
   `get_provider_adapter`.

See `sentinel/providers/openai.py` for the reference implementation,
including lazy import, key-redaction helpers, and error category mapping.

## Planned adapters

- **Anthropic** — Claude model family via the `anthropic` SDK.
- **Google Gemini** — Gemini model family via the `google-generativeai` SDK.

## Community adapters

- **Ollama** — Ollama exposes an OpenAI-compatible endpoint; an adapter can
  reuse the OpenAI SDK with a custom `base_url`.
- Any provider with a Python SDK or HTTP API is a candidate.

## Contributor guide

To contribute a new adapter, follow the two-file pattern above using the
OpenAI adapter as your reference. The main invariants to preserve:

- Lazy SDK import with a graceful `SENTINEL_PROVIDER_SDK_IMPORT_ERROR` return.
- No exceptions past the adapter boundary — every error path returns a
  `SentinelError`.
- Redact secrets from error details before including them in `SentinelError.details`.
- Use the standardized `PROVIDER_*` category constants from `base.py`.
