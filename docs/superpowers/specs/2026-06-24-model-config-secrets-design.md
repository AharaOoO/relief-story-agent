# Model Configuration And Secret Isolation Design

## Goal

Allow a locally deployed Relief Story Agent to bind Gemini, DeepSeek, and GPT-compatible endpoints to existing pipeline stages without storing API keys in run state, API responses, artifacts, or persistent JSON files.

## Architecture

The service loads a JSON model registry at startup. The registry contains reusable non-secret profiles and stage-to-profile bindings. Profiles may name an environment variable through `api_key_env`, but plaintext `api_key` entries are rejected.

Run requests may:

- choose another registered profile through `model_profiles`;
- override non-secret tuning fields through `model_configs`;
- temporarily provide a direct `api_key` for backward compatibility.

The direct key remains memory-only because the field is excluded from all Pydantic serialization and representation. Environment references and profile names are safe to persist and survive service restarts.

## Resolution Order

For each model stage:

1. Use the run-level profile override when present.
2. Otherwise use the registry's stage binding.
3. Apply only fields explicitly supplied in the run-level `model_configs` entry.
4. At call time, prefer a memory-only direct key, then resolve `api_key_env`, then use the local placeholder key for endpoints that require no authentication.

## Safe Introspection

`GET /api/config/models` returns:

- profile names, endpoint URLs, model names, and environment variable names;
- stage-to-profile bindings;
- whether each referenced secret is configured;
- missing environment variable names.

It never returns secret values.

## Failure Behavior

- A registry containing plaintext `api_key` fails to load.
- A stage bound to an unknown profile fails to load.
- A referenced but missing environment variable fails the affected model call with a clear error.
- A direct key disappears after persistence by design; durable runs should use `api_key_env`.

## Verification

Tests inspect serialized model dumps, API payloads, and raw state files for secret leakage. Additional tests cover registry validation, explicit override merging, environment resolution, and safe status output.
