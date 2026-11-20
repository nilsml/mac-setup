# Arbeidsmiljø

- Du kjører i en Linux-sandbox med egen hjemmekatalog.
- Bare eksplisitte mounts gir tilgang til vertens filer. Endringer gjennom
  skrivbare mounts påvirker verten.
- Innholdsmounts er skrivebeskyttet gjennom sine monteringsstier. Dersom samme
  kilde også inngår i prosjektmounten, kan den endres gjennom prosjektstien.
- Personlige grunninstruksjoner og agenter leveres separat fra innholdsmountene.
- Kontroller faktisk verktøy- og tilkoblingsstatus før du lover tilgang til en
  tjeneste. En skill eller agentdefinisjon oppretter ingen MCP-tilkobling.
- Ikke les eller endre hemmeligheter eller forsøk å omgå sandboxens avgrensninger.

## Jira og Confluence

- Bruk twg CLI og twg-skillene for Jira, Confluence og annen Atlassian-kontekst.
- Hvis twg ikke er innlogget, be brukeren kjøre `twg login` i sandboxens terminal
  (`oc shell NAVN`). Ikke start innloggingen selv.
- Rovo bak mcp-gateway er bare reserve når brukeren ber om det.

## Browse gjennom MCP-gateway

- Finn verktøyets eksakte kallsti med search.
- OpenCodes execute har ingen page, browser eller snapshot.
- Send Playwright-koden som en streng til Browse-verktøyet:
  tools["mcp-gateway"].execute({ code: "await page.goto(...); ..." })
- Ikke anta at ekstra parametere som session gjør det ytre
  execute-kallet til et Browse-kall.
