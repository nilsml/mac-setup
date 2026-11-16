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

## Innholdslag: lesende grunnlag

- `profiles.py` velger lag fra en privat vertskatalog. `oc capabilities`
  viser forventet lagsett for en prosjektsti eller et eksisterende miljø.
- Repoavgrensning krever både riktig oppløst repo-rot og forventet lokalt
  konfigurert origin. Et mappenavn alene er ikke tilstrekkelig.
- Kontroller mot faktiske personlige mapper, arbeidsrot, arbeidsprosjekter,
  det avtalte produktrepoet og en undermappe bestod. Et eksisterende
  sandboxnavn ble også kontrollert med bare metadataoppslag.
- 61 enhetstester består. Nye tester dekker blant annet stiavgrensning,
  symlinker, feil repoidentitet, nestet repo, Git-miljøvariabler og
  credential-lignende verdier i katalogen.
- Vertskatalogen er lagt inn separat i dotfiles etter godkjenning. Bare
  katalogfilen tillates i Git; andre filer i samme configmappe ignoreres.
- Dette velger ikke komponentversjoner og installerer ingen skills,
  hovedinstruksjoner, MCP-servere eller agenter. Oppstartsadferden er uendret.
- Utkastet til en felles, versjonslåst profilkontrakt ble senere erstattet
  av levende innholdsmounts. Se `CONTENT-MOUNTS.md`.

## Prosjektidentitet fra Git-roten

- Etter godkjent atferdsutkast bruker prosjektoppstart i `oc.py` Git-roten
  som mount og sandboxidentitet. Valgt undermappe sendes til `start.py`
  med `--workdir`. Direkte bruk av `start.py` er uendret.
- Nestede repoer bruker innerste rot. Utenfor Git brukes valgt mappe.
  Arvede `GIT_*`-overstyringer ignoreres, og Git-feil avbryter oppstart.
- Koblede worktrees, submoduler og andre repoer med ekstern Git-metadata
  avvises ved prosjektoppstart. Ingen ekstra mounts eller automatisk
  sammenslåing med hovedrepoet innføres.
- Eldre navn med samme rotmount gjenbrukes. Flere treff krever valg.
  Eldre undermappemounts migreres ikke og kan fortsatt åpnes med `open NAVN`.
- 77 tester består. De 16 nye testene dekker prosjektoppdagelse og delegering,
  inkludert ekte lokale Git-repoer, koblet worktree, symlinker, mellomrom
  i stier, ugyldig metadata og overstyrt Git-miljø.
- Faktiske `--dry-run`-kontroller fra repo-roten og en undermappe valgte samme
  eksisterende miljø med riktig startkatalog. Kontroll utenfor Git beholdt
  valgt mappe. Ingen sandbox ble startet eller endret av kontrollene.
- `git diff --check` består. Funksjonstest av faktisk TUI-oppstart fra
  undermappen er ikke kjørt i denne delen av arbeidet.

## Levende innhold i nye, utskiftbare sandboxer

- Brukeren valgte skrivebeskyttede arbeidsmapper fremfor pins, profilpakker
  og ettermontering. Gamle miljøer skal ikke migreres eller gjenskapes.
- `content.py` planlegger mounts og kontrollerer relative stier,
  remappbare symlinker og kjente agent- og skill-kollisjoner. Format 2 i
  vertskatalogen binder eksisterende ruter til innholdskilder.
- `oc.py` sender `--content` ved prosjektoppstart. `start.py` bruker sbx
  sine posisjonelle ekstra arbeidsområder med `KILDE:MÅL:ro`.
  Eksisterende eldre miljøer gjenåpnes uten innholds- eller credentialendring.
- `content_runtime.py` registrerer skill- og instruksjonsstier, global
  agentlenke og standardagent. Providers, Docker-generert `AGENTS.md` og
  øvrige innstillinger bevares. Konflikter stopper oppsettet.
- `install-launcher.py` viser en eksplisitt kopiplan for gjennomgått kode
  utenfor prosjektmountene. Ingen installasjon eller shellendring er utført.
- Den kopierte miljøinstruksjonen inneholder nå bare sandboxregler,
  uten dupliserte personlige regler eller påstander om MCP-status.
- 125 tester består. Offentlig dokumentasjon bruker syntetiske kilder.
  Personlig katalog og nml-agentinnhold er fortsatt ikke endret eller aktivert.
- En ny syntetisk testsandbox bekreftet faktisk mountmetadata, lesing,
  avvist skriving med errno 30, bevart providerdel og oppdagelse av
  `main`, `reviewer` og `synthetic-check` i OpenCode.
- Tre modellsteg med GPT-6.1 Terra uten reasoning bekreftet første sesjons
  standardagent, fellesinstruksjoner, faktisk skill-lasting etter
  kildeoppdatering uten reinstallasjon, og agentbytte i en annen sesjon
  med bevart modell og fellesinstruksjoner. Den andre sesjonen fikk ingen
  modellrunde med standardagenten før byttet; dette delkravet er utestet.
- Modell- og mounttestene brukte bare syntetisk innhold. Testsandboxen er
  stoppet og beholdt. Ingen eksisterende miljøer ble endret.
- Ekte test brukte `sbx create` og runtime direkte. Hele
  `start.py --setup-only` med credential-registrering er enhetstestet,
  men ikke kjørt ende til ende i denne delen.
- Vertskatalog, nml-hovedagent, fellesinstruksjoner og launcherinstallasjon
  krever fortsatt konkret godkjenning før skriving utenfor prosjektet.

## Godkjent personlig aktivering

- Brukeren godkjente konkret hovedagentutkast, kopi av fellesinstruksjoner,
  katalogformat 2, installert launcher og endret shellfunksjon.
- De godkjente kildefilene er opprettet i det private innholdsrepoet.
  Hovedagenten låser ingen modell. Macens eksisterende grunninstruksjoner
  og agentdefinisjoner er beholdt.
- Vertskatalogen har fortsatt samme scopes og avhengigheter. Bare
  formatversjonen og eksplisitte innholdskilder er endret.
- De 20 eksplisitte launcher- og kitfilene er installert utenfor
  prosjektmountene. Shellfunksjonen peker på denne kopien.
- Ingen sandboxer er startet eller endret i aktiveringsdelen. Fysisk test
  av det personlige oppsettet i en ny sandbox gjenstår; tidligere
  funksjonstester brukte syntetisk innhold.
- Ingen commit eller push er utført.
- Lesende aktiveringskontroll bekreftet identiske installerte filer og
  grunninstruksjoner, forventet ruting for personlige mapper, arbeidsrot,
  skill-repoer, produktrepo og undermappe, uten kjente navnekollisjoner.
  Shellsyntaks, diffkontroll og alle 125 tester bestod.
