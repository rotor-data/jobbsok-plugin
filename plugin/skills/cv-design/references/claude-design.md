# Designa själv i Claude Design

Hon designar. Du planerar med henne, paketerar hennes innehåll och gör designen till en mall som fylls per jobb. Samtalsregler: en fråga i taget, korta meddelanden, inga tekniska ord.

Claude Design (claude.ai/design) är en research preview. Den kan importera ett designsystem, ta emot filer, redigera direkt på ytan och exportera till PDF, PPTX, fristående HTML och zip. Den har ingen funktion för datamallar; det är därför vi lägger platserna för innehållet som attribut i HTML:en (`slots.md`).

---

## 1. Brief (5 minuter)

En fråga i taget. Skriv svaren till `<home>/design/brief.md` med hennes egna ord, eftersom briefen följer med in i Claude Design.

1. **Mottagare.** "Vilka kommer att läsa ditt CV, ungefär? Tänk bransch och typ av arbetsplats."
2. **Känsla i tre ord.** "Om någon bläddrar fram ditt CV i en hög, vilka tre ord vill du att de tänker?"
3. **Foto.** "Vill du ha med ett foto? I Sverige är det valfritt." Ja: be om en bild med neutral bakgrund och spara som `<home>/profil/foto.jpg`.
4. **Förebilder.** "Har du sett något CV du gillade? Vad var det i det?"
5. **Varianter.** "Söker du till olika slags arbetsplatser, till exempel både myndigheter och byråer? Då kan du göra två–tre varianter av samma design: en stram, en standard och en lite friare. Det väljs sedan automatiskt per jobb."

Mall för `brief.md`:

```markdown
- Läsare: mest offentlig sektor, ibland kommunikationsbyråer
- Känsla: lugn, saklig, varm
- Foto: nej
- Gillade: luften i ett CV hon sett, namnet stort men inte skrikigt
- Varianter: stram (myndighet), standard, kreativ (byrå/kultur)
```

## 2. Regler och "gör inte" (2 minuter)

Säg kort vilka ramar som gäller och varför, i två–tre meningar. Exempel:

> "Några saker ligger fast så att CV:t går att läsa både för människor och för de system många arbetsgivare sorterar med: text minst 9 punkt (helst 10–11), högst två typsnitt, en accentfärg, en kolumn eller en smal kolumn vid sidan, inga tabeller och ingen text i bilder. Allt det står i instruktionen du klistrar in, så Claude Design håller koll på det också."

Detaljerna står i `typografi.md`. Instruktionen i paketet (`README-for-claude-design.md`) innehåller briefen, reglerna och "gör inte"-listan.

## 3. Paketet

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_export.py" "<cv.json eller ansökningsmapp>" --home "<home>"
```

Svaret har `zip`, `mapp`, `instruktion` och `komponenter`. Paketet innehåller:

- `cv-exempel.html` och `brev-exempel.html`: hennes riktiga innehåll med platserna markerade
- `komponenter/`: sidhuvud, sektion, post, punktlista, kompetenslista, sidokolumn och brevhuvud, var och en med `<!-- @dsCard group="CV" -->` överst så att paketet kan importeras som designsystem
- `tokens.css` (färger, typsnitt och mått som variabler), `mall.css`, `fonts/`
- `README-for-claude-design.md`: texten hon klistrar in

`exempelinnehall: true` betyder att faktabanken var tom och exemplet i pluginen användes. Säg det, och bygg hellre `design/underlag/cv.json` först. `brief_saknas: true`: skriv briefen innan hon går vidare.

## 4. Hon designar i Claude Design

Säg ungefär:

> "Nu är paketet klart. Öppna Claude Design, starta ett nytt projekt och ladda upp zip-filen (eller importera den som designsystem). Klistra in texten från instruktionsfilen som första meddelande. Sedan kan du ändra fritt: be om andra färger, flytta saker, prova en smal kolumn. Det viktiga är att platserna för innehållet finns kvar, och det vet Claude Design genom instruktionen. När du är nöjd, exportera som fristående HTML eller zip och ge mig filen."

Varianter: "Gör en sida per variant, till exempel stram, standard och kreativ, och exportera dem. Varje sida blir en variant här."

**Valfritt: DesignSync.** Har sessionen verktyget DesignSync (startas med `/design-sync`) kan paketet synkas direkt till ett designsystem-projekt på claude.ai/design, och hennes ändringar hämtas tillbaka på samma sätt. Använd det bara om verktyget faktiskt finns i sessionen och hon vill. Uppladdning och export fungerar alltid och är huvudvägen.

## 5. Import

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_import.py" "<exporterad.html eller .zip>" --namn "<namn>" --home "<home>"
```

