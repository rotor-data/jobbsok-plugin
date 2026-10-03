# Kultur-Q-sort (18 satser, `kultur-qsort-18-v1`)

Gemensam för coachen (fas 4, block 4H) och arbetsgivarkortet. **Samma id och samma satser överallt**, så att hennes ideal, hennes senaste jobb och en arbetsgivare kan jämföras direkt. Ändras en sats får instrumentet ett nytt versionsnamn (`-v2`).

Satserna är egna parafraser av OCP-logiken (O'Reilly, Chatman & Caldwell 1991; Sarros 2005), inte originaltexten, och de är inte validerade. Underlag: `docs/research/kultur-ledarskap-evidens.md` avsnitt 1. Dimensionen i parentes är för ditt bruk och visas inte för henne.

## Satserna

| id | Sats | Dimension |
|---|---|---|
| s1 | Man provar nya sätt även om det kan gå fel. | innovation |
| s2 | Man tar chansen när en möjlighet dyker upp, snabbt. | innovation |
| s3 | Det finns tydliga mål, och man följs upp mot dem. | resultat |
| s4 | Höga förväntningar på prestation, och det märks vem som levererar. | resultat |
| s5 | Det ska vara noggrant och rätt, hellre sent än slarvigt. | detalj |
| s6 | Det finns tydliga rutiner och man följer dem. | detalj/stabilitet |
| s7 | Man delar information och hjälper varandra över gränserna. | samarbete |
| s8 | Beslut förankras i gruppen innan de fattas. | samarbete |
| s9 | Kunden eller medborgaren går först, även när det är obekvämt internt. | kund |
| s10 | Man säger som det är, även uppåt. | integritet |
| s11 | Man håller vad man lovar, och etik går före snabba vinster. | integritet |
| s12 | Man bryr sig om varandra som människor, inte bara som kolleger. | stödjande |
| s13 | Man får beröm och erkännande när man gjort något bra. | stödjande/belöning |
| s14 | Det är förutsägbart, och stora omorganisationer är ovanliga. | stabilitet |
| s15 | Man tävlar internt, och den bästa idén vinner. | konkurrens |
| s16 | Man har stort eget ansvar och lite detaljstyrning. | autonomi |
| s17 | Arbetstiden respekteras och kvällsmejl är inte normen. | gränser/balans |
| s18 | Organisationen tar ansvar för samhället och miljön på riktigt. | socialt ansvar |

## I chatten (4–10–4)

Visa alla 18 numrerade i ett meddelande (det är en övning, så listan är okej). Hon svarar med siffror.

1. **Psykoedukation, en mening:** "Det här är ett sätt att sätta ord på kultur. Att tvingas välja säger mer än att gradera allt, för då blir allt 'ganska viktigt'."
2. **Ideal, topp:** "Vilka **fyra** beskriver bäst en arbetsplats där du skulle blomma?" Följ upp på **en** av dem: "Berätta om ett tillfälle då du hade just det."
3. **Ideal, botten:** "Vilka **fyra** behöver du minst, eller skaver?" Resten hamnar i mitten. Fyra exakt: har hon fem, be henne stryka en ("vilken kan du vara utan?").
4. **Senaste jobbet**, samma två frågor: "Och hur var det på [arbetsplatsen hon nämnt]? Vilka fyra stämde mest där, och vilka fyra minst?" Har hon inget senaste jobb: ta det jobb hon minns bäst, eller hoppa över steget.
5. **Glappet.** Räkna tyst: topp = 3, mitten = 2, botten = 1, glapp = ideal − senaste. Visa **aldrig** tabellen eller siffrorna. Ta de två eller tre största glappen och säg det som **2–3 korta insikter**, som förslag:
   > "Du vill att man säger som det är, även uppåt, och att man bryr sig om varandra. På förra jobbet var just de två längst ner. Är det där det skavde?"
   > "Rutiner hamnade högt på förra jobbet men lågt hos dig. Det låter som att det var för mycket ordning, inte för lite."
   Ett negativt glapp (mer där än hon vill) är lika viktigt som ett positivt.
6. Låt henne rätta. Spara hennes ord om glappet i `hennes_ord`.
7. **Varningssignaler:** fråga en gång: "Finns det någon av satserna som är en dealbreaker om den saknas, eller om den finns?" Det hon säger går till `dealbreakers` (och i fas 7 till `varningssignaler`).

Gör inte: räkna ut ett "fitvärde", kalla henne en kulturtyp, eller fråga om alla 18 en i taget.

## Vid trötthet

Kärnan är steg 2, 3 och 5 med bara idealet plus en fråga: "Vilken av de här saknades mest på förra jobbet?" Det ger ett glapp utan en andra sortering.

## JSON (`faser.needs_profile.kultur_profil`)

```json
{
  "instrument": "kultur-qsort-18-v1",
  "datum": "2026-10-01",
  "ideal": {"topp": ["s10", "s12", "s16", "s7"], "botten": ["s15", "s4", "s2", "s6"]},
  "senaste_jobb": {"arbetsplats": "Regionens kommunikationsenhet", "topp": ["s6", "s3", "s4", "s14"], "botten": ["s10", "s12", "s16", "s1"]},
  "storsta_glapp": [
    {"sats": "s10", "ideal": 3, "senaste": 1, "hennes_ord": "Man fick inte säga emot, allt gick via tre chefer"},
    {"sats": "s6", "ideal": 1, "senaste": 3, "hennes_ord": "Rutiner för rutinernas skull"}
  ],
  "insikter": ["Det som skavde var att man inte fick säga som det är"],
  "dealbreakers": ["s15 finns: intern tävling"],
  "exempel": [{"sats": "s12", "berattelse": "När mamma var sjuk ringde min chef och sa att jag skulle gå hem"}]
}
```

Arbetsgivarkortet skattar samma satser (`topp`/`botten` med id `s1`–`s18`) och jämför mot `ideal`. Fas 7 kopierar `ideal` till `preferenser.json` → `kultur_ideal`.
