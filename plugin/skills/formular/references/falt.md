# Vanliga formulärfält och var värdet hämtas

| Fält i formuläret | Källa | Kommentar |
|---|---|---|
| Förnamn / Efternamn | `fakta.person.namn` | Dela vid sista mellanslaget; fråga om det är osäkert (dubbla efternamn). |
| E-post, Telefon | `fakta.person.epost`, `.telefon` | |
| Adress, Postnummer | fråga | Lagras inte i faktabanken som standard. |
| Ort / Bostadsort | `fakta.person.ort` | |
| LinkedIn, Portfolio | `fakta.person.lankar[]` | Välj efter `etikett`. |
| Nuvarande titel / arbetsgivare | `fakta.roller[]` där `slut` är null | Titel på formulärets språk (`titel.sv`/`titel.en`). |
| Anställningshistorik (upprepade block) | `fakta.roller[]` i omvänd ordning | Datum `YYYY-MM`; beskrivning ur `beskrivning` eller de meriter som `cv.json` valt. |
| Utbildning | `fakta.utbildning[]` | |
| Språk + nivå | `fakta.sprak[]` | Mappa nivå till sidans skala och visa mappningen. |
| Körkort | `fakta.person.korkort` | |
| Personligt brev (textfält) | `brev.json` → `stycken` | Vid teckengräns: korta via skrivlagret, inte genom att klippa. |
| CV / Brev (uppladdning) | `cv.pdf`, `brev.pdf` i ansökningsmappen | |
| Löneanspråk | fråga | Aldrig gissa. |
| Tillträde / Uppsägningstid | fråga | |
| Referenser | `fakta.referenser[]` | Standard: "Lämnas på begäran". Fråga innan namn lämnas ut. |
| Hur hittade du annonsen? | källan i `annons.md` | |
| Personnummer, födelsedatum, kön, medborgarskap | **lämnas till henne** | Fyll aldrig i. Frivilliga mångfaldsfrågor: hon väljer själv. |
| Samtycke GDPR / villkor | **lämnas till henne** | Visa texten, bocka aldrig i. |
