"""Kjøres i sandboxen. Bevarer eksisterende leverandører og kjøretidsdata."""

import json
from pathlib import Path


DEFAULT_MODEL = "openai/gpt-6.2-sol"
# opencode gir bare gratismodeller i sandboxen, fordi den bruker offentlig nøkkel.
ALLOWED_PROVIDERS = ("openai", "anthropic", "berget", "opencode")
PROVIDER_POLICIES = (
    {"action": "provider.use", "resource": "*", "effect": "deny"},
    *(
        {"action": "provider.use", "resource": name, "effect": "allow"}
        for name in ALLOWED_PROVIDERS
    ),
)


def with_provider_policies(config, rules=PROVIDER_POLICIES):
    """Append provider rules last, so they win over earlier policies."""
    current = config.get("policies", [])
    if not isinstance(current, list):
        raise ValueError("Forventet policies som liste. Ingen filer endret.")
    rules = list(rules)
    if current[-len(rules):] == rules:
        return config
    return {**config, "policies": [*current, *rules]}


def with_default_model(config, model=DEFAULT_MODEL):
    """Set a fallback model without replacing an explicit choice."""
    current = config.get("model")
    if current is not None and not isinstance(current, str):
        raise ValueError("Forventet model som tekst. Ingen filer endret.")
    return config if current else {**config, "model": model}


def merge_providers(config, additions):
    existing = config.get("providers", {})
    if not isinstance(existing, dict):
        raise ValueError("Forventet providers som objekt")
    conflicts = [
        name for name, value in additions.items()
        if name in existing and existing[name] != value
    ]
    if conflicts:
        raise ValueError("Eksisterende leverandøroppsett avviker. Ingen filer endret.")
    legacy = config.get("provider", {})
    if isinstance(legacy, dict) and set(additions) & set(legacy):
        raise ValueError("Leverandør finnes i eldre provider-felt. Ingen filer endret.")
    return {**config, "providers": {**existing, **additions}}


def main():
    root = Path.home() / ".config/opencode"
    path = root / "opencode.json"
    config = json.loads(path.read_text()) if path.exists() else {}
    additions = json.loads(Path(__file__).with_name("providers.json").read_text())
    updated = with_provider_policies(
        with_default_model(merge_providers(config, additions))
    )
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
