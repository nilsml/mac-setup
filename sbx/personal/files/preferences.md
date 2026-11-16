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
