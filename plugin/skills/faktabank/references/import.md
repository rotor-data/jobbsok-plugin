# Import av underlag

Allt som importeras är ett utkast tills hon godkänt det, och allt räknas som hennes egna uppgifter (`egen_uppgift`). Läs, extrahera, visa, och spara först efter ja.

## Gammalt CV (PDF/DOCX)
- Be henne lägga filen i `<home>/import/` eller bifoga den i samtalet.
- PDF: använd PDF-läsning (pdf-skillen eller `pdftotext` om det finns). DOCX: packa upp med Python `zipfile` och läs `word/document.xml` (ta texten i `<w:t>`), eller använd docx-skillen.
- Extrahera: roller (arbetsgivare, titel, ort, period), punktrader per roll, utbildning, kurser, språk, kompetenser, länkar.
- Perioder: gör om till `YYYY-MM`. Står bara år: fråga om månaden, eller använd `-01` och säg det.
- Hoppa över personnummer, födelsedatum, ålder, civilstånd och foto (foto bara om hon ber).
- Punktrader skrivs om till en rad per merit utan nya påståenden. Siffror behålls som `egen_uppgift` och bekräftas.

## Aktualitetsanalys (efter ett CV)
Visa kompakt, en rad per punkt, innan intervjun:
1. **Ålder:** senaste datum i CV:t, annars filens datum (`stat`), annars fråga. "Det här CV:t verkar vara från våren 2019."
2. **Luckan:** från senaste roll eller datum till i dag, i år och månader.
3. **"Pågående" roller** (står "– nu" eller saknar slut): "Är du kvar som lagerkoordinator, eller har det ändrats?"
4. **Inaktuellt:** gamla system, versioner och termer ("Office 2010", "Lotus Notes", gamla avdelningsnamn).
5. **Saknas:** sektioner som brukar finnas (profilrad, språk, kurser, körkort).
6. **Längd:** för långt (mer än två sidor, punkter om gamla roller) eller för kort (roller utan en enda punkt).
Fråga sedan: "Vad har hänt sedan dess?" och gå till den riktade uppdateringen i SKILL.md steg 3.

Spara hur det gamla CV:t såg ut (layout, längd, språk, foto eller inte) i `import/<filnamn>.anteckning.md`. cv-design kan läsa det när hon ska välja mellan att behålla eller byta stil. Fråga också om det finns formuleringar hon gillar; spara dem ordagrant i `rost.json` → `gillade_formuleringar`.

## LinkedIn-dataexport (ZIP)
Instruktion till henne:
1. LinkedIn → Jag (profilbilden) → Inställningar och sekretess → Datasekretess → Hämta en kopia av dina data.
2. Välj "Vill du ha något särskilt?" och bocka i Profil, Positioner, Utbildning, Kompetenser, Språk, Certifieringar (eller ta hela arkivet).
3. Vänta på mejlet (från minuter upp till ett dygn), ladda ner ZIP:en och lägg den i `import/` i Jobbsok-mappen.

Läsning (Python stdlib `zipfile` + `csv`; filnamnen kan variera något mellan år):
| Fil | Fält → faktabank |
|---|---|
| `Profile.csv` | First Name, Last Name → `person.namn`; Headline → `person.titel.sv/en`; Summary → underlag till `sammanfattning_rad`; Geo Location → `ort` |
| `Positions.csv` | Company Name, Title, Description, Location, Started On, Finished On → roller. Datum som "Mar 2021" → `2021-03` |
| `Education.csv` | School Name, Start Date, End Date, Degree Name, Notes → utbildning |
| `Skills.csv` | Name → kompetensförslag (mappas sedan via taxonomy.py) |
| `Languages.csv` | Name, Proficiency → sprak (mappa nivå och visa mappningen) |
| `Certifications.csv` | Name, Authority, Started On → kurser |

Profiltexter på LinkedIn är ofta på engelska: lägg dem i `en` och fråga om svensk version.
Logga aldrig in på LinkedIn åt henne och hämta aldrig något därifrån via webbläsaren.

## Fritt berättande
Låt henne prata klart. Sammanfatta det i en lista med roller och möjliga meriter, och gå sedan in i intervjun roll för roll för att bekräfta och precisera.

## Dubbletter och konflikter
Om flera källor säger olika (t.ex. olika slutdatum): visa båda och fråga. Spara aldrig en sammanvägning utan att hon valt.
