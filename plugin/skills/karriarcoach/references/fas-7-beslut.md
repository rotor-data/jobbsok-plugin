# Fas 7 – Beslut

**Mål:** en riktning formulerad med hennes ord, det som inte är förhandlingsbart, och konkreta nästa steg. Sedan skrivs `preferenser.json`, som styr jobbsökningen.
**Ingång:** minst ett experiment med resultat, eller att hon uttryckligen vill bestämma nu (notera det i så fall).
**Metod:** MI, att framkalla och förstärka förändringsprat, och att respektera ambivalens.

## Block 7A – Låt henne formulera beslutet

Läs upp en kort sammanfattning av resan (3–6 meningar ur profilen) och fråga sedan:
- "Vad tänker du när du hör det?"
- "Vart lutar det åt nu?"
- "Vad är det som gör att det lutar dit?" (önskan, skäl, behov)
- "Vad kan göra det svårt? Vad har du som gör att du klarar det?" (förmåga)
- Skalfråga: "Hur bestämd är du, 0–10?" och "Varför inte lägre?" (`commitment_0_10`)

Lyssna efter DARN-CAT och spara ordagranna citat (`change_talk`): `desire` ("jag vill"), `ability` ("jag kan"), `reason` ("för att"), `need` ("jag måste"), `commitment` ("jag ska"), `activation` ("jag är redo"), `taking_steps` ("jag har redan").

Om hon fortfarande tvekar: respektera det. "Det låter som att du inte är klar, och det är okej. Vad skulle du behöva veta för att bli det?" Ett nytt experiment är ett bra utfall. Om hon väljer att stanna och crafta: det är också ett beslut. Då kan preferenser.json fortfarande skrivas, med en smalare sökning, eller skjutas upp.

## Block 7B – Icke förhandlingsbart och nästa steg

- "Vilka tre saker får nästa jobb inte sakna?" och "Vad får det absolut inte innehålla?"
  Psykoedukation, en mening, om hon väger lön mot restid eller titel mot vardag: "Folk brukar överskatta hur mycket en högre lön eller finare titel betyder efter ett år, och underskatta hur mycket pendlingen och chefen gör. Därför ligger de högt här."
- Nästa steg: "Vad gör du först, och när?" Två eller tre steg, med datum. Föreslå ett uppföljningsdatum (`review_date`, ofta efter 4–6 veckor).

## Block 7C – Skriv preferenser.json

Översätt det ni kommit fram till. Använd **hennes gränser** från fas 1 (eller justerade senare, med hennes godkännande). Läs datakontraktet för formatet.

Fyll i:
- `riktningar`: en per vald riktning. `namn` med hennes ord, `sokord` (vardagliga ord och titlar som förekommer i annonser, 4–10 st, inklusive synonymer), `exkludera_ord` (det hon inte vill ha, till exempel "säljare", "provision", "skift"). `yrkes_id` lämnas tomt (`[]`) om du inte har taxonomi-ID. Jobbsökningen kompletterar senare.
- `orter`: från fas 1. `kommun_id` och `region_id` lämnas tomma om du inte vet dem.
- `hårda_gränser`: pendling i minuter, färdsätt, resdagar per månad, distansdagar, lönegolv per månad (eller `null`), anställningsform och omfattning (fråga om de saknas).
- `varden_topp5`: från fas 2, i rangordning.
- `vitaminer`: från fas 4 (`variety`→`variation`, `autonomy`→`autonomi`, `social_contact`→`social_kontakt`, `workload`→`arbetsbelastning`).
- `arbetsdag`: idealveckan (`aktivitet`, `timmar`), energigivare och energitjuvar från loggen (med hennes ord).
- `kompetens_id`: lämna `[]` om faktabanken inte har ID. Kompetenser är inte coachens huvudsak.
- `exkludera_arbetsgivare`: fråga ("Finns det arbetsgivare du inte vill se?").
- `sprak_ansokan`: fråga om hon vill söka på engelska också.
- `kultur_ideal` (om Q-sorten är gjord): `{"instrument": "kultur-qsort-18-v1", "topp": [...], "botten": [...]}` direkt ur `kultur_profil.ideal`.
- `ledarskap_krav`: `{"ansvar": "ingen|sak|personal", "chefsegenskaper_topp3": [...], "avstamning_frekvens": "...", "krav": ["hennes ord, t.ex. 'chef som ger mandat och står för det'"]}` ur `ledarskap_eget.ansvar_vilja` (högsta skalan) och `ledarskap_behov`.
- `varningssignaler`: korta formuleringar som jobbsökningen, arbetsgivarkortet och rollkorten letar efter, ur `ledarskap_behov.aldrig_igen` och `kultur_profil.dealbreakers`, med hennes ord ("chef som tar upp fel inför gruppen", "intern tävling"). Lägg inte in sådant hon inte sagt.

Visa i klartext innan du sparar:
> "Så här kommer jobbsökningen att leta: jobb som [riktning], med sökord som ..., inom 40 minuter med buss eller cykel från Uppsala, högst två resdagar i månaden, 1–3 distansdagar, minst 34 000 kr i månaden. Den hoppar över annonser med ord som 'säljare' och 'skift'. Stämmer det, eller ska något ändras?"

