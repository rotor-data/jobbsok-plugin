# Steg 2 – Efter intervjun

Gör debriefen så snart som möjligt, helst samma dag: minnet väger toppar och slut (peak-end), och detaljerna försvinner fort. Säg det kort till henne.

## A. Debrief (öppet först, sedan riktat)

1. "Hur gick det, och hur kändes det när du gick därifrån?" Reflektera, vänta med analysen.
2. "Vad såg och hörde du?" Be om konkreta saker: lokalen, hur de pratade om varandra, vem som pratade mest, vad som hände när hon ställde en fråga, om chefen lyssnade eller sålde.
3. Gå igenom hennes frågor (`fragor_att_stalla`) en i taget: vad svarade de? Spara svaret per fråga. Ett undvikande svar är också ett svar; notera det som sådant, utan att döma.
4. Chefen, med begreppen från forskningen (`docs/research/kultur-ledarskap-evidens.md` 2b) men hennes ord: verkar relationen gå att bygga (LMX), får man välja hur (autonomistöd), är det tryggt att säga emot (psykologisk trygghet)?
5. Två skalor 0–10: "Hur gärna vill du gå vidare?" och "Hur säker är du på din bild av dem?".

Skilj på vad hon **såg** (belägg) och vad hon **tror** (tolkning). Peka vänligt på det om hon drar stora slutsatser av en detalj, och lika mycket om hon bortförklarar en tydlig signal ("Du sa att han avbröt dig tre gånger. Hur väger du det?").

## B. Kultur-Q-sort "som du upplevde den"

Samma 18 satser och samma metod som coachen (`skills/karriarcoach/references/kultur-qsort.md`): de fyra som mest stämde på arbetsplatsen som hon upplevde den, de fyra som minst stämde, resten i mitten. Sedan jämförelsen mot hennes ideal: överlapp i toppen och de satser där ideal och upplevelse krockar. Säg det som en spegel, inte ett betyg ("Tre av dina fyra viktigaste hamnade i mitten. Det kan betyda att du inte såg dem, eller att de inte finns. Vilket tror du?"). Spara med `kalla: "intervju"` och `sakerhet` (låg efter en intervju, oftast).

Saknas kultur-qsort.md ännu: använd satserna i `docs/research/kultur-ledarskap-evidens.md` avsnitt 1 (id `s1`–`s18`).

## C. Arbetsgivarkortet: egna intryck

Uppdatera `sok/arbetsgivare/<slug>.json` med hennes egna intryck (Q-sorten, chefsintrycket, svaren på frågorna) **via `arbetsgivarkort.py`** (kör `--help` för rätt kommando). Skriv aldrig direkt i kortet. Finns inget kort eller inget kommando för egna intryck: spara allt i `intervju.json` → `debrief`, sätt `arbetsgivarkort_uppdaterat: false` och säg att det läggs in när kortet finns. Arbetsgivarkortet tillhör en annan del: rör inte dess format.

## D. Nya varningssignaler

Fick hon syn på något hon inte vill ha igen? Fråga: "Var det något som fick dig att tänka 'det där känner jag igen' på fel sätt?" Spara i `debrief.varningssignaler_nya` med belägg (vad hon såg). Är signalen allmän (gäller fler arbetsgivare än den här) fråga om den ska in i hennes egna varningssignaler; säger hon ja, lägg till den i `preferenser.json` → `varningssignaler` enligt coachens format och validera.

## E. Tackmejlet

Skriv nu klart `tackmejl.md` med något konkret som sades (se `forberedelse.md` F). Hon skickar.

## Spara

`intervju.json` → `debrief` (en per omgång), validera, anteckning i `logg.json`. Fråga om hon vill sätta ett datum för att höra av sig om hon inte fått besked (`foljupp_datum`).
