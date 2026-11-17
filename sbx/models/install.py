"""Kjøres i sandboxen. Bevarer eksisterende leverandører og kjøretidsdata."""

import json
from pathlib import Path


DEFAULT_MODEL = "openai/gpt-6.1-sol"


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
    updated = with_default_model(merge_providers(config, additions))
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
