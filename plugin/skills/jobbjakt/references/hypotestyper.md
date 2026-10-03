# Spårtyper (hypoteser) – vad, varför, hur

Ett spår är ett antagande om var rätt jobb finns, med en metod som testar det billigt. Det sparas i `sok/hypoteser.json`:

```json
{"schema_version":1,"hypoteser":[{
  "id":"h-003","typ":"alternativ_titel","status":"aktiv|pausad|beskuren",
  "beskrivning":"Kommunikatörsjobb heter ofta 'content lead'",
  "motivering":"hon vill skriva och planera, inte sälja",
  "metod":"jakt_titlar|jakt_arbetsgivare|jakt_signaler|webbrecept|recept|malbolag|manuell",
  "parametrar":{"roll":"kommunikatör"},"recept":null,"webbrecept":"content-lead",
  "skapad":"2026-10-01","senast_kord":"...",
  "korningar":[{"datum":"...","fynd":4,"uid":["webb-..."],"anteckning":"4 nya, 1 kända"}],
  "utbyte":{"fynd":12,"bedomda":8,"intressant":3,"sokt":1,"nej":4,"dubbletter":2,"andel":0.5,"beraknad":"..."}
}]}
```

`hittad_via` i `jobb.sqlite` = spårets id. Det kopplar varje annons till spåret som hittade den (första spåret vinner).

## 1. alternativ_titel
- **Varför:** samma jobb har många namn. Hon söker på sitt eget ord, arbetsgivaren skriver ett annat.
- **Test:** `jakt_titlar.py --roll "<hennes titel>" [--region "<län>"]`. Läs `titlar` (antal olika arbetsgivare som använt rubriken) och `sokord_forslag`. Ta de 3–5 som stämmer med vad hon vill göra. Avfärda brus (t.ex. säsongsjobb som felfilats).
- **Sedan:** lägg titlarna i ett webbrecept (`jakt_webbrecept.py skapa <namn> --titel ... --hypotes <id>`) och föreslå att jobbsok-receptets `q` breddas (efter ja).

## 2. narliggande_yrke
- **Varför:** taxonomin vet vilka yrken som är utbytbara (`substitutes`) och vilka som ligger i samma yrkesgrupp. Annonser som nämner hennes roll hamnar också under andra yrken.
- **Test:** samma körning, listan `yrken` (relation: utbytbart / samma yrkesgrupp / annonser som nämner X). Välj 1–3 med rimlig volym (`annonser`).
- **Sedan:** yrkes-id kan läggas i receptets `occupation-name` (efter ja).

## 3. energimatch
- **Varför:** hennes energigivare (coach.json → energy_log.patterns.energizers, preferenser.arbetsdag) säger mer än titeln. "Skriva", "ordna processer", "möta människor en och en".
- **Test:** översätt 1–2 energigivare till kompetensord och kör `jakt_titlar.py --kompetens "<ord>"`. Se vilka yrken annonserna med de orden hamnar under. Jämför med energitjuvarna – stryk yrken som är fulla av dem.
- **Exempel:** energigivare "förklara krångliga saker enkelt" → kompetens "pedagogik", "klarspråk" → yrken: utbildare, webbredaktör, kommunikatör i myndighet.

## 4. liknande_arbetsgivare
- **Varför:** de som anställt hennes yrke i regionen de senaste åren gör det sannolikt igen, också utan att annonsen når henne.
- **Test:** `jakt_arbetsgivare.py region --roll <roll> --region "<län>" --kallor-forslag`. Visa topp 10 (namn, antal, senaste). Bemanningsbolag (Academic Work, Poolia, Adecco …) är kanaler, inte arbetsgivare – nämn dem separat.
- **Sedan:** efter hennes ja: hitta karriärsidan (ett webbsök `"<bolag>" lediga jobb`) och `kalla_lagg_till.py <url> --namn "<bolag>"`. Offentliga arbetsgivare har ofta Varbi-RSS (`https://{kund}.varbi.com/what:rssfeed/`).

## 5. likar
- **Varför:** gillar hon X, finns det ofta fler som X – samma sorts uppdrag, samma sorts kollegor.
- **Test:** `jakt_arbetsgivare.py likar --bolag "X" [--region ...]`. Likhet = hur mycket av X:s yrkesprofil de täcker, gånger volym. Komplettera med ett webbsök `konkurrenter till "X"` eller `"X" OR liknande bransch` för bransch och värderingar, som statistiken inte ser.
- **Varning:** stora arbetsgivare (regioner, universitet) liknar många. Lyft fram de mindre och mer specifika.

## 6. vardedriven
- **Varför:** topp-5-värden (preferenser.varden_topp5, coach.identity.values_top5) pekar ut sektorer: samhällsnytta → myndigheter, kommuner, idéburen sektor; hållbarhet → klimat-, energi-, cirkulära bolag.
- **Test:** ett webbsök som listar organisationer i sektorn och regionen (t.ex. `idéburna organisationer Uppsala`, `myndigheter med huvudkontor i Uppsala`), sedan `jakt_arbetsgivare.py likar` på den som stämmer bäst. Nischsajter: `ideellt` i webbrecepten (Arena Opinion, Arena Idé).
- **Sedan:** målbolag → källor (efter ja) och/eller dold marknad.

## 7. tillvaxtsignal
- **Varför:** bolag som växer anställer innan annonsen syns, eller har behov som ingen annons beskriver.
- **Test:** `jakt_signaler.py --bolag "<målbolag>" ... --sok "nyanställer <ort>" --sok "etablerar <ort>"`. Signaler: nyanställer, expanderar, nytt_kontor, förvärv, kapital, ny_ledning, upphandling.
- **Sedan:** en signal + passform → dold marknad (utkast). Bolaget kan också bli källa.

## 8. webbjakt och nischsajt
- **Varför:** många annonser finns bara på bolagets karriärsida (Teamtailor, Varbi, Lever, Ashby, Greenhouse) eller på en branschsajt.
- **Test:** se webbjakt.md.

## 9. dold_marknad
- **Varför:** en del tjänster tillsätts utan annons. (Siffran "70–80 %" är dåligt belagd – säg "en betydande andel".)
- **Test och gränser:** se dold-marknad.md. Bara utkast.

## 10. joker
Ett medvetet sidospår utanför filtren. Spara om hon vill följa upp, med `--motivering`.

## Att formulera ett bra spår
- En mening, med vanliga ord, som hon kan säga ja eller nej till.
- Kopplad till något hon själv sagt (citera gärna).
- Testbar inom en körning. "Fler jobb inom kommunikation" är för brett; "Myndigheter i Uppsala anställer kommunikatörer under titeln 'kommunikationsstrateg'" går att testa.
