# Fas 5 – Möjliga vägar

**Mål:** ta fram realistiska vägar och pröva dem mot det hon vet, inte mot drömmar. Ordningen är fast: **job crafting först**, sedan tre Odyssey-planer.
**Ingång:** fas 4 klar.
**Tid:** 2 pass. Det är här titlar äntligen får dyka upp.

## Block 5A – Job crafting först

Säg varför: "Innan vi tittar på andra jobb vill jag pröva en sak: går det nuvarande att forma om? Ibland är det inte jobbet utan fördelningen som är fel. Och om svaret är nej vet vi också mer."
(Om hon saknar jobb: gör övningen på det senaste jobbet, kort, som underlag för vad hon ska leta efter. Hoppa annars över till 5B.)

1. **Uppgifter.** "Rita din vecka som block: vilka uppgifter tar hur mycket tid?" Jämför med idealveckan från fas 4.
   - "Vilka 10 % skulle du vilja göra till 30 %?"
   - "Vad kan du lämna ifrån dig, byta bort eller göra kortare?"
2. **Relationer.** "Vilka på jobbet ger dig energi? Kan du jobba mer med dem? Vem skulle du vilja lära känna?"
3. **Synen på jobbet.** "Vem är det egentligen till för? Om du ser det så, ändras något?"
4. **Genomförbarhet:** "0–10, hur troligt är det att du får göra de här ändringarna? Vem bestämmer?" och "Vad skulle hända om du frågade?"

Om genomförbarheten är 6 eller högre och värdena från fas 2 inte kränks i grunden: föreslå att crafting blir **ett** av experimenten i fas 6. Om den är låg: notera varför, det säger något om vad som inte får finnas på nästa arbetsplats.

## Block 5B – Tre Odyssey-planer

Förklara: "Nu tre helt olika versioner av de närmaste fem åren. Alla tre ska vara på riktigt möjliga, ingen är fel."
1. **Plan A – Nuvarande spår:** det du gör nu, eller den naturliga fortsättningen.
2. **Plan B – Om det spåret försvann:** om ditt yrke inte fanns i morgon, vad skulle du göra?
3. **Plan C – Om pengar och vad andra tycker inte spelade någon roll.**

Per plan, en i taget:
- "Ge den en rubrik, som i en tidning."
- "Vilka tre frågor skulle planen besvara åt dig?"
- Fyra mätare 0–10: **resurser** (har jag tid, pengar och kontakter?), **gillande** (hur mycket lockar den?), **självförtroende** (tror jag att jag kan?), **koherens** (hänger den ihop med vem jag är?).
- "Hur ser en vanlig tisdag ut i den planen, timme för timme?" (focalism-skydd, se samtalsteknik.md). Detta är den viktigaste frågan i fasen. Gör den ordentligt för de **en eller två planer hon lockas mest av**, inte för alla tre. Att gå igenom tre tisdagar blir tjatigt.

Ta mätarna snabbt (alla fyra i ett meddelande går bra) och lägg tiden på rubriken och tisdagen. Fråga om planer som hon själv avfärdar med "nej, det där går ju inte": "Vad skulle krävas?", innan du låter den gå.

Nu får du föreslå konkreta roller eller arbetsområden **utifrån mönster** ("du dras mot att reda ut problem åt någon i ett litet team: det finns i till exempel controllerroller i mindre bolag, verksamhetsutveckling i kommuner, eller support för ekonomisystem"). Föreslå, motivera från hennes data, och låt henne välja.

## Block 5C – Rollkort: gör varje riktning konkret och belagd

När hon har pekat ut riktningar (ur Odyssey-planerna och dina förslag): ta fram ett **rollkort** per riktning, 3–5 st, och alltid ett för att stanna och forma om nuvarande jobb. Ett rollkort ersätter vaga omdömen ("det skulle passa dig") med det annonserna och hennes egna ord faktiskt säger.

```bash
S="${CLAUDE_PLUGIN_ROOT}/scripts/rollkort.py"
python3 "$S" bygg --stanna
python3 "$S" bygg --roll "kommunikatör" --region "Uppsala län"     # en per riktning
python3 "$S" glapp <slug>
```
`bygg` hämtar ur JobTech: riktiga titlar, vanligaste arbetsgivare i regionen, annonser per år och trend, de 5–8 vanligaste arbetsuppgifterna (teman med exempelmeningar ur annonserna), vanliga krav och 3 aktuella annonser. Lönen kommer från SCB (snittlön per yrkesgrupp, riket och riksområdet). Allt cachas. Exit 3 betyder nätfel: säg det och använd webbsök för de 3 aktuella annonserna, men hitta inte på siffror.

