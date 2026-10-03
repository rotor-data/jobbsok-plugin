# Designprocessen steg för steg

> **Nödreserv.** Huvudvägen är att hon designar själv i Claude Design (`claude-design.md`). Använd den här processen med inbyggda förval bara när hon inte har tillgång till Claude Design, och erbjud den inte som förstaval.

Målet är **en** design som håller för alla framtida ansökningar. Hela processen tar 20–40 minuter och kan pausas mellan stegen. Allt sparas i `<home>/design/`.

Samtalsregler: en fråga i taget, korta meddelanden, visa hellre än beskriv, inga tekniska ord.

---

## Steg 1. Brief (5 minuter)

Fyra frågor, en i taget. Spara svaren i minnet för samtalet. De styr valet av förslag.

1. **Mottagare.** "Vilka kommer att läsa ditt CV, ungefär? Tänk bransch och typ av arbetsplats." Lyssna efter konservativ (myndighet, bank, juridik, vård), neutral (kommun, industri, de flesta tjänstemannajobb) eller kreativ (byrå, media, design, startup).
2. **Känsla i tre ord.** "Om någon bläddrar fram ditt CV i en hög, vilka tre ord vill du att de tänker?" Exempel om hon kör fast: lugn, saklig, varm, modern, stram, personlig, självklar.
3. **Foto.** "Vill du ha med ett foto? I Sverige är det helt valfritt. Det kan göra CV:t personligt, men vissa rekryterare föredrar utan för att minska fördomar." Säger hon ja: be om en bild med neutral bakgrund, axlar och ansikte, och spara den som `<home>/profil/foto.jpg`.
4. **Förebilder.** "Har du sett något CV eller någon mall som du gillade? Visa gärna en bild eller beskriv den." Fråga vad hon gillade i den. Det är ofta en enda sak (färgen, luften, namnet).

Sammanfatta: "Så: mottagare mest inom offentlig sektor, känslan lugn, saklig och varm, inget foto, och du gillade luften i den du visade. Stämmer det?"

## Steg 2. Regler först (2 minuter)

Berätta kort, i två–tre meningar, vilka ramar som gäller och varför. Ingen föreläsning. Exempel:

> "Innan jag visar förslag: några saker ligger fast, för att CV:t ska gå att läsa både för människor och för de system som många arbetsgivare sorterar med. Texten blir 10–11 punkt, högst två typsnitt, en färg som accent och allt vänsterjusterat. Inom de ramarna kan vi göra nästan vad som helst."

Detaljerna finns i `typografi.md`. Ta fram dem bara om hon frågar eller vill något som skaver.

## Steg 3. Tre förslag (10 minuter)

**Välj tre förval** som svarar mot briefen. Alla tre ska vara rimliga. Ett av dem får vara lite modigare.

| Brief | Förslag |
|---|---|
| Konservativ mottagare | konservativ, kompakt, modern |
| Neutral | konservativ, modern, varm |
| Kreativ eller personlig | modern, varm, konservativ |
| Lång erfarenhet (över ca 12 år, många roller) | ta med kompakt |
| Foto: ja | ta med varm (porträtt) |

Förvalen:
- **konservativ** "Lugn klassisk": en kolumn, serifrubriker med linje, petrol.
- **modern** "Modern med sidokolumn": Inter, versala rubriker, kontakt och kompetenser i smal kolumn till höger, blå.
- **varm** "Varm med porträtt": serif, terrakotta, rubriker med accentstreck, plats för foto.
- **kompakt** "Kompakt och tät": datum i egen vänsterspalt, tätare, grön. För mycket innehåll på två sidor.

Justera gärna ett förval direkt efter briefen innan du visar det (till exempel varm utan foto, eller en annan accentfärg som hon nämnt) genom att kopiera förvalet till `<home>/design/forslag/<namn>.json`, ändra där och ange sökvägen i `--forval`.

**Rendera** med hennes riktiga innehåll:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" forslag "<cv.json>" --forval konservativ,modern,varm \
  --out "<home>/design/forslag" --home "<home>"
