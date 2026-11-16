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

## Beholdte miljøer

- `opencode-work` er arbeidsmiljøet for `mac-setup`.
- `opencode-test` og `opencode-oauth-test` er beholdt som testmiljøer.
- Eksisterende `opencode-Solea` ble ikke endret.
- Ingen sandboxer er slettet som del av denne arbeidsflyten.
