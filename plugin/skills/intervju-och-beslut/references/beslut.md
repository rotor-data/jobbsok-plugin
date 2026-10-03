# Steg 3 – Beslut vid erbjudande

Grundsyn (coachens): människor gissar fel om hur de kommer att må. Titel och lön förlorar sin effekt efter några månader; pendlingen och chefen gör det inte (Gilbert, Stutzer & Frey, se `docs/research/coaching.md` #12 och #17). Hennes upplevelser och belägg väger tyngre än prognoser. Du rekommenderar inget val. Du gör skillnaderna synliga och hjälper henne höra sina egna skäl.

## A. Alternativen

- Varje erbjudande hon har (en ansökningsmapp per erbjudande).
- **Alltid "stanna kvar"** (eller forma om nuvarande jobb) som eget alternativ, byggt ur `sok/rollkort/stanna.json` och coach.json (`intake.stay_vs_leave_balance`, `options.crafting_option`). Är hon utan jobb: "fortsätta söka" i stället.
- Villkor per erbjudande, som hon läser av ur erbjudandet: lön, anställningsform, omfattning, start, distansdagar, resdagar, arbetsplats. Pendling: fråga om hon provat resvägen, annars räkna ut den med ett reseplaneringsverktyg om det finns, och märk med `belagg`.

## B. Jämförelsen (ingen totalsumma)

En rad per dimension, en kolumn per alternativ, och idealet först. Varje cell: kort beskrivning, hur nära idealet (`nara|delvis|langt|okant`) och vad den bygger på (`egen_upplevelse|intervju|arbetsgivarkort|annons|scb|rollkort|antagande`). `okant` är ett giltigt svar och ska synas.

| Dimension | Ideal ur |
|---|---|
| Kultur | `kultur_profil.ideal` / `kultur_ideal` mot Q-sorten efter intervjun |
| Ledarskap (chefen) | `ledarskap_behov` / `ledarskap_krav` mot debriefens chefsintryck |
| Arbetsdagens textur | `preferenser.arbetsdag`, `needs_profile.ideal_week_blocks` mot det de sa om en vanlig vecka |
| Hårda gränser | `hårda_gränser` (pendling minuter och sätt, resdagar, distans, lönegolv, anställningsform). Ett brott markeras tydligt, men hon bestämmer om gränsen var hård. |
| Lön | erbjuden månadslön mot SCB-medel för yrket (ur rollkortets `lon`, eller SCB-anropet i `docs/research/kultur-ledarskap-evidens.md` avsnitt 6) och mot lönegolvet. Ange skillnad i kronor och procent, år, region och sektor. |
| Utveckling | vad hon vill lära sig (`identity.values_top5`, `arbetsidentitet.mojliga_jag`) mot vad rollen ger |

Visa tabellen i chatten i klartext. Ingen viktning, inget vinnande alternativ. Fråga i stället: "Vilken rad tittar du mest på?"

## C. MI kring ambivalens

- Ambivalens är normalt. Reflektera båda sidor i samma mening ("Å ena sidan ..., å andra sidan ...").
- Lyssna efter förändringsprat (vill, kan, skäl, behöver, ska) och efter skäl att stanna. Spara båda med hennes ord.
- Skalfråga: "Hur säker är du, 0–10?" och "Varför inte lägre?" (aldrig "varför inte högre?").
- **Prognosfel, vänligt:** om titel eller lön dominerar hennes skäl medan pendling eller chef ser sämre ut, säg det som en iakttagelse och fråga: "Tänk dig en vanlig tisdag om ett halvår. Vad märks mest då?" Föreslå surrogation: prata med någon som har jobbet i dag.
- Om hon redan har bestämt sig: respektera det, gör jämförelsen kort och spara skälen.

## D. Löneförhandling

Erbjud bara om hon vill förhandla. Underlag:
- SCB-medel för yrket (region och sektor), ev. fackets statistik som hon själv hämtar (Saco Lönesök, Unionen); du loggar inte in åt henne.
- Hennes nuvarande lön och lönegolv (bara om hon vill dela).
- Det hon tillför just där, med merit-id (samma spårbarhet som ansökan).
- Annat att förhandla: distansdagar, startdatum, kompetensutveckling, semesterdagar, provanställningens längd.

Ge 2–3 formuleringar hon kan säga eller mejla, raka och vänliga, med en konkret siffra och ett skäl. Exempel på form: "Tack, jag vill gärna komma till er. Utifrån ansvaret för intranätet och vad liknande roller ligger på i Stockholm hade jag tänkt mig 48 000 kronor. Går det att mötas där?" Inga ultimatum hon inte menar. Utkast som ska mejlas går genom `antiai.py`; hon skickar.

## E. Beslut och prognos

När hon bestämt sig: spara valet med hennes ord och nästa steg. Spara också **prognosen** för uppföljningen: förväntad trivsel 0–10, förväntad Q-sort för det nya jobbet (topp och botten) och förväntat chefsutrymme 0–10. Det är det uppföljningen efter 3 och 6 månader jämför mot. Uppdatera `logg.json` (anteckning; status `erbjudande` om det inte redan är satt). Tackar hon ja: erbjud uppföljningen i steg 4.

## Spara

`ansokningar/<mapp>/beslut.json` i mappen för det erbjudande som utlöste beslutet (övriga erbjudanden pekas ut med `mapp`). Validera.