- Platser som finns kvar behålls. Där de försvunnit matchas elementen mot hennes innehåll (namn, titlar, rubriker, punkter). Upprepade element (roller, punkter) blir en mall som upprepas.
- `osakert` listar det som inte gick att avgöra. **Fråga henne om varje punkt**, med vanliga ord: "Jag hittade inte datumen för dina roller i designen. Vill du att de ska synas? Då kan du be Claude Design lägga till dem." Ändra inte hennes design på egen hand.
- `hittat` listar det som hittades. `varningar` gäller bilder och typsnitt som inte gick att hämta (utan nät används systemtypsnitt).
- `tokens_fran_design`: färger och typsnitt som hon ändrat i Claude Design förs över till designen.
- `andra_sidor`: zip-filen hade fler sidor (till exempel brevet eller varianter). Importera dem med `--sida <fil>` och `--brev` eller `--variant`.
- Mallen sparas i `<home>/design/mallar/<namn>/` med versioner; en ny import med samma namn blir nästa version.

## 6. Kontroll

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mall_kontroll.py" "<namn>" --home "<home>"
```

Rendera med kort och långt CV, svenska och engelska, med och utan foto, plus brevet. `rapport` är en färdig svensk sammanfattning. Titta på bilderna (`fall[].bild`) själv först och visa sedan jämförelsesidan.

- `blockerar: true`: innehåll försvinner eller PDF:en går inte att läsa. Säg vad som saknas och be henne ändra i Claude Design (ofta har en lista eller ett datumfält tagits bort). Importera igen och kör kontrollen på nytt.
- `problem`: råd, inte stopp. Säg dem vänligt: "Datumen är 8 punkt, och det blir svårläst utskrivet. Be gärna Claude Design göra dem 9–10 punkt."
- `forslag`: bra att veta, till exempel att ett mycket långt CV blir tre sidor.

## 7. Användning och varianter

När kontrollen är ren renderas alla nya ansökningar med hennes mall: `render.py cv <mapp>` läser `design.json.layout = "egen:<namn>"`.

Varianter:

```bash
# en egen sida från Claude Design som variant
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_import.py" stram.html --namn stram --variant stram --home "<home>"
# eller en härledd variant av samma mall (andra färger, ordning, foto)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" variant kreativ farg_accent=#9a4a2f visa_foto=ja --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" variant standard --standard --home "<home>"
```

Skillen `ansokan` väljer variant per jobb och skriver den i `cv.json` → `design_variant`. Hon kan alltid byta.

## 8. Ändra igen

- **Små ändringar** (färg, storlek, ordning på delarna): `design_tool.py set` eller `sektioner`, om mallen använder variablerna från `tokens.css`. Visa före och efter med `--jamfor`.
- **Större ändringar**: kör `design_export.py` igen (paketet visar då standardupplägget med hennes färger), eller be henne öppna sitt projekt i Claude Design igen. Exportera, importera med **samma namn** (ny version) och kör kontrollen.
- **Ångra**: mallens versioner ligger i `mallar/<namn>/versioner/`; designens i `design_tool.py historik` och `aterstall`.
