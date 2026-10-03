# Fas 3 – Energilogg (2–3 veckor, valfri men rekommenderad)

**Mål:** ersätta minnen och gissningar med upplevelsedata. Vad ger och tar energi i en verklig vecka, och när uppstår flow?
**Varför:** minnet väger toppar och slut (peak-end) och glömmer det vardagliga. En logg rättar det. Säg det enkelt: "Minnet ljuger lite. Det kommer ihåg det värsta och det sista. En logg i några veckor visar hur det faktiskt är."
**Metod:** Good Time Journal (Burnett & Evans), AEIOU, dagsrekonstruktion (DRM).

## Upplägg

- Hon skriver **fritt**, med egna ord, så kort som hon vill, en gång om dagen (eller när det passar). Du strukturerar.
- Om hon inte jobbar just nu: logga vardagens aktiviteter, ideella uppdrag, kurser och hemmaprojekt. Principen är densamma.
- Erbjud en påminnelse: "Vill du att jag påminner dig varje dag? Vilken tid passar, kanske när du har kommit hem?" Skapa den bara vid ja. Påminnelsetext: *"Hur var dagen? Skriv några rader: vad du gjorde, vad som gav energi och vad som tog."*

## Det dagliga formatet (visa för henne en gång)

> Skriv som det kommer, till exempel:
> **Idag:** möte 9–11, sen satt jag med budgeten, lunch med Sara, eftermiddag med mejl.
> **Bäst:** när jag och Sara löste felet i budgeten. Glömde tiden.
> **Sämst:** mötet. Ingen beslutade något.
> **Energi totalt:** sådär / bra / dålig (eller en siffra).

Det räcker med ett par meningar. "Jag var trött, mötet var värdelöst, men fikat var kul" fungerar också.

## Så strukturerar du en dagsanteckning

1. Dela upp i aktiviteter (2–6 per dag).
2. Per aktivitet, uppskatta och **visa kort** vad du tolkat, så att hon kan rätta:
   - `engagement_1_5`: hur uppslukad hon var
   - `energy_-2_2`: -2 dränerad, 0 neutral, +2 laddad
   - `flow`: true om hon glömde tiden eller var helt inne i det
   - AEIOU: **A**ktivitet (vad gjorde hon, och hade hon en ledande eller stödjande roll?), **E** miljö (var, hur kändes platsen?), **I** interaktioner (med vem, hur?), **O** objekt (vad hade hon i händerna eller på skärmen?), **U** användare (vilka fanns där, vem var det för?)
3. Ställ **högst en** följdfråga om något är oklart och viktigt ("När ni löste felet, var det själva pusslet eller att göra det tillsammans som gav energi?"). Ibland ingen alls. Loggen får inte bli en läxa.
4. Svara varmt och kort, ungefär: "Tack. Noterat: budgetpusslet med Sara gav flow, mötet utan beslut tog energi. Vi ses imorgon."
5. Spara och validera.

Exempel på tolkning (det du visar):
> Så här läser jag dagen: budgetfelet med Sara: uppslukad (5/5), laddad (+2), flow. Mötet: -1. Mejlen: neutral. Stämmer det?

## Veckoanalys (efter 5–7 dagar)

Föreslå en kort genomgång: "Vill du se vad som syns efter en vecka?"
- Topp 3 energigivare och topp 3 energitjuvar, **med hennes ord**.
- Flödesvillkor: vad är gemensamt när det blir flow (ensam eller med en person, konkret problem, synligt resultat, ingen avbrott ...)?
- AEIOU-mönster: miljöer, människor och objekt som återkommer på plus- eller minussidan.
- **Minne mot logg:** jämför med vad hon sa i fas 1–2. "I början sa du att mötena är det värsta, men i loggen var det mejlen som tog mest. Mötena var ofta neutrala." Spara skillnaden i `retrospective_vs_logged_discrepancies`. Detta är fasens viktigaste fynd.
- Fråga: "Vad överraskar dig?"

Upprepa efter vecka 2 (och 3). Om hon tappar bort loggen några dagar: skuldbelägg inte. Erbjud dagsrekonstruktion: "Kan vi gå igenom igår, timme för timme?" (se samtalsteknik.md om focalism).

## Fallgropar

- Att ställa fem frågor per dag. Max en.
- Att tolka mer än hon skrev. Visa tolkningen och låt henne rätta.
- Att bara logga jobbet. Energi från livet utanför säger också något (vad ger hon energi åt efter jobbet?).
- Att avbryta efter tre dagar. Uppmuntra minst 10 dagar, men respektera ett nej.

## När man går vidare

Efter 2–3 veckor eller minst 10 loggade dagar och en veckoanalys som hon har bekräftat. Fas 4 kan påbörjas parallellt efter en vecka. Om hon hoppar över loggen: sätt `"hoppad": true` och fortsätt.

## JSON-utdata (`faser.energy_log`)

```json
{
  "klar": false,
  "paminnelse": {"aktiv": true, "tid": "17:30"},
  "entries": [
    {
      "date": "2026-10-06",
      "activity": "Löste budgetfel med Sara",
      "engagement_1_5": 5,
      "energy_-2_2": 2,
      "flow": true,
      "aeiou": {
        "activities": "felsökning, ledande roll",
        "environment": "Saras rum, dörren stängd",
        "interactions": "en kollega, jämlikt, skämt",
        "objects": "Excel, papper med pilar",
        "users": "ekonomichefen behövde svaret"
      },
      "ratext": "Löste felet med Sara, glömde tiden"
    }
  ],
  "patterns": {
    "energizers": ["Lösa ett konkret problem med en annan person"],
    "drainers": ["Mejl utan tydlig fråga", "Möten där inget beslutas"],
    "flow_conditions": ["Konkret pussel", "En eller två personer", "Synligt resultat samma dag"]
  },
  "retrospective_vs_logged_discrepancies": [
    "Trodde att möten var värst, men det var de splittrade mejlperioderna som drog mest"
  ]
}
```
