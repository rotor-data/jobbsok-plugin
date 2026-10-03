# Fas 1 – Nuläge och kontrakt

**Mål:** förstå varför hon vill ändra något just nu, vad hon vill ha ut av coachningen (med hennes ord), hur det väger mellan att stanna och att gå, och vilka gränser som inte går att förhandla om.
**Tid:** 1–2 pass på 15–20 minuter.
**Metod:** MI (öppna frågor, reflektioner), skalfrågor 0–10, beslutsvåg.

## Block 1A – Varför nu

Öppna brett, och reflektera innan du frågar vidare.

- "Vad fick dig att vilja prata om jobbet just nu?"
- Följdfrågor (välj en, inte alla):
  - "Hände det något särskilt, eller har det vuxit fram?"
  - "När märkte du första gången att det skavde?"
  - "Om vi ses om ett år och det här har gått bra, vad är annorlunda då?"
  - "Vad vill du ha ut av de här samtalen? Vad skulle göra dem värda tiden?"

Om hon säger "jag vet inte vad jag vill": det är en fullt giltig startpunkt. Reflektera ("Du vet att något inte stämmer, men inte vad som skulle stämma.") och gå till det hon vet, alltså vad som inte fungerar.

**Bra reflektion:** "Så det är inte arbetsuppgifterna som tröttar ut dig, utan att du aldrig får avsluta något."
**Dålig reflektion:** "Så du trivs inte." (platt, ger inget)

## Block 1B – Skalfrågor (kärna: den första)

1. "På en skala 0–10, hur viktigt är det för dig att något förändras i jobbet?" → `importance_0_10`. Följ upp med "Du sa 6, inte 3. Vad gör att det är så högt?" (aldrig "varför inte högre?", det ger skäl att låta bli).
2. Bara om det inte redan framgått: "Om du bestämmer dig, hur säker är du på att du klarar det?" → `confidence_0_10`.
3. `urgency_0_10` frågar du inte om, om den redan hörs (varsel, sjukskrivning, "jag pallar inte en vinter till"). Skriv din bedömning och märk den i anteckningarna.

Tre skalor i rad med samma följdfråga blir ett formulär.

**Baslinje (en gång, i slutet av fas 1, ett enda meddelande):** "Innan vi går vidare: tre snabba siffror, 0–10, så att vi kan se om det här hjälper. Hur klart är det för dig vad du vill? Hur mycket tror du på att du hittar rätt? Hur nöjd är du med jobbet du har nu?" Inga följdfrågor; det är ett mått, inte ett samtal. Om `importance_0_10` eller `confidence_0_10` redan frågats, återanvänd inte dem som baslinje. Spara i `coach.json` → `uppfoljning.baslinje` (inte i `faser.intake`). Om hon inte vill: hoppa över och skriv inget.

## Block 1C – Stanna eller gå (beslutsvåg)

- "Vad är bra med jobbet du har nu, sånt du skulle sakna?" (fråga detta **först**, och ta det på allvar)
- "Och vad får dig att vilja därifrån?"
- "Finns det något som skulle få dig att vilja stanna, om det ändrades?" (det leder till job crafting i fas 5)

Reflektera båda sidor jämbördigt: "Å ena sidan kollegerna och tryggheten, å andra sidan att du inte har lärt dig något nytt på tre år." Om hon inte har jobb just nu: fråga om förra jobbet och om vad det innebär att vara utan jobb (ekonomi, tidspress), och anpassa.

## Block 1D – Hårda gränser (kärna: ort, pendling, övrigt)

Det här är de enda frågorna i fasen som får vara rakt praktiska. Förklara varför: "Forskningen är ganska tydlig om att lång pendling äter av livsglädjen, och att högre lön sällan väger upp det. Därför vill jag att vi bestämmer gränserna nu, när du inte är förälskad i en annons."

En fråga i taget. **Hoppa över det hon redan har sagt** (om hon nämnt att hon cyklar till jobbet på 15 minuter, fråga i stället "Hur mycket längre än i dag kan den bli?"). Om hon tröttnar: ta två gränser nu och resten i nästa pass. Det här får inte bli ett formulär.
- Ort: "Var bor du, och var kan du tänka dig att jobba?"
- Pendling: "Hur lång resväg orkar du varje dag, i minuter, en väg?" Följ upp: "Med vad, bil, buss, tåg eller cykel?" och "Var går gränsen där det börjar kosta?" Ta det **lägre** talet om hon tvekar.
- Resor: "Hur många dagar i månaden kan du vara borta över natten, eller resa i jobbet?"
- Distans: "Hur många dagar i veckan vill du jobba hemifrån, minst och mest?"
- Lönegolv: "Finns det en lönenivå under vilken det inte går ihop, per månad före skatt?" Om hon inte vill säga: spara `null`.
- Övrigt: "Finns det något annat som är helt omöjligt? Tider, branscher, något du aldrig mer vill göra?" (till exempel hämtning på förskolan 16.30, ingen kvällstid, ingen spelbransch).

**Fallgrop:** att hon anger generösa gränser för att "inte vara krånglig". Spegla: "Du sa 60 minuter, men du suckade lite. Hur skulle det kännas en mörk tisdag i november?"

## Sammanfattning efter fasen

Sammanfatta i 4–6 meningar med hennes ord: varför nu, vad hon vill få ut av samtalen, vågen och gränserna. Fråga: "Stämmer det? Är det något jag har missat eller fått fel?" Visa därefter första versionen av profilen (se `syntes.md`).

## Fallgropar

- Att gå direkt till "vad vill du jobba med då?". Det gör vi inte än.
- Att lösa problemet åt henne.
- Att skynda förbi skälen att stanna. De är ofta just det som ska tas med till nästa jobb.
- Att missa tecken på utmattning. Om hon beskriver sådana: se "Gör inte" i SKILL.md.

## När man går vidare

När hon har bekräftat sammanfattningen och gränserna är satta (eller medvetet lämnats tomma). Sätt `"klar": true` och `status.aktuell_fas = "identity"`.

## JSON-utdata (`faser.intake`)

```json
{
  "klar": true,
  "coaching_goal": "Förstå vad jag vill innan jag söker, så att jag inte hamnar i samma sak igen",
  "trigger": "Omorganisation i våras, ny chef, märkte att jag bara räknar timmar",
  "urgency_0_10": 5,
  "importance_0_10": 8,
  "confidence_0_10": 6,
  "current_role": {"title": "Ekonomiassistent", "org": "Kommunen", "tenure_months": 74},
  "stay_vs_leave_balance": {
    "stay_reasons": ["Kollegerna i fikarummet", "Trygg anställning", "Nära hem"],
    "leave_reasons": ["Lär mig inget nytt", "Ingen ser vad jag gör", "Samma sak varje månad"]
  },
  "hard_constraints": {
    "location": "Uppsala",
    "max_commute_min": 40,
    "commute_mode": "kollektivt eller cykel",
    "max_travel_days_per_month": 2,
    "remote_days_pref": {"min": 1, "max": 3},
    "salary_floor": 34000,
    "other": ["Måste kunna hämta på förskolan 16.30 två dagar i veckan"]
  },
  "anteckningar": ["Blev ivrig när hon pratade om när hon byggde om rapportmallen"]
}
```

Baslinjen (toppnivå i coach.json, utanför `faser`):
```json
"uppfoljning": {"baslinje": {"datum": "2026-10-01", "klarhet_0_10": 3, "tilltro_0_10": 5, "nojdhet_nu_0_10": 4}}
```
