---
name: faktabank
description: Använd när hon vill bygga, fylla på eller rätta sin faktabank – det alla CV och brev hämtar från. Till exempel "lägg in mitt gamla CV", "här är min LinkedIn-export", "jag vill berätta om mitt jobb på X", "lägg till en kurs", "det där stämmer inte", "översätt mina meriter till engelska" eller "vilka kompetenser har jag". Intervjuar roll för roll, en fråga i taget, och sparar bara det hon står för.
---

# Faktabanken

Faktabanken (`profil/fakta.json` i hennes mapp) är den enda källan till sanning om henne. Allt som senare står i CV, brev och formulär måste gå att spåra hit. Ditt jobb är att få in det som stämmer, i en form som går att återanvända, utan att hitta på.

Datamapp: `$JOBBSOK_HOME`, annars `~/Jobbsok`. Finns den inte: följ steg 1 i `jobbsok-start` först.
Fullständigt format: `references/format.md`. Läs det innan du skriver första gången.

## Grundregler

- **Hitta aldrig på.** Ingen siffra, titel, period eller merit som hon inte själv sagt eller som inte står i ett underlag hon gett dig. Är du osäker: fråga.
- **Siffror bara när hon står för dem.** Fråga "Är det en siffra du kan stå för om någon frågar?" Ja och den finns i ett dokument → `kalla: "dokumenterat"`. Ja ur minnet → `kalla: "egen_uppgift"`. Nej → ingen siffra; beskriv omfattning i stället (`omfattning`: "team 6 pers", "5 enheter").
- **`belagg`** för varje merit: `verifierat` om det finns ett underlag (intyg, rapport, CV hon skrev då), annars `egen_uppgift`.
- **En fråga i taget.** Vänta på svaret. Sammanfatta kort efter varje roll.
- **Hennes ord först.** Formulera meriten, visa den, och låt henne rätta. Använd hennes egna uttryck när de är bra; spara dem hon gillar i `profil/rost.json` → `gillade_formuleringar`.
- **Spara aldrig** personnummer, ålder, födelsedatum eller civilstånd, även om de står i underlaget.
- **Validera efter varje ändring:**
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" "<home>/profil/fakta.json"`
  Rätta felen direkt utan att nämna det tekniska.
- Skriv filen hel och giltig. Behåll allt som finns; ändra bara det ni pratat om.

## Steg 1 – Utgångsläge

Läs `profil/fakta.json`. Är den tom: fråga **först** om hon har ett CV, även ett gammalt eller halvfärdigt ("Har du ett CV liggande, hur gammalt som helst? Då slipper vi börja från noll."). Andra vägar, som går att kombinera: LinkedIn-export, eller att berätta fritt.

Har den innehåll: visa kort vad som finns (roller, antal meriter, vad som saknas enligt `status.py`) och fråga vad hon vill göra.

## Steg 2 – Import och aktualitet

Detaljer per källa i `references/import.md`. Allt importerat är ett **utkast** och räknas som hennes egna uppgifter (`belagg` och siffrornas `kalla` = `egen_uppgift`) tills hon säger något annat. Siffror bekräftas.

Efter ett CV: visa en **aktualitetsanalys** i högst sex rader innan intervjun (se import.md): CV:ts ålder, luckan fram till i dag, "pågående" roller som kanske slutat, inaktuella verktyg och termer, saknade sektioner, och vad som är för långt eller kort. Fråga om det finns formuleringar hon gillar i det gamla CV:t (→ `rost.json` `gillade_formuleringar`) och anteckna hur det såg ut.

Logga aldrig in på LinkedIn och skrapa aldrig.

## Steg 3 – Intervju per roll (kärnan)

Gå roll för roll, senaste först. Frågebank och exempel i `references/intervju.md`.

**Finns ett importerat CV:** gör en riktad uppdatering, inte en full intervju. Fråga först vad som hänt sedan CV:t skrevs (ny roll, nya uppgifter i samma roll, kurser, ideellt). Ny uppgift hos samma arbetsgivare med ny titel blir en ny roll; samma titel blir nya meriter. Bekräfta sedan de gamla raderna i klump ("De här fyra ser bra ut, stämmer de fortfarande?") och fördjupa bara de svaga: utan resultat, "ansvarade för", oklara siffror.

