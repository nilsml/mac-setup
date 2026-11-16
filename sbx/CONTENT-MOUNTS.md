# Levende innholdsmounts

## Modell

Nye sandboxer får én skrivbar prosjektmount og eksplisitt valgte,
skrivebeskyttede innholdsmounts. De bruker arbeidsfilene direkte, uten pins,
kopiering av innhold eller oppdateringsmotor. Sandboxene kan erstattes.
Varig arbeid må ligge i prosjektmounten eller eksterne systemer.

En gammel sandbox får ingen nye mounts eller innholdsregistrering automatisk.
Bruk et nytt navn for den nye løsningen. `oc open NAVN` og `oc shell NAVN`
kan fortsatt åpne gamle miljøer med deres opprinnelige oppsett.

## Privat vertskatalog

Katalogformat 1 støttes fortsatt for lesende lagvalg. Prosjektoppstart med
innhold krever format 2 og `content` på hvert valgt lag:

```json
{
  "schemaVersion": 2,
  "layers": [
    {
      "id": "personal",
      "scope": {"type": "always"},
      "requires": [],
      "content": {
        "source": "~/content/personal",
        "skills": ["plugins/core/skills"],
        "instructions": ["opencode/AGENTS.md"],
        "agents": "opencode/agents",
        "defaultAgent": "main"
      }
    },
    {
      "id": "work",
      "scope": {"type": "directory", "path": "~/work"},
      "requires": ["personal"],
      "content": {
        "source": "~/content/work",
        "skills": ["plugins/core/skills"]
      }
    }
  ]
}
```

`source` er en absolutt sti eller `~/`-sti. Øvrige innholdsstier er relative
til kilden. `skills` er obligatorisk. Instruksjoner og agenter er valgfrie.
Bare ett lag kan levere agentmappen. Standardagenten må ha en Markdown-fil
direkte i denne mappen. Agenter må være OpenCode-definisjoner; Claude-hooks
konverteres ikke.

Ruting, avhengigheter og kontroll av repoidentitet følger samme regler som
format 1. Katalogen skal ligge utenfor prosjektets skrivbare mount.
Ingen credentials, shellkommandoer eller automatisk prosjektbootstrap.

## Opprettelse

`oc` sender `--content` til `start.py`. Direkte `start.py` beholder
eksplisitt mappevalg og aktiverer innhold bare med `--content`.
`--catalog FIL` kan brukes ved prosjektoppstart og `capabilities`.

For hvert lag brukes sbx sitt ekstra arbeidsområde:

```text
VERTSKILDE:/opt/opencode-content/LAG:ro
```

Launcheren kontrollerer oppløste kilder, nødvendige filer og kjente
navnekollisjoner før opprettelse. Alle mounts vises før bekreftelse.
Etter opprettelse kontrolleres faktiske mounts og kit før konfigurasjon.

Runtime-koden kjøres som `agent`. Den bevarer Docker-generert JSON, providers,
global `AGENTS.md` og manuelle verdier. Den legger til skill- og
instruksjonsstier og lager en lenke fra global `agents` til den monterte
agentmappen. Ukjent JSONC, konfliktende standardagent, eksisterende agentmappe
eller kilder som ikke kan kontrolleres, stopper oppsettet.

Oppsettmarkør ligger i `~/.local/state/opencode-sbx/content.json`.
Gjenåpning gjennom prosjektoppstart kontrollerer oppsettet uten å oppdatere det.
Ved ufullstendig oppsett beholdes sandboxen. Ingen automatisk reparasjon,
sletting eller gjenskaping. Velg et nytt navn etter at årsaken er rettet.

## Avgrensninger

- Hele den valgte kildemappen er lesbar, inkludert eventuell Git-historikk.
- Skrivebeskyttelsen gjelder mountstien. En overlappende skrivbar prosjektmount
  kan gi en alternativ skrivbar sti til samme kilde.
- Endringer på verten blir synlige i mounten. OpenCode kan trenge `/reload`
  eller en ny sesjon før endret innhold brukes. Allerede innlastet
  samtaleinnhold blir ikke dermed erstattet.
- Kollisjonskontrollen dekker de eksplisitte kildene og kjente filbaserte
  prosjektkilder. Den er ingen full analyse av plugins, HTTP-kataloger eller
  alle mulige prosjektkonfigurasjoner.
- Tilgjengelige agent- og skill-filer beviser ingen MCP-tilkobling eller
  faktisk modellbruk.
- Vanlig `oc` skal bruke en gjennomgått launcher utenfor prosjektmountene.
  `install-launcher.py` viser som standard bare en kopiplan. Installasjon
  og endring av shellfunksjonen krever separat godkjenning.

## Kilder

- https://docs.docker.com/ai/sandboxes/usage/#multiple-workspaces
- https://opencode.ai/docs/skills
- https://opencode.ai/docs/agents
- https://opencode.ai/docs/instructions
