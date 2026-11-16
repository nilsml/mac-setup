"""Engangsoverføring på Macen. Ingen nøkler i filer, argumenter eller utdata.

Uten --apply kontrolleres bare at aktive API-nøkler finnes.
Kjør aldri som dynamisk --command-kilde fra den skrivbare prosjektmappen.
"""

import argparse
import json
import subprocess
import sys


TARGET = "opencode-work"
PROVIDERS = ("anthropic", "berget")


def export_active_key(provider):
    result = subprocess.run(
        ["opencode", "auth", "export", provider],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(f"Eksport feilet for {provider}. Detaljer skjult.")
    try:
        entries = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError(f"Uventet eksportformat for {provider}.") from None
    if not isinstance(entries, list):
        raise ValueError(f"Uventet eksportformat for {provider}.")
    active = [
        entry for entry in entries
        if isinstance(entry, dict)
        and entry.get("integrationID") == provider
        and entry.get("active") is True
    ]
    if len(active) != 1:
        raise ValueError(f"Forventet én aktiv innlogging for {provider}.")
    value = active[0].get("value", {})
    key = value.get("key")
    if value.get("type") != "key" or not isinstance(key, str) or not key.strip():
        raise ValueError(f"Ingen aktiv API-nøkkel for {provider}.")
    if "\n" in key or "\r" in key:
        raise ValueError(f"Uventet nøkkelformat for {provider}.")
    return key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Registrer nøklene i sbx")
    parser.add_argument("--sandbox", default=TARGET, help="Sandbox som skal få nøklene")
    parser.add_argument("--provider", action="append", choices=PROVIDERS, help="Overfør bare valgt leverandør; kan gjentas")
    args = parser.parse_args()
    target = args.sandbox
    if not target or target.startswith("-") or any(c.isspace() for c in target):
        raise ValueError("Ugyldig sandboxnavn.")

    # Kontroller alle valgte før noe registreres. Nøkler holdes bare i prosessminnet.
    providers = tuple(dict.fromkeys(args.provider or PROVIDERS))
    keys = {provider: export_active_key(provider) for provider in providers}
    if not args.apply:
        print(f"Aktive API-nøkler finnes for {', '.join(providers)}. Ingenting registrert for {target}.")
        return

    for provider, key in keys.items():
        result = subprocess.run(
            ["sbx", "--no-input", "secret", "set", provider, "--sandbox", target],
            input=key + "\n",
            capture_output=True,
            text=True,
        )
        # Ikke vis rå utdata fra verktøy som håndterer hemmeligheter.
        if result.returncode:
            raise ValueError(
                f"Registrering av {provider} feilet. Detaljer skjult. "
                "Tidligere registreringer beholdes; ingen automatisk tilbakerulling."
            )
        print(f"{provider}: registrert for {target}.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
