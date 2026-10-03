# Fas 4 – Behovsprofil

**Mål:** översätta det ni vet till behov hon kan känna igen i en annons och på en arbetsplats: grundbehov, krav och resurser, lagom mängd (som intervall), passform mot grupp och chef, och en idealvecka i timblock.
**Ingång:** fas 2 klar, helst minst en veckas logg.
**Tid:** 2–3 pass. **Kärna:** 4D, 4E, 4G, kultur-Q-sorten (4H) och chefsfrågornas kärna (4F). Ta bara de andra blocken om fas 1–2 inte redan gett svaret (grundbehov och passform brukar redan finnas i kränkt-exemplen och skälen att gå).

Utgå från det hon redan berättat: "När du pratade om mormor ... Vad betyder det för vad du behöver?"

## Block 4A – Grundbehov (SDT)

Ett behov i taget, en fråga per meddelande. Börja med minnet, ta siffran sist.
- **Autonomi:** "När var du senast fri att bestämma *hur* du gjorde något?" Sedan: "Hur ofta händer det nu, 0–10?"
- **Kompetens:** "När kände du dig senast skicklig, på riktigt?"
- **Samhörighet:** "När kände du dig senast som 'en av oss'?"

## Block 4B – Vad du vill göra med dagarna (RIASEC via aktiviteter)

Använd **aktiviteter, inte titlar**. Visa en blandad lista med 12–18 aktiviteter (2–3 per typ) och be henne välja vad hon gärna gör 60 % av tiden, och vad hon står ut med i 10 %:

- R: laga, bygga eller fixa något fysiskt; jobba utomhus; hantera maskiner eller verktyg
- I: ta reda på varför något inte fungerar; analysera siffror; läsa in sig på något svårt
- A: formge, skriva eller skapa; hitta på nya lösningar; göra något snyggt
- S: hjälpa någon som har det svårt; lära ut; lyssna och stötta
- E: övertyga, sälja eller förhandla; driva ett projekt framåt; leda en grupp
- C: få ordning på röriga uppgifter; följa upp detaljer; bygga system och rutiner

Sammanfatta som "det du dras till är att reda ut ett problem och få ordning på det åt någon", inte som bokstäver. Spara de tre bokstäverna för eget bruk (`riasec_top3`). **Evidensen för att kongruens ger nöjdhet är svag** (r ≈ .10–.20). Använd det som en ingrediens.

## Block 4C – Värden i jobbet (TWA)

"Ranka de här sex efter vad ett jobb måste ge dig": prestation (se resultat), bekvämlighet (bra villkor och arbetsmiljö), status, altruism (hjälpa andra), trygghet, autonomi. Följdfrågor: "Vilket har jobbet aldrig gett dig?" och "Hur länge står du ut med ett glapp där?"

## Block 4D – Krav och resurser (JD-R)

- "Vilka är de fem saker som kräver mest av dig i dag?" För varje: "Är det en utmaning som du växer av, eller ett hinder som bara tar?" (`challenge|hindrance`)
- "Vad hjälper dig att orka? Stöd, frihet, feedback, kolleger, utrustning?"
- "Vilken resurs saknar du mest?" Den hamnar högst i `resources_needed`.

## Block 4E – Vitaminer som intervall (Warr)

Fråga **aldrig** "vill du ha mer variation?". Svaret blir alltid ja. Säg varför, en gång: "Det mesta är som vitaminer: för lite är dåligt, men för mycket också. Därför frågar jag om golv och tak." Fråga efter golv och tak på en skala 0–10:
- Variation: "Hur mycket omväxling vill du ha innan det blir splittrat? Och hur lite innan det blir tråkigt?"
- Autonomi: "Hur mycket vill du bestämma själv innan det blir ensamt eller otydligt?"
- Social kontakt: "Hur många samtal och möten per dag innan du blir tom? Hur få innan du blir ensam?" Gärna med konkreta tal: timmar med människor per dag.
- Arbetsbelastning: "Var går gränsen mellan skönt tempo och stress?"
Kontrollera mot loggen: "I loggen var de bästa dagarna två möten och resten eget arbete. Låter 3–5 rätt?"

## Block 4F – Passform

