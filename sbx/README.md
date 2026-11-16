# OpenCode i Docker Sandboxes

Gjenbrukbart Linux-miljø for OpenCode, med **én vedvarende sandbox per prosjekt**. Bare prosjektmappen monteres fra Macen, med skrivetilgang. Bredere arbeid gjøres utenfor `sbx`.

Oppskriftene hører hjemme i `mac-setup`. Innlogging, API-nøkler, databaser og samtaler skal ikke i Git eller images.

## Status

Verifisert 16. november 2026 med `sbx` 0.53.0 og OpenCode 2.3.0:

- Debian 13 ARM64, zsh, oh-my-zsh, Starship, autoforslag og syntaksutheving.
- Git, GitHub CLI, eza, Neovim, Node/npm og Python med venv.
- Nord-tema, Powerline-plugin og et kort, Linux-tilpasset instruksjonsutvalg.
- Minimale modellkall til GPT-6.1 Sol, Claude Opus 5.5 og Bergets GLM-5.3 Flash svarte `OK` i `opencode-work`.
- Seks Berget-modeller er konfigurert. Bare GLM er funksjonstestet.
- Oppstartsscriptet er testet med simulerte CLI-kall og lesende kontroll mot eksisterende sandbox. Ny opprettelse gjennom scriptet må fortsatt prøves i terminalen.

Agenter og skills er neste leveranse. MCP, inkludert Browse og Logseq, er utsatt. Full kontroll av tastatursnarveier, terminalvisning og persistens gjenstår.

## Første oppsett på en Mac

Du trenger Docker Sandboxes (`sbx`), Python 3.9 eller nyere på verten og OpenCode på Macen. Sandboxen bruker Python 3.13. `sbx` har sin egen runtime; vanlig Docker Desktop-daemon er ikke nødvendig for arbeidsflyten nedenfor.

Kontroller og logg inn fra terminalen:

```sh
sbx version
sbx login
sbx secret set openai --oauth
opencode auth list
```

ChatGPT-innloggingen skal være registrert i `sbx` **før sandboxen opprettes**. Anthropic og Berget må ha aktive API-nøkkelinnlogginger i Macens OpenCode, slik at engangsoverføringen kan hente dem.

## Daglig bruk

Kjør fra prosjektmappen, uavhengig av hvor `mac-setup` er klonet:

```sh
python3 ~/Dev/mac-setup/sbx/start.py .
```

Ved første kjøring:

1. Scriptet viser hvilken mappe som blir skrivbar og ber om bekreftelse.
2. `sbx` oppretter sandboxen med begge mixinene. Godkjenn nettverks- og credential-forespørslene i terminalen.
3. Manglende Anthropic- og Berget-nøkler registreres direkte fra Macens OpenCode, avgrenset til denne sandboxen.
4. OpenCode åpnes i prosjektet.

Senere kjøringer gjenåpner samme sandbox. Navnet avledes fra mappens navn og en hash av den absolutte stien. Flytting av prosjektmappen gir et nytt navn. Scriptet sletter eller gjenskaper aldri en eksisterende sandbox.

Scriptet monterer ikke hele `~/Dev`, hjemmemappen eller naboprosjekter. En eksisterende sandbox må ha riktig prosjektmappe, begge mixinene og nøyaktig én skrivbar vertsmount. Velger du selv en overordnet mappe som argument, blir hele den mappen tilgjengelig. Velg derfor prosjektroten.

### Eksisterende arbeidsmiljø

Det verifiserte miljøet for dette repoet heter `opencode-work`:

```sh
python3 ~/Dev/mac-setup/sbx/start.py ~/Dev/mac-setup --name opencode-work
```

Uten `--name` får dette repoet et nytt, avledet navn. Bruk kommandoen over for å beholde den eksisterende historikken.

### Andre valg