Annars, för varje roll:

1. **Grunduppgifter:** arbetsgivare, titel, ort, start och slut (`YYYY-MM`). Bekräfta.
2. **Sammanhang:** vad organisationen gjorde och vad rollen fanns till för (blir `beskrivning`, 1–2 meningar).
3. **Meriter i CAR-form**, en åt gången:
   - *Utmaning:* "Vad var det som behövde lösas?"
   - *Handling:* "Vad gjorde du, konkret?"
   - *Resultat:* "Vad blev annorlunda efteråt?"
   - *Omfattning:* team, budget, antal kunder/enheter.
   - *Siffror:* bara enligt grundreglerna ovan.
   Komprimera till **en rad**: verb i preteritum + vad + resultat, eller omfattning när hon inte kan nämna ett resultat. Hitta aldrig på ett resultat för att raden ska bli snyggare. Visa raden, låt henne rätta.
**Flaggat från coachen:** om `profil/coach.json` har `faser.needs_profile.ledarskap_eget.informella_exempel` med `till_faktabanken: true` och `faktabank_status: "flaggad"` för den här rollen, ta upp dem som förslag med hennes ord ("I coachningen berättade du att du …. Ska det med?"). Ställ CAR-frågorna som vanligt; lägg inte till resultat eller "ledde" som hon inte sagt. Sätt sedan `faktabank_status` till `bekraftad` (+ `fakta_id`) eller `avbojd`.
4. Sikta på 3–5 meriter för de senaste rollerna, 1–2 för äldre. Fråga om det finns något hon är stolt över som inte kommit upp.
5. Spara rollen, validera, sammanfatta i tre rader och fråga om nästa roll.

Meritens id är `<roll-id>-m<n>`. Ändra aldrig id på en befintlig merit (ansökningar refererar till dem).

## Steg 4 – Övrigt

Utbildning, kurser, språk (nivå: modersmål, flytande, god, grundläggande), ideellt, körkort, länkar, referenser (namn, roll, kontakt, relation; används "på begäran"). En sak i taget, korta frågor.

`sammanfattning_rad`: när rollerna är klara, föreslå en mening om vem hon är yrkesmässigt, byggd bara på faktabanken. Låt henne skriva om.

## Steg 5 – Kompetenser och taxonomi

1. Föreslå kompetenser utifrån meriterna. Hon godkänner listan och nivå (`expert`, `van`, `grund`).
2. Mappa varje kompetens till JobTech taxonomi:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/taxonomy.py" sok "<kompetens>" --home "<home>"`
   - Exit 0: välj den träff som bäst motsvarar det hon menar och sätt `taxonomi_id`. Flera rimliga: fråga henne med vanliga ord.
   - Exit 3 (nätet blockerat): hämta URL:en i `url` med webbverktyget, spara svaret och kör
     `taxonomy.py spara "<kompetens>" --fil <svar.json> --home "<home>"` så att det cachas i `cache/taxonomy/`.
   - Ingen träff: `taxonomi_id: null`. Det är okej.
3. Lägg samma id i meriternas `taggar` där det passar, så matchar jobbsökningen rätt.

## Steg 6 – Engelska

Fråga om hon söker jobb på engelska (`preferenser.sprak_ansokan`). I så fall: översätt alla Txt-fält till `en`, troget och utan att förstärka. Visa roll för roll och låt henne godkänna. Fråga om svenska titlar ska stå kvar som egennamn.

## Steg 7 – `aldrig_pastaa`

Under hela samtalet: när hon säger att något *inte* stämmer, är överdrivet eller känsligt ("jag hade inget formellt personalansvar", "jag är inte certifierad", "nämn inte sjukskrivningen"), lägg till en rad i `aldrig_pastaa` med hennes ord. Fråga en gång i slutet: "Finns det något du inte vill att jag någonsin påstår om dig?" Skrivlagret och formulärskillen läser den här listan.

## Avslut

Kör `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/status.py" --format json --home "<home>"` och berätta fyllnadsgraden och vad som saknas. Föreslå nästa steg (oftast `cv-design`). Hon kan alltid komma tillbaka och rätta: "säg bara 'ändra i faktabanken'".
