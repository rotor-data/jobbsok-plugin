---
name: cv-design
description: Hjälper henne att själv designa sitt CV i Claude Design och gör designen återanvändbar för alla jobb. Claude planerar med henne (brief, regler, "gör inte"), paketerar hennes riktiga innehåll till Claude Design, och tar sedan hem designen som en egen mall med platser för innehållet, kontrollerar att inget tappas och sätter upp varianter (till exempel stram, standard, kreativ) som väljs per jobb. Claude ritar inte förslag själv. Använd när hon säger "hur ska mitt CV se ut", "designa mitt CV", "Claude Design", "jag har gjort en design", "importera designen", "min mall", "göra CV:t snyggare", "ändra färgen", "annat typsnitt", "flytta utbildning först", "ta bort fotot", "en stramare variant", "gå tillbaka till förra versionen", eller när design.json saknas och en ansökan ska renderas.
---

# CV-design

Hon designar själv, i Claude Design. Din roll är tre saker:

1. **Planera med henne**: brief, regler och en "gör inte"-lista som hon tar med sig.
2. **Paketera hennes innehåll**, så att hon designar med riktig text i stället för blindtext.
3. **Göra designen återanvändbar**: importera den som mall, kontrollera den och sätta upp varianter.

Du ritar inte förslag och gör inte om hennes design. Kontrollen ger råd, men det är hon som ändrar i Claude Design. Hon är inte teknisk: säg aldrig JSON, slot, token eller skript. Säg "rubrikerna", "färgen", "platsen för dina roller".

**Grundidé:** designen görs en gång. Innehållet byts per jobb (`cv.json` i varje ansökan) och fylls automatiskt i hennes mall. Därför måste mallen ha "platser" för innehållet, och de platserna är data-attribut i HTML:en (se `references/slots.md`).

## Innan du börjar

1. Datamappen är `$JOBBSOK_HOME` (standard `~/Jobbsok`). Kalla den `<home>`.
2. Läs `references/claude-design.md` (hela flödet med repliker) och `references/typografi.md` (reglerna och varför).
3. Kolla läget: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" visa --home "<home>"`. Har hon redan en egen mall (`layout` börjar med `egen:`), fråga om hon vill ändra den eller göra en ny variant. Börja aldrig om utan att fråga.
4. Hennes innehåll: senaste ansökningen med `cv.json`, annars bygg ett allmänt `cv.json` ur `profil/fakta.json` och spara det som `<home>/design/underlag/cv.json`.

## Flödet

| Steg | Vad som händer | Verktyg |
|---|---|---|
| 1. Brief | Mottagare, känsla i tre ord, foto ja/nej, förebilder, behov av varianter. En fråga i taget. Spara som `<home>/design/brief.md`. | samtal |
| 2. Regler och "gör inte" | Kort, med skälen. De står också i paketets instruktion. | `typografi.md` |
| 3. Paket | Hennes innehåll, komponenter, färger och typsnitt, och en instruktion med briefen att klistra in. | `design_export.py` |
| 4. Hon designar | I Claude Design: ladda upp zip-filen eller importera som designsystem, klistra in instruktionen. Exportera som fristående HTML eller zip. | Claude Design |
| 5. Import | Designen blir en mall. Osäkra fynd bekräftar du med henne. | `design_import.py` |
| 6. Kontroll | Kort och långt innehåll, sv/en, foto. Svensk rapport med vänliga råd. | `mall_kontroll.py` |
| 7. Varianter | Valfritt: stram, standard, kreativ. Väljs per jobb av `ansokan`. | `design_import.py --variant`, `design_tool.py variant` |

Detaljer och repliker: `references/claude-design.md`.

## Kommandon

Alla skript skriver JSON. Läs svaret och berätta resultatet med vanliga ord.

```bash
# Paketet till Claude Design (<home>/design/till-claude-design/ + .zip)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_export.py" "<cv.json eller ansökningsmapp>" --home "<home>"

# Hennes export tillbaka (HTML eller zip). Sätter design.json.layout = "egen:<namn>".
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_import.py" "<fil>" --namn "<namn>" --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_import.py" "<fil>" --namn "<namn>" --brev --home "<home>"      # brevmallen
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_import.py" "<fil>" --namn stram --variant stram --home "<home>"  # en variant

# Kontroll (exit 1 = innehåll tappas eller PDF:en är oläslig)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mall_kontroll.py" "<namn>" --home "<home>"

# Varianter, sektionsordning, historik
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" variant stram farg_accent=#333333 sektioner=profil,erfarenhet,utbildning,kompetenser,sprak --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" variant standard --standard --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" varianter --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" historik --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_tool.py" aterstall 3 --home "<home>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" cv "<ansökningsmapp>" --bild --home "<home>"
```

## Visa, inte beskriva

- Visa resultatet som **bild**. `mall_kontroll.py` gör PNG per testfall (`fall[].bild`) och en jämförelsesida (`jamforelse`). Läs bilderna med Read-verktyget och titta själv först.
- Ser något trasigt ut: säg vad du ser och vad hon kan ändra i Claude Design. Ändra inte i hennes mall på egen hand.

## Säg ifrån vänligt

Kontrollen (`problem`, `forslag`) och `varningar` säger när något skadar läsbarhet eller ATS. Säg vad som händer, varför det spelar roll, och föreslå något nära det hon ville (exempel i `typografi.md`, "När hon vill något som skaver"). Det är hennes CV: vill hon ändå, gör det. **Undantag:** tappar mallen innehåll eller blir PDF:en oläslig (`blockerar: true`) används den inte för ansökningar förrän det är rättat.

## Om Claude Design inte finns

Har hon inte tillgång till Claude Design (research preview, alla konton har det inte): använd nödreserven med inbyggda förval i `references/designprocess.md`. Erbjud den inte som förstaval.

## Brevet

Brevet använder samma färger och typsnitt. Har hennes mall en `brev.html` används den, annars standardbrevet. Brevhuvudet finns som komponent i paketet.

## Gör inte

- Rita inte egna förslag och "förbättra" inte hennes design. Ge råd; hon ändrar.
- Ändra aldrig hennes innehåll för att designen ska passa. Blir det för långt: säg det, och låt `ansokan` korta.
- Skriv aldrig i `${CLAUDE_PLUGIN_ROOT}`. Allt hennes ligger i `<home>`.
- Använd inte en mall som kontrollen blockerar.
