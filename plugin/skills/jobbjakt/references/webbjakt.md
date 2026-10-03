# Webbjakt – precisa frågor, inga sidhämtningar

Webbsöket görs av dig med webbsökverktyget. Skriptet `jakt_webbrecept.py` gör frågorna, sparar dem som recept (`sok/webbrecept/<namn>.json`) och gör om svaren till annonser.

## Flöde
1. `jakt_webbrecept.py skapa <namn> --hypotes <id> [--titel ... --ort ...] [--nisch kommunikation,ideellt] [--oppen] [--max-fragor 12]`
   Utan `--titel/--ort` används preferenser.json (riktningar[].sokord, orter[].namn). Nisch väljs ur profilen om du inte anger den; distans läggs till om hon vill jobba på distans minst 3 dagar.
2. `jakt_webbrecept.py visa <namn>` → frågorna, en per rad (`q1: site:teamtailor.com "kommunikatör" "Uppsala"`).
3. Kör frågorna med webbsök, en i taget. Läs bara titel, url och snippet. Hämta inte sidorna.
4. Samla träffarna som JSON: `[{"url":"...","titel":"...","snippet":"...","fraga":"q1"}]`. Ta bara med sådant som ser ut som en enskild annons.
5. `jakt_webbrecept.py normalisera <namn> --ingest < resultat.json`. Skriptet
   - avvisar LinkedIn, Indeed, Glassdoor, Jobbland och MFN (villkor/robots),
   - avvisar list- och startsidor på rekryteringssystemen (kräver annonsmönster i url:en),
   - tar bort utm-parametrar, gissar arbetsgivare ur url:en (Teamtailor-/Varbi-subdomän, Lever/Ashby/Greenhouse-sökväg),
   - matar in via `jakt_hypoteser.py ingest` med `hittad_via` = spårets id och loggar körningen på både recept och spår.
6. Nästa gång: `visa` och kör samma frågor. Recepten är det som gör jakten upprepbar.

## Plattformar (site:)
teamtailor.com, varbi.com, jobs.lever.co, jobs.ashbyhq.com, boards.greenhouse.io (även job-boards.greenhouse.io), jobs.smartrecruiters.com, myworkdayjobs.com, reachmee.com. Standard: teamtailor, varbi, lever, ashby, greenhouse.

## Levande nischsajter (jobbsajter.md, kontrollerat 2026-10-01)
| nisch | sajter |
|---|---|
| kommunikation | sverigeskommunikatorer.se, resume.se, dagensmedia.se |
| ideellt | jobb.arenaopinion.se, arenaide.se |
| startup | thehub.io |
| ingenjor | ingenjorsjobb.se |
| distans | remoteok.com, weworkremotely.com, remotive.com |
| eu | eu-careers.europa.eu |
| bemanning | jobb.jurek.se, wise.se, academicwork.se |

Använd inte: Blocket Jobb (nedlagt), StepStone.se (finns inte), Jobbdirekt, Kulturjobb, Vårdjobb, Techjobs (döda eller nere), Jobbland (stänger ute robotar), Jobbsafari/Jooble/Careerjet (mest dubbletter av Platsbanken). Egen sajt: `--sajt domän.se`.

## Bra frågor
- En titel per fråga, i citattecken. Ort i citattecken eller `("Uppsala" OR "Stockholm")`.
- Hellre `site:varbi.com "kommunikationsstrateg" "Uppsala"` än en lång fråga med många ord.
- `--oppen` ger en fråga per titel utan site:, som utesluter LinkedIn, Indeed och Platsbanken (den har vi redan).
- Ger en fråga noll träffar två gånger: ta bort den (kör `skapa` igen med färre titlar).

## Karriärsidor som dyker upp
En ny arbetsgivare med egen karriärsida är värd mer än en annons. Visa den för henne; efter ja: `kalla_lagg_till.py <karriärsidans url> --namn "<bolag>"` så bevakas den automatiskt framöver.
