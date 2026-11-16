# OpenCode i Docker Sandboxes

Gjenbrukbart Linux-miljø for OpenCode, med **én utskiftbar sandbox per prosjekt**. Prosjektmappen monteres skrivbart. Nye miljøer kan i tillegg få skrivebeskyttede innholdsmounts. Varig arbeid skal ligge i prosjektmounten eller eksterne systemer.

Oppskriftene hører hjemme i `mac-setup`. Innlogging, API-nøkler, databaser og samtaler skal ikke i Git eller images.

## Status

Verifisert 16. november 2026 med `sbx` 0.53.0 og OpenCode 2.3.0:

- Debian 13 ARM64, zsh, oh-my-zsh, Starship, autoforslag og syntaksutheving.
- Git, GitHub CLI, eza, Neovim, Node/npm og Python med venv.
- Nord-tema, Powerline-plugin og et kort, Linux-tilpasset instruksjonsutvalg.
- Minimale modellkall til GPT-6.1 Sol, Claude Opus 5.5 og Bergets GLM-5.3 Flash svarte `OK` i `opencode-work`.
- Seks Berget-modeller er konfigurert. Bare GLM er funksjonstestet.
- Ny sandbox er opprettet gjennom oppstartsscriptet med pseudo-terminal, begge mixinene og registrering av manglende modellsecrets.
- Personlig og syntetisk prosjektlokal skill er oppdaget og brukt av GPT-6.1 Sol. Navnekollisjon stoppet installasjonen uten filendringer.
- Skills, samtalemetadata og alle meldinger var bevart etter bekreftet stopp/start.
- `oc.py` er testet med enhetstester, ekte lesende oppslag, prosjektgjenkjenning, åpning/avslutning av TUI i pseudo-terminal og bekreftet stopp av testsandboxen.

Ny innholdslevering bruker levende, skrivebeskyttede mounts, uten pins eller kopiering av skills og agenter. Se [CONTENT-MOUNTS.md](CONTENT-MOUNTS.md). Vertskatalog, personlig hovedagent og grunninstruksjoner må godkjennes og aktiveres separat. Den eldre installasjonspiloten beholdes. MCP og funksjonstest av spesialagenter kommer etter grunnleveransen.

MCP bruker en felles vertskatalog. Nye miljøer fra den oppdaterte launcheren får dynamisk oppdagelse og lasting av registrerte tjenester ved behov. Eksisterende miljøer beholdes uendret, uten migrering eller ettermontering. Browse er registrert globalt; relay-/nettlesertilkobling er ikke bekreftet. Separat Logseq-forbindelse med innebygde V2-agentrettigheter og en global Rovo-registreringsplan er implementert. Egen tilgangsplugin er fjernet. Agentgrensen er testet i ny sandbox mot en syntetisk Logseq-tjeneste. Full ekstern aktivering og ende-til-ende-test gjenstår. Installert launcher er ikke automatisk oppdatert. Se [MCP.md](MCP.md).

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

`oc.py` gir én inngang for prosjektoppstart og eksisterende miljøer:

```sh
python3 ~/.local/share/opencode-sbx/launcher/oc.py           # Meny med navn, status og prosjekt
python3 ~/.local/share/opencode-sbx/launcher/oc.py .         # Opprett eller gjenåpne prosjektmiljø
python3 ~/.local/share/opencode-sbx/launcher/oc.py list
python3 ~/.local/share/opencode-sbx/launcher/oc.py open NAVN
python3 ~/.local/share/opencode-sbx/launcher/oc.py shell NAVN
python3 ~/.local/share/opencode-sbx/launcher/oc.py stop NAVN
python3 ~/.local/share/opencode-sbx/launcher/oc.py capabilities .
```

Kortkommandoen `oc` installeres ikke av scriptet. Den er lagt inn separat i brukerens dotfiles etter godkjenning. For gjeldende zsh-økt kan du definere:

```sh
oc() { python3 "$HOME/.local/share/opencode-sbx/launcher/oc.py" "$@"; }
```

Deretter er `oc`, `oc .`, `oc list`, `oc open NAVN`, `oc shell NAVN` og `oc stop NAVN` tilstrekkelig. Permanent shelloppsett gjøres separat i dotfiles etter godkjenning.