En fråga per nivå, med konkreta exempel:
- Jobb: "Vad måste jobbet innehålla?"
- Organisation: görs med kultur-Q-sorten i block 4H.
- Grupp: "Bland vilka kolleger vill du vara den som kan minst?" och "Vill du ha kolleger som vänner, eller som trevliga proffs?" (`work_friends_importance_0_10`), samt gruppstorlek.
- Chef och ledarskap, både hennes eget och det hon behöver: följ `references/ledarskap.md` (4F-1 och 4F-2). Utdata: `ledarskap_eget` och `ledarskap_behov`.

## Block 4H – Kultur (Q-sort)

Följ `references/kultur-qsort.md`: 18 satser, fyra högst och fyra lägst, först för idealet och sedan för senaste jobbet. Glappet visas som 2–3 korta insikter, aldrig som siffror. Utdata: `kultur_profil`.

Varför i fas 4 och inte fas 2: Q-sorten jämför ideal mot verklighet, och då behövs värdena (fas 2) och helst loggen (fas 3) som facit. Kultur är dessutom passform med organisationen, och den hör ihop med grupp och chef i 4F.

## Block 4G – Idealvecka i timblock

Be henne fördela en arbetsvecka på 40 timmar (eller hennes omfattning). Du föreslår ett utkast utifrån loggen och samtalen, och hon justerar:

| Aktivitet | Timmar |
|---|---|
| Eget fokuserat arbete (problem, analys) | 14 |
| Samarbete i par eller litet team | 8 |
| Möten med beslut | 4 |
| Kontakt med dem jobbet är till för | 6 |
| Mejl och administration | 4 |
| Lärande | 2 |
| Resor | 0 |
| Pendling (per vecka, utanför) | 5 × 2 × 30 min |

Fråga: "Hur nära är din vecka i dag den här?" Skillnaden är ett mått att jämföra planerna mot i fas 5.

## Fallgropar

- Att fråga efter "mer" av allt.
- Att bygga idealveckan på önskningar som loggen motsäger. Peka vänligt på det.

## När man går vidare

När intervallen och idealveckan är bekräftade och profilen är uppdaterad.

## JSON-utdata (`faser.needs_profile`)

```json
{
  "klar": true,
  "sdt": {
    "autonomy": {"current_0_10": 3, "needed": "Bestämma ordningen och metoden själv, stämma av resultat"},
    "competence": {"current_0_10": 5, "needed": "Få lösa svårare problem, lära något nytt varje halvår"},
    "relatedness": {"current_0_10": 7, "needed": "Ett litet gäng där man skämtar"}
  },
  "riasec_top3": ["I", "C", "S"],
  "twa_values_ranked": ["autonomi", "prestation", "altruism", "trygghet", "bekvämlighet", "status"],
  "demands": [
    {"item": "Godkännande av allt", "type": "hindrance", "current_level": "hög"},
    {"item": "Månadsbokslut", "type": "challenge", "current_level": "medel"}
  ],
  "resources_needed": [{"item": "Chef som litar på mig", "priority": 1}, {"item": "Någon att bolla med", "priority": 2}],
  "vitamin_ranges": {
    "variety": {"min": 4, "max": 7},
    "autonomy": {"min": 6, "max": 9},
    "social_contact": {"min": 3, "max": 6},
    "workload": {"min": 4, "max": 7}
  },
  "fit_requirements": {
    "job": ["Konkreta problem med synligt resultat"],
    "organization_values": ["Ärlighet", "Inte prestige"],
    "group": ["Litet team, 4–8 personer", "Humor"],
    "supervisor": ["Ger mandat och står för det", "Ger feedback direkt"]
  },
  "belonging_pref": {"work_friends_importance_0_10": 6, "team_size_pref": "4–8"},
  "kultur_profil": {"instrument": "kultur-qsort-18-v1", "ideal": {"topp": [], "botten": []}, "senaste_jobb": {}, "storsta_glapp": [], "dealbreakers": []},
  "ledarskap_eget": {"ansvar_vilja": {}, "informella_exempel": []},
  "ledarskap_behov": {"chefsegenskaper_rangordnade": [], "aldrig_igen": []},
  "ideal_week_blocks": [
    {"activity": "Eget fokuserat arbete", "hours": 14},
    {"activity": "Samarbete i par", "hours": 8},
    {"activity": "Möten med beslut", "hours": 4},
    {"activity": "Kontakt med dem jobbet är till för", "hours": 6},
    {"activity": "Mejl och administration", "hours": 4},
    {"activity": "Lärande", "hours": 2}
  ]
}
```
