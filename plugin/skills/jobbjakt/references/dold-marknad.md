# Dolda marknaden – bara utkast, aldrig autoskick

En del tjänster tillsätts utan annons eller innan annonsen syns. Siffran "70–80 %" är dåligt belagd; säg "en betydande andel".

## Underlag
- **Målbolag:** `jakt_arbetsgivare.py region` / `likar`, `malbolag.py`, bolag hon själv nämnt.
- **Signaler:** `jakt_signaler.py --bolag "<målbolag>" ... [--fran-kallor] [--nya]`. Cision (tillåtet) och bolagens egna pressrums-RSS (robots.txt kontrolleras). MFN läses inte: robots.txt förbjuder.
- **Karriärsidor utan flöde:** registreras som pagehash via `kalla_lagg_till.py` (efter ja).

## Steg
1. Välj högst 3 målbolag per körning där både passform (värden, arbetsdag) och ett skäl finns: en signal, återkommande rekrytering av hennes yrke, eller en person hon känner.
2. Föreslå **kontaktväg**, i den ordningen: någon hon känner (fråga henne), rekryterande chef eller kommunikationschef som nämns i pressmeddelande eller på bolagets webb, bolagets allmänna rekryteringsadress. Hämta inga personuppgifter från LinkedIn; föreslå i stället att hon själv tittar där.
3. Skriv **utkast** (med skillen ansokan för ton och fakta, källa per påstående ur fakta.json):
   - kort kontaktmejl (5–7 meningar): varför just de, varför nu (signalen, med källa), vad hon kan bidra med (1–2 meriter), en enkel fråga (15 minuter, ett samtal).
   - eller spontanansökan om de har en sådan kanal.
   Spara som `ansokningar/<YYYY-MM-DD>-<bolag>-spontan/mejl.md` med status `utkast` i `logg.json`.
4. Säg tydligt: "Det här är ett utkast. Jag skickar ingenting – du bestämmer om och när."
5. Spara spåret (`typ dold_marknad`) och logga körningen. Följ upp om två veckor om hon skickat.

## Aldrig
- Skicka mejl, kontaktförfrågningar eller formulär.
- Hitta på kontaktpersoner eller påstå något om bolaget utan källa.
- Skrapa LinkedIn, Indeed eller MFN.