Spara därefter till `$JOBBSOK_HOME/profil/preferenser.json`, med `schema_version: 1`, och validera:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" "$JOBBSOK_HOME/profil/preferenser.json"
```

Exempel:
```json
{
  "schema_version": 1,
  "riktningar": [
    {"namn": "Den som reder ut systemen åt andra", "yrkes_id": [], "sokord": ["systemförvaltare", "applikationsspecialist", "ekonomisystem", "förvaltningsledare", "superanvändare", "verksamhetsutvecklare ekonomi"], "exkludera_ord": ["säljare", "provision", "skift"]}
  ],
  "orter": [{"namn": "Uppsala", "kommun_id": "", "region_id": ""}],
  "hårda_gränser": {"max_pendling_min": 40, "pendling_satt": "kollektivt", "max_resdagar_manad": 2, "distans_dagar": {"min": 1, "max": 3}, "lonegolv_manad": 34000, "anstallningsform": ["tillsvidare"], "omfattning": ["heltid"]},
  "varden_topp5": ["Tillit", "Erkännande", "Lärande", "Humor", "Balans"],
  "vitaminer": {"variation": {"min": 4, "max": 7}, "autonomi": {"min": 6, "max": 9}, "social_kontakt": {"min": 3, "max": 6}, "arbetsbelastning": {"min": 4, "max": 7}},
  "arbetsdag": {
    "idealvecka": [{"aktivitet": "Eget fokuserat arbete", "timmar": 14}, {"aktivitet": "Samarbete i par", "timmar": 8}],
    "energigivare": ["Lösa ett konkret problem med en annan person"],
    "energitjuvar": ["Möten där inget beslutas"]
  },
  "kompetens_id": [],
  "exkludera_arbetsgivare": [],
  "sprak_ansokan": ["sv"],
  "kultur_ideal": {"instrument": "kultur-qsort-18-v1", "topp": ["s10", "s12", "s16", "s7"], "botten": ["s15", "s4", "s2", "s6"]},
  "ledarskap_krav": {"ansvar": "sak", "chefsegenskaper_topp3": ["ger_frihet", "tillganglig", "skyddar"], "avstamning_frekvens": "veckovis", "krav": ["Chef som ger mandat och står för det"]},
  "varningssignaler": ["Chef som tar upp fel inför gruppen", "Intern tävling"]
}
```

## Block 7D – Uppföljning och avslut

Efter att preferenserna sparats, i ett meddelande: "Samma tre siffror som i början, 0–10: hur klart är det vad du vill, hur mycket tror du på att du hittar rätt, hur nöjd är du med nuvarande jobb? Och en till: hur väl har du känt dig förstådd i de här samtalen?" Spara i `uppfoljning.efter_coachning`. Visa skillnaden mot baslinjen i **en** mening, utan att tolka den som ett betyg: "Klarheten gick från 3 till 7." Om den inte rört sig: säg det rakt och fråga vad som hade hjälpt.

Erbjud en uppföljning 3 och 6 månader in i ett nytt jobb (trivsel 0–10, samma 18 kultursatser för det faktiska jobbet, "min chef ger mig utrymme och backar mig" 0–10, "skulle du välja samma igen?"). Spara som `uppfoljning.nytt_jobb[]` när det blir av. Det är en uppföljning för henne, inte evidens.

Påminn om en mänsklig samtalspartner om hon inte redan har en (se "Alliansen" i SKILL.md).

Avsluta med att visa den slutliga profilen (se syntes.md) och erbjud nästa steg: att börja söka jobb eller att bygga faktabanken och CV:t.

## Fallgropar

- Att formulera beslutet åt henne. Använd hennes ord, även om de är mindre eleganta.
- Att skriva för breda sökord så att hon drunknar, eller för smala så att inget kommer. 4–10 sökord per riktning.
- Att tyst mjuka upp en hård gräns för att få fler träffar. Fråga alltid.

## JSON-utdata (`faser.decision`)

```json
{
  "klar": true,
  "chosen_path": "Systemförvaltning av ekonomisystem, i en organisation där man litar på varandra",
  "rationale_in_client_words": "Jag får lösa problem åt folk utan att någon ska godkänna varje steg, och det är fortfarande ekonomi som jag kan.",
  "change_talk": [
    {"type": "desire", "quote": "Jag vill vara den man ringer när det krånglar"},
    {"type": "taking_steps", "quote": "Jag har redan pratat med två"}
  ],
  "commitment_0_10": 8,
  "next_steps": [
    {"action": "Uppdatera CV med systemerfarenheten", "by": "2026-11-10"},
    {"action": "Ringa Annas kollega om öppna roller", "by": "2026-11-05"}
  ],
  "review_date": "2026-12-15",
  "non_negotiables": ["Max 40 min resa", "Chef som ger mandat", "Hämta 16.30 två dagar i veckan"],
  "beslut_utan_experiment": false
}
```
