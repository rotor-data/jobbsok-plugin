# Steg 1 – Intervjuförberedelse

Börja med det praktiska (block A) så att inget glöms, och fråga sedan hur mycket tid hon har. Har hon en kväll: gör B, D och E. Har hon flera dagar: allt.

## A. Praktiskt

Fråga en sak i taget och spara i `intervju.json` → `omgangar[n]`:
- datum och tid, plats eller videolänk, format (`plats|video|telefon`),
- vem hon träffar (namn och roll; inget mer om dem),
- restid till platsen jämfört med `hårda_gränser.max_pendling_min` (en intervju är ett bra tillfälle att prova resvägen i rusningstid; säg det),
- vad hon ska ta med (id-handling bara om de bett om det, betyg, arbetsprov).

## B. Troliga frågor med STAR-svar

Ta fram 6–10 troliga frågor ur, i den här ordningen:
1. `analys.json` → `krav` med `typ: ska` (en kompetensfråga per tungt krav),
2. luckorna (`lucka: true`), som alltid kommer upp,
3. det hon skrivit i brevet (de frågar om det de läst),
4. standardfrågorna: berätta om dig själv, varför oss, varför nu, svårt samarbete, misstag, styrkor och svagheter,
5. **"Beskriv din ledarstil"** (eller "hur leder du utan mandat?"), alltid.

För varje fråga: ett svar i **STAR** (situation, uppgift, handling, resultat) byggt på **en** merit. Skriv i stödord, inte manus; hon ska kunna säga det med egna ord på 60–90 sekunder.
- `kalla` = merit-id. Resultatet får bara innehålla meritens egna `siffror`.
- Finns ingen merit som passar: sätt `status: "saknar_exempel"` och hjälp henne hitta ett med faktabankens intervjuteknik (`skills/faktabank/references/intervju.md`): "När var du senast …?", "Vad gjorde du konkret?", "Hur märktes det efteråt?". Lägg in det nya i fakta.json först, sedan i svaret.

**Ledarstilen** byggs ur `ledarskap_eget`: `informella_exempel` (ett konkret STAR-exempel), `stil_spegel` (hennes ord om hur hon leder), `under_stress` (svaret på "och när det blir stressigt?") och `ansvar_vilja` (svara ärligt om hon inte vill ha personalansvar). Gör inte om hennes ord till ledarskapsjargong. Saknas `ledarskap_eget`: ställ två av frågorna i `docs/research/kultur-ledarskap-evidens.md` avsnitt 2a och spara svaren (be coachen ta resten senare). Kolla `aldrig_pastaa`: står där att hon inte haft formellt personalansvar, får svaret aldrig antyda det.

**Luckorna**: varje lucka får ett svar i tre delar: säg rakt att hon inte gjort just det, närmaste erfarenhet (med merit), och hur hon skulle lära sig (konkret, inte "jag lär mig snabbt"). Spara i `lucka_hantering`.

## C. Frågor hon ställer till dem (5–8, prioriterade)

Målet är att få reda på det hennes trivsel hänger på, inte att verka intresserad. Be om exempel, inte värderingar ("Berätta om senast …").

Källor, i prioritetsordning:
1. **Varningssignaler** (`preferenser.json` → `varningssignaler`, `ledarskap_behov.aldrig_igen`): en fråga som skulle avslöja varje signal.
2. **Hennes topp i Q-sorten** (`kultur_profil.ideal.topp` / `kultur_ideal`) och de tre största glappen mot senaste jobbet: en fråga per sats som testar just den.
3. **Krav på chefen** (`ledarskap_krav`, `ledarskap_behov`: avstämningsfrekvens, autonomistöd, psykologisk trygghet).
4. **Det som är okänt i arbetsgivarkortet** (tomma fält, `sakerhet: lag`, `fragor_att_stalla`).
5. Arbetsdagens textur ("Hur ser en vanlig vecka ut, möte för möte?") om rollkortet inte redan svarar.

Utgå från frågebanken i `docs/research/kultur-ledarskap-evidens.md` avsnitt 4 och skriv om till hennes situation. Varje fråga får `testar` (vilken sats, signal eller okänt fält) och `prioritet` 1–8. Föreslå att be om ett samtal med en blivande kollega utan chefen. Ta med `analys.json` → `fragor_till_arbetsgivaren` som inte redan besvarats.

Exempel på koppling (form, inte innehåll): signal "allt ska godkännas i flera led" → "Berätta om en text som publicerades nyligen: vem läste den innan, och hur lång tid tog det?"

## D. Arbetsprov och urvalsfrågor

Står det i `annons.md` (överst, "Urvalsfrågor/arbetsprov") eller i kallelsen: sätt `arbetsprov.forekommer: true` och hjälp henne förbereda:
- Ta reda på formen: skrivprov på plats, hemuppgift, case, presentation. Fråga vad de sagt om tid och bedömning.
- **Hemuppgift eller presentation:** gör en plan (vad som bedöms enligt annonsens krav, disposition, tidsåtgång). Hon skriver själv; du ger feedback. Text som hon lämnar in går genom `antiai.py`, och påståenden om henne genom faktabanken. Du skriver aldrig arbetsprovet åt henne.
- **Skrivprov på plats:** öva en gång med en uppgift i samma genre (t.ex. för IVO: skriv om ett stycke myndighetstext i klarspråk på 20 minuter), och ge feedback mot annonsens krav.
- **Urvalsfrågor i formulär:** svar på högst 150 ord per fråga, ett belagt exempel var, via skrivlagret i `skills/ansokan/references/` (connector eller `fallback-prompt.md`).

## E. Övningsläge

Erbjud: "Vill du att jag spelar intervjuare en stund?" Ställ en fråga i taget, de 3–5 viktigaste (en lucka och ledarstilen ska vara med). Efter hennes svar: en sak som var bra (konkret), en sak att skärpa (konkret), och om svaret hade STAR-delarna och ett resultat. Ingen poängsättning. Föreslå en ny formulering bara om hon ber om det. Avsluta efter 5 frågor eller när hon vill. Spara kort i `ovning`.

## F. Tackmejl (utkast, hon skickar)

`tackmejl.md`, att skicka samma dag eller dagen efter: 3–4 meningar till den hon träffade. Tacka konkret för något som sades, en mening som knyter an till rollen med en riktig merit, och svar på något hon inte hann säga om det finns. Samma regler som följemejlet i `skills/ansokan/references/brev-och-mejl.md` (ton, inga klyschor). Skriv det klart **efter** debriefen (steg 2), med det som faktiskt sades; före intervjun bara en mall. Kör `antiai.py`.

## intervju.md

Hennes fusklapp, högst två sidor:

```markdown
# Intervju: <roll>, <bolag>
**När:** <datum tid> · **Var:** <plats/länk> · **Träffar:** <namn, roll>
**Ta med:** …

## Din vinkel (en mening)
## Troliga frågor (stödord i STAR)
## Ledarstil
## Om luckorna
## Dina frågor (i prioritetsordning)
## Arbetsprov (om det finns)
## Efteråt: tackmejl samma dag, och berätta för mig hur det gick
```

## Spara

`intervju.json` enligt datakontraktet, `intervju.md`, `tackmejl.md`. Validera intervju.json. Sätt `logg.json` → `status: "intervju"` om det inte redan är gjort, och en anteckning med datum.