```

Svaret har `jamforelse` (sidan med alla tre) och per förslag `bild`, `pdf`, `sidor` och `varningar`. **Titta på bilderna själv först.** Visa sedan bilderna (A, B, C) och länka jämförelsesidan.

Fråga om helheten först, inte detaljer: "Vilken känns mest som du, om du bara får titta i tre sekunder?" Sedan: "Är det något i de andra du vill låna?"

**Kombinera.** Hon säger kanske "rubrikerna från B och färgen från A". Utgå från det förslag hon gillade mest:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" init --forval konservativ --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" kombinera --fran modern --tokens rubrik_stil \
  --jamfor "<cv.json>" --home "<home>"
```

Översättning från hennes ord:

| Hon säger | Tokens |
|---|---|
| "rubrikerna" | `rubrik_stil`, `font_rubrik`, `storlek_rubrik_pt` |
| "färgen" | `farg_accent` (ibland även `farg_dampad`) |
| "typsnittet" | `font_brod` och/eller `font_rubrik` |
| "namnet" | `storlek_namn_pt`, `font_rubrik` |
| "luften", "mer andrum" | `sektion_luft_mm`, `radavstand`, `marginal_mm` |
| "upplägget", "kolumnen" | `layout` |

## Steg 4. Finjustering i rundor

Varje runda: en eller ett par ändringar, med före och efter. Bara tokens ändras, aldrig mallen.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" set storlek_namn_pt=27 sektion_luft_mm=7 \
  --anteckning "större namn, mer luft" --jamfor "<cv.json>" --home "<home>"
```

- Använd hennes ord i `--anteckning`. Det blir historiken.
- Visa före- och efterbilden. Fråga: "Bättre, sämre, eller vill du gå längre åt samma håll?"
- Läs `varningar`. Finns en: säg ifrån vänligt enligt `typografi.md`.
- **Högst 3–4 rundor.** Märker du att hon velar fram och tillbaka: "De här två ligger väldigt nära varandra. Båda fungerar. Vill du välja med magkänslan, eller ska vi låta det vila till i morgon?"
- Ångrar hon sig: `design_tool.py historik` och `aterstall <version>`.
- Ordningen på sektionerna: `design_tool.py sektioner profil,erfarenhet,utbildning,kompetenser,sprak,kurser,ideella,referenser`. Utbildning först passar bara om den är nyare och viktigare än erfarenheten.

## Steg 5. Stresstest

Innan designen fryses: visa att den håller för alla jobb.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" stresstest --home "<home>"
```

Det renderar hennes design med ett kort CV, ett långt CV med mycket långa titlar och organisationsnamn, på svenska och engelska, plus personligt brev på båda språken. Rendera också hennes eget innehåll i en lång variant om hon har många roller.

Titta efter, och rätta med tokens om något fallerar:
- **Sidantal:** långt CV högst 2 sidor, brev 1. Blir det 3 med sidokolumn eller porträtt: säg det ("med mycket erfarenhet blir den här designen tre sidor; då kortar vi texten per jobb, eller så tar vi lite mindre luft"). Fältet `problem` listar fynden.
- **Långa titlar:** bryts de snyggt, krockar de med datumet?
- **Sidbrytningar:** ingen rubrik ensam längst ner, ingen post som delas mitt i rubriken.
- **Engelska rubriker:** Experience, Education, Skills syns rätt.
- **Brevet** ser ut att höra ihop med CV:t.

Visa henne en översikt med jämförelsesidan och säg kort vad du kollade.

## Steg 6. Frysning och versioner

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" frys --anteckning "<hennes ord>" --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" namn "Lugn och varm" --home "<home>"
```

Säg: "Nu är designen sparad som version N. Alla ansökningar använder den från och med nu, och du behöver aldrig tänka på den igen. Vill du ändra något senare säger du bara till; de gamla versionerna finns kvar."

Varje `cv.json` har `design_version`. Ändras designen senare renderas nya ansökningar med den nya, medan redan skickade PDF:er ligger kvar som de var.

## Om något inte fungerar

- **Ingen PDF** (`motor: "html"`): Chrome saknas, vanligt i Coworks sandlåda. Visa HTML-filen och läs upp `instruktion` med egna ord: öppna i webbläsaren, Skriv ut, Spara som PDF, A4, utan sidhuvud och sidfot.
- **Ingen bild:** länka `jamforelse.html`, den visar förslagen som inbäddade sidor.
- **Typsnitt saknas:** skriptet varnar och använder systemtypsnitt. Säg att det ser lite annorlunda ut på den här datorn.
- **Fotot hittas inte:** CV:t renderas utan foto och skriptet varnar. Be henne lägga bilden i profilmappen.