**Så fyller du kortet (reglerna):**
1. **Arbetsuppgifterna.** Läs `arbetsuppgifter_till_claude` (teman med 2 exempelmeningar) och skriv en mening per tema med annonsernas ord: `rollkort.py satt <slug> --falt uppgift --uppgift <i> --text "..."`. Skriv inte till något som inte står i exemplen.
2. **"Passar för att" citerar henne.** Varje påstående har hennes ord med fas och fält: `rollkort.py citat <slug> --typ passar --text "Skrivandet är kärnan: 29 % av annonserna" --citat "Skriva klart en text som någon faktiskt förstår" --fas energy_log --falt "patterns.energizers[0]"`. Skriptet vägrar om citatet inte finns ordagrant där. Hittar du inget citat finns inget belägg, och då stryker du påståendet.
3. **Skavet visas lika tydligt som passformen.** Minst lika många `--typ skav` som `passar`, med hennes ord (energitjuvar, kränkta värden, hårda gränser).
4. **Glappet: hårda krav eller önskelista.** Säg det rakt till henne: "Annonser är arbetsgivarens önskelistor. Man får ofta jobbet utan att uppfylla allt, och det är vanligt att söka en bra bit över det man själv tror." `glapp` delar kraven i **hårda krav** (legitimation, lagstadgad behörighet eller certifiering, körkort när rollen kräver det, säkerhetsprövning, centralt språkkrav) och **önskelista** (allt annat). Bara ett saknat hårt krav är ett skav, och då med vad som krävs för att skaffa det. Önskelistan visar du som "vanligt efterfrågat: du har X av Y", aldrig som ett underkännande. Ta med rollkort **en nivå över hennes nuvarande** (till exempel strateg, ansvarig eller senior) när riktningen stämmer; underskatta henne inte för att önskelistan är lång.
5. **Varje marknadspåstående har en siffra eller en annons.** "65 annonser 2025 i Uppsala län, stabilt", "Uppsala universitet: 37 annonser på tre år", "48 400 kr i snitt (SCB 2025, riket)". Aldrig "efterfrågat", "växande" eller "bra betalt" utan siffran.
6. **Den vanliga tisdagen bygger på riktiga arbetsuppgifter.** Lägg tisdagen timme för timme av temana och ange vilka: `rollkort.py satt <slug> --falt vanlig_tisdag --uppgift 0 --uppgift 2 --text "..."`. Fråga sedan henne: "Vad gör du kl. 14.30?"
7. **Inga adjektiv utan belägg.** Ord som "spännande", "kreativ" och "stimulerande" stryks om de inte är hennes egna ord (citerade) eller annonsens (med annons-id).
8. **Kontrollera innan du visar:** `rollkort.py kontrollera --alla`. Flaggor (exit 1) rättas eller stryks. "Väntar på research" (kultur, ledarskap, arbetsidentitet, fackets lön) är tomma krokar: säg rakt att de inte är bedömda än, och gissa inte.

**Visa henne korten** i klartext, ett i taget och kort: titel, 2 citat, siffrorna, tisdagen och skavet. Visa sedan matrisen:
```bash
python3 "$S" jamfor --md
```
Den jämför värden, arbetsdag och energi, hårda gränser, hårda krav och önskelista (bara saknade hårda krav drar ner), marknadsvolym samt kultur och ledarskap (tomma tills vidare) med vikter. Säg att det är "en karta, inte en dom", visa vikterna och fråga: "Stämmer vikterna, eller väger något tyngre för dig?" Ändrar hon: skriv `rollkort_vikter` i `profil/preferenser.json` (t.ex. `{"varden":4,"marknad":0}`), validera och kör `jamfor` igen. Kolumnen "täckning" visar hur mycket som gick att bedöma. Läs aldrig ett högt totalvärde med låg täckning som ett ja.

**Huvudbudskapet är etiketten, inte siffran.** Varje riktning har `etikett` och `motivering` (Stark riktning / Bra riktning – värd att pröva / Sträckriktning – pröva gärna / Möjlig – kräver X / Bryter mot din gräns: X). Säg etiketten och det som talar för, och nämn totalen bara som sortering. Önskelistan i glappet är inget underkännande: har hon hälften och riktningen stämmer är det en bra riktning. Saknas inga hårda krav är en sträckriktning något att uppmuntra, inte avråda från.

Översikten visar korten under "Riktningar" när den byggs om (`oversikt.py`).

## Block 5D – Jämför mot data och gränser

Matrisen från rollkorten (5C) är grunden. Komplettera med det den inte täcker, till exempel:

| | Plan A | Plan B | Plan C |
|---|---|---|---|
| Värden topp 5 (hur många uppfylls) | 2/5 | 4/5 | 4/5 |
| Behov och vitaminer inom intervallen | delvis | ja | social kontakt för låg |
| Hårda gränser (pendling, resor, lön) | ok | ok | **lön under golvet år 1–2** |
| Arbetsdagens textur mot idealvecka | 40 % lika | 70 % | okänt |
| Energidata från loggen | dränerande mejlflöden | flowvillkor finns | okänt |

Kalla det "en karta, inte en dom". Det som strider mot en hård gräns ska sägas rakt: "Plan C bryter mot lönegolvet du satte. Vill du flytta golvet medvetet, eller ska planen ändras?"

## Block 5E – Flaggor för prognosfel

Gå igenom varje plan och sätt flaggor där hon kanske gissar fel. Säg det vänligt och med en motfråga:
- `focalism`: hon tänker bara på en sak (uppgiften) och glömmer resten av dagen. → "Vad gör du kl. 14.30 en tisdag?"
- `impact_bias`: "allt kommer att bli bra/hemskt". → "Hur kändes det tre månader efter förra bytet?"
- `titel_eller_lon`: lockelsen bygger på status eller lön, som vi vänjer oss vid. → "Om lönen var samma, skulle den locka lika mycket?"
- `pendling_underskattad`: lång resväg ses som en detalj. → "Det är x timmar i veckan. Vad skulle du annars göra med dem?"
- `peak_end`: bilden av ett yrke bygger på ett starkt minne eller en enskild person.
- `ingen_logg`: det finns ingen upplevelsedata att jämföra med.
- `borde`: planen drivs av ett "borde" från fas 2.

Flaggorna är inte nej. De blir hypoteser att pröva i fas 6.

## Fallgropar

- Tre varianter av samma plan. Om B och C liknar A: "Gör C riktigt galen, vi kan alltid tämja den."
- Att ranka planerna åt henne. Fråga: "Vilken vill du veta mer om?"
- Att glömma crafting.
- Att hon kastar en plan för att hon "inte kan". Fråga vad som skulle behövas.

## När man går vidare

När hon har valt 1–2 planer (eller crafting) att pröva, och flaggorna är omsatta i frågor.

## JSON-utdata (`faser.options`)

```json
{
  "klar": true,
  "crafting_option": {
    "task": ["Ta över analysen av avvikelser (10 % → 30 %)", "Lämna fakturakontroll till nya kollegan"],
    "relational": ["Fler ärenden med Sara", "Fråga om att sitta med verksamhetscontrollern en dag i veckan"],
    "cognitive": ["Se rapporterna som verktyg för rektorerna, inte för ekonomichefen"],
    "feasibility_0_10": 4
  },
  "odyssey_plans": [
    {
      "id": "A",
      "headline": "Ekonom som får bestämma själv i en mindre organisation",
      "questions": ["Finns friheten på riktigt i mindre bolag?", "Räcker lönen?", "Blir det ensamt?"],
      "resources_0_10": 8, "like_0_10": 6, "confidence_0_10": 8, "coherence_0_10": 6,
      "fit_scores": {"values": "3/5", "needs": "delvis", "constraints_ok": true, "day_texture_match": "60 %"},
      "forslag_roller": ["Redovisningsekonom", "Controller i mindre bolag"]
    },
    {
      "id": "B",
      "headline": "Den som reder ut systemen åt andra",
      "questions": ["Gillar jag supportsamtal hela dagen?", "Behövs certifiering?", "Vad tycker de som gör det?"],
      "resources_0_10": 6, "like_0_10": 8, "confidence_0_10": 5, "coherence_0_10": 8,
      "fit_scores": {"values": "4/5", "needs": "ja", "constraints_ok": true, "day_texture_match": "70 %"},
      "forslag_roller": ["Systemförvaltare ekonomisystem", "Applikationsspecialist"]
    },
    {
      "id": "C",
      "headline": "Snickerier och restaurering i egen regi",
      "questions": ["Kan jag leva på det?", "Tål kroppen det?", "Saknar jag kolleger?"],
      "resources_0_10": 3, "like_0_10": 9, "confidence_0_10": 3, "coherence_0_10": 7,
      "fit_scores": {"values": "4/5", "needs": "social kontakt för låg", "constraints_ok": false, "day_texture_match": "okänt"}
    }
  ],
  "forecast_bias_flags": [
    {"plan_id": "C", "flagga": "focalism", "fraga": "Hur ser fakturering, kundjakt och ensamma dagar ut?"},
    {"plan_id": "B", "flagga": "peak_end", "fraga": "Bilden bygger på en konsult hon gillade. Prata med tre andra."}
  ],
  "valda_for_test": ["B", "crafting"],
  "rollkort": ["stanna", "systemforvaltare-uppsala"]
}
```
