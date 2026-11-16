# Funn fra utprøvingen

Verifisert 16. november 2026 med `sbx` 0.53.0 og OpenCode 2.3.0 på macOS.

## Base og mixiner

- OpenCodes standard-kit leverte Debian 13 ARM64 med bruker `agent` og `/home/agent`.
- Basen hadde Git, curl, GitHub CLI og sudo, men manglet blant annet zsh, Starship, Node og Python.
- `personal/` ble bygget og installert. Kontroll av verktøy, JSON-konfigurasjon og shelloppstart bestod.
- Verifiserte versjoner: zsh 5.9, Starship 1.22.1, Node 20.19.2 og Python 3.13.5.
- Powerline-kilden var identisk med vertens gjennomgåtte plugin ved kopiering.
- `sbx kit validate --offline` kunne ikke validere v3-kilden uten kit-builder. Bygging gjennom `sbx` lyktes.

## ChatGPT

- `opencode-test` ble opprettet før OAuth var registrert i `sbx`.
- Etter registrering viste `sbx inspect` OAuth, men modellkallet feilet med `Missing scopes: api.responses.write`.
- Begge direkte OpenCode-innloggingsforsøkene inne i denne sandboxen feilet. Ingen ChatGPT-konto ble lagret der.
- Nettverkspolicyloggen viste tillatte forespørsler til `auth.openai.com`.
- `opencode-oauth-test` ble opprettet etter OAuth-registrering og bekreftet bruk av lagrede OAuth-credentials.
- GPT-6.1 Sol svarte `OK`. Ingen direkte innlogging i den nye sandboxen var nødvendig.
- Resultatet støtter rekkefølgen OAuth først, opprettelse etterpå. Den nøyaktige årsaken til forskjellen er ikke isolert.

## Samlet modelloppsett

- `models/` ble bygget, men `sbx kit add` avviste installasjon fordi recreate-flyten ikke støtter credential-deklarasjoner.
- Opprettet derfor `opencode-work` med begge mixinene fra starten.
- Engangsscriptet gjenbrukte aktive Anthropic- og Berget-nøkler fra Macens OpenCode og registrerte dem som sandbox-avgrensede secrets.
- GPT-6.1 Sol, Claude Opus 5.5 og Bergets GLM-5.3 Flash svarte alle `OK` i `opencode-work`.
- Første Anthropic-kall under parallelle oppstarter feilet før serveren var klar. Et sekvensielt forsøk lyktes. Årsaken er ikke isolert.
- Brukeren rapporterte at arbeidsmiljøet så ut til å fungere bra.

## Nyopprettelse, skills og persistens

- Opprettet en ny `oc-skills-integration` gjennom `start.py --setup-only`, med pseudo-terminal og bekreftelse på scriptets eget spørsmål. Begge mixinene og engangsoverføring av manglende modellsecrets fungerte.
- Bare et syntetisk testprosjekt er montert. Ingen eksisterende sandboxer ble endret.
- Miljøkontrollen bestod. En separat personlig skill-pilot installerte en versjonslåst skill uten ekstra mounts.
- OpenCodes API oppdaget personlig og prosjektlokal skill med forventede kildebaner. GPT-6.1 Sol lastet begge via `skill`, uten andre verktøy, og ga forventet syntetisk resultat.
- Midlertidig prosjektlokal navnekollisjon avviste både installasjon og kontroll. Prosjektfil, installert skill og eierskapsmetadata var uendret.
- Etter bekreftet stopp startet filkontrollen samme miljø igjen. Skills, eierskapsmetadata, OpenCode-samtalens metadata og alle meldinger var bevart. Gjentatt installasjon var uendret.
- `sbx inspect` rapporterer tilstand som `state`; `sbx ls --format json` bruker `status`.
- Integrasjonstestene er manuelt orkestrert. De inngår ikke i enhetstestene eller CI. Generell skill-integrering og støttet installerkontrakt gjenstår.

## Enkel daglig betjening

- `oc.py` tilbyr miljømeny, prosjektoppstart, liste, åpning, terminal og bekreftet stopp.
- Prosjektoppslag gjenbruker også eldre navn. Flere treff krever et eksplisitt valg. Opprettelse delegeres til `start.py`.
- 42 enhetstester består, inkludert eksisterende oppstarts- og modelltester.
- Ekte lesende oppslag og prosjektplan bestod. `open` startet OpenCode i pseudo-terminal med alternativ skjerm; Ctrl+C ga exitkode 0. Dette erstatter ikke visuell kontroll i vanlig terminal.
- TUI-en viste Qwen4 Max/OpenRouter som standardmodell i det nye miljøet. Vi endret ikke dette automatisk. GPT-6.1 Sol er eksplisitt funksjonstestet; standardmodellens tilgang er ikke testet.
- Bekreftet `stop` avsluttet bare testsandboxen og beholdt miljøet. Den er stoppet.
- Kortkommandoen `oc` er lagt til separat i dotfiles etter brukerens godkjenning. Ingen permanent bakgrunnsmodus eller slettekommando er lagt til.

## Beholdte miljøer

- `oc-skills-integration` beholdes som stoppet testmiljø.
- `opencode-work` er arbeidsmiljøet for `mac-setup`.
- `opencode-test` og `opencode-oauth-test` er beholdt som testmiljøer.
- Eksisterende `opencode-Solea` ble ikke endret.
- Ingen sandboxer er slettet som del av denne arbeidsflyten.