```sh
# Lesende forhåndsvisning. Oppretter eller starter ingenting.
python3 ~/Dev/mac-setup/sbx/start.py . --dry-run

# Sett opp miljøet uten å åpne OpenCode.
python3 ~/Dev/mac-setup/sbx/start.py . --setup-only

# Egendefinert navn, som må brukes igjen ved senere oppstart.
python3 ~/Dev/mac-setup/sbx/start.py . --name opencode-mittprosjekt
```

Scriptet stopper ved feil. Hvis opprettelsen lyktes før et senere steg feilet, beholdes sandboxen. Kjør samme kommando igjen for å fortsette. Eksisterende registrerte secrets overskrives ikke automatisk.

## Sesjoner og tabs

Flere OpenCode-sesjoner i samme prosjekt kan brukes som tabs i samme sandbox. Separate sandboxer har separate OpenCode-servere og databaser. Sesjonene deres samles ikke automatisk i én tabrad; bruk separate terminalfaner når du bytter prosjekt.

OpenCode støtter `tabs.scope: "global"` på tvers av mapper i samme server. Valget `--all-tabs` setter dette midlertidig for klienten, uten å endre Macens konfigurasjon eller gi flere filtilganger:

```sh
python3 ~/Dev/mac-setup/sbx/start.py . --all-tabs
```

Dette forener ikke separate sandboxer. Standardoppsettet holder én prosjektmappe per sandbox.

## Livsløp: exit, stopp og sletting

| Handling | Konsekvens |
| --- | --- |
| Avslutt OpenCode | Agentøkten avsluttes. Sandboxen stopper automatisk når ingen økter holder den i gang. Den slettes ikke. |
| Åpne en zsh-økt i samme sandbox | Denne økten kan holde sandboxen i gang etter at OpenCode er avsluttet. |
| `sbx stop NAVN` | Stopper miljøet. Data beholdes til neste oppstart. Aktive prosesser avbrytes. |
| `sbx run --name NAVN` | Starter eller gjenåpner eksisterende miljø. |
| `sbx rm NAVN` | Sletter sandboxen. Filer i den delte prosjektmappen på Macen beholdes. |

Scriptet bruker verken `--detach` eller `--rm`. Miljøene kjører derfor ikke permanent og slettes ikke automatisk ved exit. `sbx`-bakgrunnstjenesten kan fortsatt kjøre på Macen selv om alle sandboxene er stoppet.

```sh
sbx ls
sbx inspect opencode-work
sbx exec -it opencode-work zsh -l
sbx stop opencode-work
```

Installerte programmer, shellhistorikk og OpenCode-data skal overleve stopp og oppstart så lenge sandboxen finnes. Dette er dokumentert av Docker, men full persistens er ikke ende-til-ende-testet her.

**Stopp er den vanlige handlingen når du vil frigjøre ressurser.** Behandle sletting som potensielt tap av intern historikk og filer. Noen kit-eide volumer kan overleve sletting, men vi har ikke verifisert hvordan denne kit-versjonen gjenkobler dem. Ta separat sikkerhetskopi før sletting. Git av prosjektet tar ikke backup av sandboxens interne data.

Ikke bruk `sbx run --rm`, `sbx prune` eller `sbx reset` som daglig avslutningskommando. `reset` fjerner også lagrede secrets. `--detach` holder et miljø kjørende etter at alle økter er avsluttet; det bruker vi ikke i dette oppsettet.

## Secrets

- `sbx` lagrer secrets i macOS Nøkkelring, ifølge Docker-dokumentasjonen.
- ChatGPT bruker global OAuth i `sbx`. Sandboxens tilgang avhenger også av kit og godkjenninger.
- Anthropic og Berget registreres som sandbox-avgrensede API-nøkler.
- Proxyen på Macen setter inn ekte credentials for godkjente leverandørdomener. Sandboxen bruker plassholdere.
- Berget-mixinen begrenser credential-injeksjon til `api.berget.ai`.
- Nøkkeloverføringen bruker `opencode auth export` for én leverandør om gangen og standard input til `sbx secret set`. Ingen nøkkelverdier skrives til filer, kommandoargumenter eller utdata.
- De opprinnelige nøklene i Macens OpenCode beholdes. Overføringen er en engangskopi; senere nøkkelbytter synkroniseres ikke automatisk.
- Sandboxen kan bruke modelltilgangen og påføre kostnader selv om den ikke kan lese nøkkelen.
- `.env`-filer og andre hemmeligheter inne i den delte prosjektmappen er tilgjengelige for agenten.

