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

## Browse gjennom MCP-gateway

- Finn verktøyets eksakte kallsti med search.
- OpenCodes execute har ingen page, browser eller snapshot.
- Send Playwright-koden som en streng til Browse-verktøyet:
  tools["mcp-gateway"].execute({ code: "await page.goto(...); ..." })
- Ikke anta at ekstra parametere som session gjør det ytre
  execute-kallet til et Browse-kall.
