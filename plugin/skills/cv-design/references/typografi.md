# Typografi och ATS – reglerna och varför

Läs före steg 2 i designprocessen. Reglerna kommer från `docs/research/cv-och-plugin.md` och etablerad typografi. `render.py` kontrollerar dem och lägger varningar i `varningar`.

## Reglerna

| Regel | Värde | Token | Varför |
|---|---|---|---|
| Brödtext | 10–11,5 pt | `storlek_brod_pt` | Mindre blir svårläst utskrivet och på mobil. Större ser ut som utfyllnad. |
| Rubriker | 11–16 pt | `storlek_rubrik_pt` | Tydlig hierarki utan att skrika. |
| Namn | 20–30 pt | `storlek_namn_pt` | Ska synas först, men inte ta en tredjedel av sidan. |
| Radavstånd | 1,2–1,45 | `radavstand` | Tätare blir en vägg, glesare splittrar punkterna. |
| Marginaler | 15–20 mm | `marginal_mm` | Under 15 mm ser trångt ut och kan klippas vid utskrift. |
| Luft mellan sektioner | 3–9 mm | `sektion_luft_mm` | Gör delarna skumbara. |
| Typsnitt | högst två, helst en familj | `font_rubrik`, `font_brod` | Fler blir rörigt. |
| Färg | en accentfärg, mörkgrå text | `farg_accent`, `farg_text` | Text behöver kontrast minst 7:1, accent och dämpad text minst 4,5:1 mot vitt. |
| Justering | vänster, aldrig marginaljusterat | (fast i mallen) | Marginaljustering ger ojämna mellanrum och sämre läsbarhet. |
| Radlängd | 60–90 tecken | följer av marginal och storlek | Längre rader tappar ögat, kortare hackar. |

## Läsmönster

Rekryterare skummar ett CV på 6–7 sekunder i ett F-mönster: vänster kant uppifrån och ned, plus några svep åt höger. Därför ligger namn, nuvarande titel, arbetsgivare och datum överst och till vänster eller i en tydlig högerkant. Mallarna gör det redan. Flytta aldrig erfarenheten långt ner för att ge plats åt en lång profiltext.

## ATS (rekryteringssystem som läser CV:t)

- **En kolumn är säkrast** (klassisk, kompakt, porträtt). Sidokolumnen fungerar oftast eftersom den bara har kontakt, kompetenser och språk, och huvudtexten kommer först i dokumentet.
- Inga layouttabeller, ingen text i bilder, inget i sidhuvud eller sidfot. Mallarna följer det.
- Standardrubriker: Erfarenhet, Utbildning, Kompetenser (Experience, Education, Skills). Hitta inte på kreativa rubriker som "Min resa".
- PDF:en måste ha ett textlager. `render.py` kontrollerar det (`textlager.finns`).
- Foto är valfritt i Sverige. Personnummer, ålder och civilstånd ska aldrig med.

## Typsnitten som finns

Alla är OFL-licensierade och ligger i `templates/fonts/`. De bäddas in i HTML och PDF.

| Typsnitt | Karaktär | Passar |
|---|---|---|
| Source Sans 3 | lugn, neutral sans, mycket läsbar | brödtext i alla stilar |
| Source Serif 4 | klassisk men modern serif | namn och rubriker i konservativ och varm stil |
| Inter | teknisk, rak, modern | allt i modern stil, en familj |

Systemtypsnitt (Georgia, Helvetica, Arial) går att välja men ser olika ut på olika datorer. Saknas en fil används datorns standardtypsnitt, och skriptet varnar.

## Färger som fungerar

Mörka, dämpade accentfärger håller både på skärm och utskrift:

| Känsla | Accent | Dämpad text |
|---|---|---|
| Lugn, trygg | `#2f5d62` petrol | `#5f6368` |
| Saklig, modern | `#2b4c7e` blå | `#5b616e` |
| Varm, personlig | `#9a4a2f` terrakotta | `#6b625c` |
| Naturlig | `#3d5a45` grön | `#5d6166` |
| Stram | `#333333` grafit | `#666666` |

Undvik ljusa färger (gult, ljusblått, pastell) som accent. De försvinner utskrivna och klarar inte kontrastkravet.

## När hon vill något som skaver

Säg vad som händer, varför det spelar roll, och föreslå något nära det hon ville. Exempel:

- **"Mindre text så att allt får plats."** "Jag förstår att du vill få med allt. Under 10 punkt blir det svårt att läsa, särskilt utskrivet, och det är oftast den som läser som tappar tålamodet först. Ska vi i stället korta de äldsta jobben? De väger minst."
- **"Två kolumner, som i mallen jag såg."** "Det går, men en del rekryteringssystem läser två kolumner hackigt och blandar ihop texten. Vi kan ha en smal kolumn till höger med bara kontakt och kompetenser. Det ger samma känsla och är säkrare."
- **"Ljusrosa rubriker."** "Ljusa färger syns dåligt utskrivna och när någon läser på mobilen i solen. Vill du ha en varm ton kan vi ta en djup rosa eller en terrakotta. Ska jag visa två?"
- **"Ikoner för telefon och mejl" / "betyg i staplar för kompetenser".** "Ikoner och staplar läses inte av rekryteringssystemen, och staplar säger ändå inte så mycket ('vad är 4 av 5 i Excel?'). Vi skriver det i ord i stället, så hittar systemen nyckelorden."
- **"Marginaljusterat ser prydligt ut."** "På papper kan det se prydligt ut, men det ger ojämna luckor mellan orden och blir svårare att läsa. Vänsterjusterat är standard i CV just därför."
- **"Tre typsnitt."** "Fler än två typsnitt brukar se rörigt ut. Vill du ha mer variation kan vi spela med storlek och tjocklek i stället."

Det är hennes CV. Har hon hört skälet och vill ändå, gör det.
