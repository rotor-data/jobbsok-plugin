# Skrivlagret via connector (valfritt)

Om Smyra-connectorn finns i ditt Claude-konto används den. Följ verktygens egna instruktioner och anropa dem med de verktygsnamn som står där.

Så här passar den in i ansökan:

- **Upptäckt.** Finns ingen sådan connector, eller svarar den med fel två gånger i rad, skriver du själv enligt `fallback-prompt.md`. Säg det kort till henne ("jag skriver klart själv"). Texter som redan är skrivna behålls.
- **Vad du skickar.** Bara annonsen, vinkeln ur `analys.json`, de meriter hon godkänt i steg 3 (med id först, så att `kalla` kan fyllas efteråt) och gränserna: `aldrig_pastaa`, luckorna och de fasta gränserna i `fallback-prompt.md`. Inga andra uppgifter om henne.
- **Röster.** CV-texterna skrivs alltid i Kims röst (klarspråk). Brevets och mejlets ton väljer hon enligt SKILL.md, steg 5. Spara id för valda röster i `rost.json` och slå upp dem igen om de försvunnit; hårdkoda aldrig id.
- **Design** görs inte i connectorn. CV och brev renderas lokalt av `render.py`.
- **Kontroller.** Allt som kommer tillbaka körs genom `antiai.py` och `sparbarhet.py` (SKILL.md, steg 7), precis som text du skrivit själv. Träffar skrivs om innan något visas för henne som färdigt.