Manuell kontroll eller registrering for en allerede opprettet sandbox:

```sh
python3 ~/Dev/mac-setup/sbx/scripts/register-model-secrets.py --sandbox NAVN
python3 ~/Dev/mac-setup/sbx/scripts/register-model-secrets.py --sandbox NAVN --apply
```

Ikke bruk dette scriptet som en dynamisk `--command`-kilde: repoet er skrivbart fra sandboxen. Engangsoverføring skal startes bevisst fra verten etter gjennomgang av koden.

## Struktur og oppdatering

```text
sbx/
├── start.py
├── personal/       # Shellverktøy, Nord, Powerline og instruksjoner
├── models/         # Berget-oppsett og credential-deklarasjon
├── scripts/        # Miljøkontroll og engangsoverføring av API-nøkler
├── tests/          # Tester uten opprettelse eller sletting av sandboxer
└── HISTORY.md      # Verifiserte funn fra utprøvingen
```

Mixinene bygges og caches av `sbx`. De kan gjenbrukes mellom prosjekter, mens hver sandbox beholder egne data og avgrensninger. Kopierte personlige standardinnstillinger oppdateres manuelt fra gjennomgåtte kilder; Macens konfigurasjon er ikke montert.

Endringer i repoet oppdaterer ikke eksisterende sandboxer. Planlegg en ny sandbox med nytt navn ved kit-endringer, og behold den gamle til data og arbeidsflyt er kontrollert. `sbx kit add` støtter foreløpig ikke vårt credential-deklarerende modelltillegg.

Standard-workloaden følger `sbx` sin OpenCode-shortcut. `personal.dockerfile` har et låst baseimage, oh-my-zsh har låst commit og Starship har låst versjon. Hele sammensetningen er ikke fullt versjonslåst: Debian-pakker følger pakkebrønnen, og fremtidige opprettelser kan få en nyere standard-workload. Verifiser kompatibilitet ved oppdatering. Starship-nedlastingen mangler separat checksumverifisering.

Tester på verten:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s sbx/tests -v
python3 sbx/start.py . --name opencode-work --dry-run
```

Miljøkontroll inne i en ny sandbox fra en Mac-terminal:

```sh
sbx exec -i NAVN sh < ~/Dev/mac-setup/sbx/scripts/check-environment.sh
```

## Neste leveranser

**MÅ**

- Prøve ny opprettelse gjennom oppstartsscriptet i en interaktiv terminal.
- Velge og gjennomgå agenter og skills for Linux-miljøet.
- Kontrollere historikk og sesjoner etter stopp og oppstart.

**BØR**

- Dokumentere og teste sikkerhetskopiering og gjenoppretting.
- Gjennomgå oppdateringsrutine og checksumverifisering av nedlastinger.

**SENERE**

- Browse og øvrige MCP-tjenester, med avgrenset transport og autentisering til Macen.
- Ollama, som krever en separat vurdering av vertstilgang.

## Kilder

- [Docker Sandboxes: Usage og livsløp](https://docs.docker.com/ai/sandboxes/usage/)
- [Docker Sandboxes: Credentials](https://docs.docker.com/ai/sandboxes/configuration/credentials/)
- [Docker Sandboxes: Author kits](https://docs.docker.com/ai/sandboxes/customize/author/)
- [OpenCode: CLI og bakgrunnstjeneste](https://opencode.ai/docs/cli)
- [OpenCode: Tabs og CLI-innstillinger](https://opencode.ai/docs/cli/config)
- Lokal `sbx`-hjelp og modelltestene oppsummert i `HISTORY.md`.