- Menyen lar deg velge miljø, så åpne OpenCode med Enter, terminal med `t` eller stoppe med `s`. `q` avbryter.
- I et Git-repo bruker `oc .` repo-roten som skrivbar mount og stabil sandboxidentitet, også når du står i en undermappe. Valgt undermappe beholdes som startkatalog. Et nestet repo bruker sin egen rot. Utenfor Git brukes mappen du oppgir.
- Git-roten kan ikke være hjemmemappen eller filsystemroten. Git-feil avbryter oppstarten. Arvede `GIT_*`-overstyringer ignoreres ved prosjektoppdagelse.
- Koblede worktrees, submoduler og andre repoer med Git-metadata utenfor prosjektroten avvises foreløpig ved prosjektoppstart. Ingen ekstra mount legges til, og worktrees slås aldri sammen med hovedrepoets miljø. Støtte krever egen mountavklaring.
- `oc shell NAVN` åpner zsh som `agent` i prosjektmappen, i gjeldende terminal. Utelat navnet for å velge fra menyen. Sandboxen starter ved behov. `exit` avslutter shelløkten; den kan holde sandboxen i gang så lenge den er åpen.
- Prosjektoppstart finner også miljøer med eldre navn. Hvis flere miljøer peker på samme prosjektmappe, må du velge. Uten interaktiv terminal må navnet angis med `--name`.
- Eldre miljøer som bare monterer en undermappe, migreres ikke og velges ikke automatisk som miljø for hele repoet. Bruk `oc open NAVN` for å gjenåpne dem med opprinnelig mount.
- Åpning starter en stoppet sandbox eller kobler en ny OpenCode-klient til samme miljø og historikk. Den garanterer ikke automatisk valg av en bestemt samtale. Separate miljøer krever separate terminalfaner.
- Åpning av et eksisterende miljø utfører ingen credential-registrering, kit-oppgradering eller skill-installasjon. Dette gjør også eldre OpenCode-miljøer tilgjengelige fra menyen.
- Stopp av et kjørende miljø krever bekreftelse og avbryter aktive prosesser. Et allerede stoppet miljø blir stående urørt.
- `open NAVN --dry-run`, `shell NAVN --dry-run` og `stop NAVN --dry-run` viser bare planen. `oc . --dry-run` bruker oppstartsscriptets lesende kontroll.
- `--all-tabs` gjelder åpning/prosjektoppstart. `--setup-only` og `--name` gjelder prosjektoppstart. Bruk `oc project STI` hvis mappenavnet er et reservert kommandonavn.
- Det finnes ingen slettekommando, automatisk oppgradering eller bakgrunnsmodus.

### Nye miljøer med innholdsmounts

`oc . --name NYTT-NAVN` bruker katalogformat 2 til å velge skrivebeskyttede
innholdsmounts. Alle kilder vises før opprettelse. Global hovedagent,
instruksjonsfiler og skill-kilder registreres i det nye miljøet, uten å
overskrive Docker-genererte providers eller global `AGENTS.md`.

Eldre miljøer åpnes uten ettermontering eller innholdsregistrering. Velg
et nytt navn for den nye løsningen. Ved feil under førstegangsoppsett
beholdes miljøet; rett årsaken og velg et nytt navn. Ingen automatisk
reparasjon eller sletting.

Før aktivering kreves en gjennomgått launcher utenfor prosjektmountene:

```sh
# Viser bare kopiplanen. Skriver ingenting.
python3 sbx/install-launcher.py
```

Installasjon med `--apply`, endring av `oc`-funksjonen og endring av privat
vertskatalog krever separat godkjenning. Eksisterende katalogformat 1 kan
fortsatt brukes for lesende lagvalg, men kan ikke opprette innholdsmounts.
`--catalog FIL` velger en eksplisitt katalog ved prosjektoppstart.

### Lesende lagvalg

`oc capabilities` viser hvilke innholdslag prosjektmappen skal få.
Utelatt argument betyr gjeldende mappe. Du kan også oppgi en sti eller et
eksisterende sandboxnavn:

```sh
oc capabilities
oc capabilities /sti/til/prosjekt
oc capabilities opencode-work
```

Den bruker en betrodd vertskatalog i `~/.config/opencode-sbx/catalog.json`.
Katalogen er privat vertskonfigurasjon og skal ikke fylles med credentials.
Bare lokal metadata leses; ingen sandbox startes eller endres.
`--catalog FIL` velger en eksplisitt katalogfil for kontroll.

**Denne kommandoen viser bare forventede lag.** Den installerer ikke
komponenter og beviser ikke at skills, MCP, agenter eller hovedinstruksjoner
er tilgjengelige. Lagvalg aktiverer ikke innholdslevering ved oppstart.

Format og sikkerhetsgrenser står i [CONTENT-MOUNTS.md](CONTENT-MOUNTS.md).

Det opprinnelige oppstartsscriptet kan fortsatt brukes direkte:

`start.py` bruker nøyaktig mappen du oppgir som mount, uten automatisk Git-rot.
Bare `oc.py` utfører den nye prosjektoppdagelsen. Bruk `--workdir UNDERMAPPE`
med `start.py` for en annen startkatalog innenfor den eksplisitte mounten.

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

Scriptet monterer ikke hele `~/Dev` eller hjemmemappen. Direkte bruk uten `--content` krever én skrivbar prosjektmount og begge mixinene. Med `--content` kontrolleres i tillegg nøyaktig de valgte skrivebeskyttede innholdsmountene. Velger du selv en overordnet mappe som prosjekt, blir hele den mappen tilgjengelig. Velg derfor prosjektroten.

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

Dette forener ikke separate sandboxer. Standardoppsettet holder én skrivbar prosjektmappe per sandbox.

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

Installerte programmer, shellhistorikk og OpenCode-data skal overleve stopp og oppstart så lenge sandboxen finnes. I det syntetiske testmiljøet er skills, eierskapsmetadata og en OpenCode-samtale med alle meldinger kontrollert før og etter stopp/start. Dette verifiserer ikke alle datatyper eller gjenoppretting etter sletting.

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
├── oc.py            # Meny, liste, prosjektoppstart, åpning og bekreftet stopp
├── start.py
├── profiles.py      # Privat katalog og lagvalg
├── content.py       # Lesende mountplan og kollisjonskontroll
├── content_runtime.py # Registrering inne i en ny sandbox
├── install-launcher.py # Eksplisitt kopiplan for betrodd launcher
├── personal/       # Shellverktøy, Nord, Powerline og instruksjoner
├── models/         # Berget-oppsett og credential-deklarasjon
├── scripts/        # Miljøkontroll og engangsoverføring av API-nøkler
├── tests/          # Enhetstester uten opprettelse eller sletting av sandboxer
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

- Godkjenne og aktivere vertskatalog, hovedagent, felles instruksjoner og betrodd launcher.
- Verifisere personlig oppsett og alle innholdslag i nye sandboxer.
- Gjennomgå skill-avhengigheter og koble til nødvendige MCP-tjenester.
- Kontrollere den daglige TUI-flyten visuelt i vanlig terminal.

**BØR**

- Avklare hva som skal bevares utenfor de utskiftbare sandboxene.
- Gjennomgå oppdateringsrutine og checksumverifisering av nedlastinger.

**SENERE**

- MCP, først aktuelle tjenester som Browse, med avgrenset transport og autentisering til Macen.
- Funksjonstest av spesialagenter etter at skill- og MCP-avhengighetene er på plass.
- Ollama, som krever en separat vurdering av vertstilgang.

## Kilder

- [Docker Sandboxes: Usage og livsløp](https://docs.docker.com/ai/sandboxes/usage/)
- [Docker Sandboxes: Credentials](https://docs.docker.com/ai/sandboxes/configuration/credentials/)
- [Docker Sandboxes: Author kits](https://docs.docker.com/ai/sandboxes/customize/author/)
- [OpenCode: CLI og bakgrunnstjeneste](https://opencode.ai/docs/cli)
- [OpenCode: Tabs og CLI-innstillinger](https://opencode.ai/docs/cli/config)
- Lokal `sbx`-hjelp og modelltestene oppsummert i `HISTORY.md`.
