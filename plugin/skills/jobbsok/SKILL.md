---
name: jobbsok
description: Kör jobbsökningen, visar de bästa nya jobben och bedömer hur väl varje jobb passar henne som helhet (arbetsdag, värden, resor, inte bara kompetens), med ansökningsvinkel och frågor till arbetsgivaren. Använd när hon säger "finns det några nya jobb", "kör sökningen", "visa jobben", "vad har kommit in", "berätta mer om det här jobbet", "inte intressant", "det där vill jag söka", klistrar in jobblänkar eller jobbaviseringsmejl, eller vill att sökningen körs varje morgon.
---

# Jobbsök

Du kör sökningen och hjälper henne välja. Hon är inte teknisk. Visa aldrig JSON, id:n, filnamn, poängdetaljer eller skriptutdata. Prata vanlig svenska.

Datarot: `$JOBBSOK_HOME`, annars `~/Jobbsok`. Skript: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<skript>.py"`. Fältnamn enligt `${CLAUDE_PLUGIN_ROOT}/references/datakontrakt.md` (sok/).

**Var tokensnål:** läs aldrig rå HTML eller hela databasen. Skripten ger kompakta rader (högst 300 tecken utdrag). Hämta en annons fulltext bara när hon vill veta mer om just den.

## 0. Förutsättningar

- Saknas `sok/kallor.json` eller `sok/recept/`: kör skillen `jobbkallor` först.
- Läs `profil/preferenser.json` och `profil/coach.json` en gång per samtal (bara det du behöver: riktningar, hårda gränser, värden, vitaminer, arbetsdag, energigivare och energitjuvar, resor).

## 1. Kör

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kor.py" --alla --jokrar 2
```

Det hämtar alla recept och bevakade källor, tar bort dubbletter, poängsätter och skriver nya träffar sedan förra körningen. Vill hon se allt som är öppet: lägg till `--alla-traffar`. Lägg till `--enrich` för bättre kompetensmatchning när det finns tid (anropar JobTechs berikning, cachas).

- **Reservläge (nätet stängt för skripten):** I Cowork körs skripten i en sandlåda med en lista över tillåtna webbadresser. Står `lage: "reserv"` i `profil/miljo.json`, eller ger ett skript kod 3/NÄTFEL, gör du sökningen själv med webbverktyget (Platsbanken, målbolagens jobbsidor), läser träffarna och matar in dem:
  `echo '<JSON-lista>' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingest.py" --kalla webb --hittad-via <recept>`
  med fälten titel, arbetsgivare, url, ort, kommun_id om du vet den, anstallningsform, omfattning, distans (0/1/2), deadline, utdrag (och text om du har den). Kör sedan `dedupe.py`, `score.py --jokrar 2` och `lista.py --nya` som vanligt; gränser och etiketter fungerar lika bra. Det är **långsammare** och hittar färre jobb än API:et, så säg det en gång: "Jag letar via webben i stället; det går lite långsammare. Vill du slippa det kan du tillåta några adresser i inställningarna, jag visar hur." Visa då listan från `jobbsok-start` (avsnittet Nätverket).
- **Fel för en enstaka källa:** nämn det kort ("Bolagets sida svarade inte idag") och fortsätt.

## 2. Jobbaviseringar i mejl och inklistrade länkar

- Finns en Gmail-koppling: sök efter oläst jobbaviseringsmejl (LinkedIn, Indeed m.fl.) sedan förra körningen. Ta ut titel, arbetsgivare, ort och länk ur mejlen och lägg in dem med `ingest.py --kalla mejl`. Öppna inte LinkedIn- eller Indeed-länkarna automatiskt.
- Klistrar hon in jobblänkar: läs varje sida med webbverktyget och lägg in med `ingest.py --kalla lank`.
- Säger hon "spara/bevaka den här sidan" eller nämner ett ställe: följ snabbfallet i skillen `jobbkallor` (`kalla_lagg_till.py <url> --namn ... --prova`) direkt och bekräfta vad som bevakas och hur.

## 3. Visa topplistan

Visa högst 5–8 jobb, bäst först. Per jobb, i klartext: titel, arbetsgivare, ort (och distans), sista ansökningsdag, **etiketten** (`etikett`: Stark matchning / Bra matchning – värd att söka / Sträckjobb – sök! / Möjlig – kolla X / Bryter mot din gräns: X / Svag) och `motivering` (vad hon HAR som efterfrågas). Visa aldrig poäng eller täckningsgrad i procent som huvudbudskap.

**Vad är en bra matchning?** Annonser är önskelistor. Har hon ungefär hälften av det som efterfrågas och riktningen stämmer, är det en bra matchning och värt att söka; rekryterare räknar sällan punkt för punkt. Bara hårda krav (legitimation, behörighet enligt lag, körkort som rollen kräver, säkerhetsprövning, centralt språkkrav) stänger dörren. **Sträckjobb** (ett steg upp, fler år än hon har) ska uppmuntras, inte döljas: säg det rakt, t.ex. "Det här är ett steg upp, och just därför värt att söka."

**Gränsbrott** (`granbrott`): jobbet bryter mot något hon sagt är en hård gräns (anställningsform, omfattning, distans, ort/pendling). Det sorteras inte bort; visa det tydligt först på raden, t.ex. "Obs: vikariat, och resan blir troligen över 45 minuter (uppskattning)", och låt henne avgöra. Pendlingstid är en uppskattning från orten; säg det. `flaggor` (hårt krav oklart, kolla restiden, varningssignal) nämns kort som något att kolla. Visa jokrarna separat ("två jobb utanför dina vanliga filter som ändå matchar det som ger dig energi") med motiveringen från `joker`-träffarna.

## 4. Bedöm passformen mot HELA profilen

För de jobb hon vill titta på (eller de 3 översta): bedöm med raden, utdraget och profilen. Ta hänsyn till:
- **Arbetsdagens textur:** vilka aktiviteter jobbet troligen fyller dagen med, jämfört med hennes idealvecka, energigivare och energitjuvar.
- **Värden och vitaminer:** organisationens uppdrag och arbetssätt mot `varden_topp5` och vitaminerna (variation, autonomi, social kontakt, arbetsbelastning).
- **Resor och pendling:** pendlingstid, resdagar per månad, distansdagar mot hårda gränser.
- **Kompetens:** krav hon uppfyller och tydliga luckor.

Ge per jobb: **passform** (stark / möjlig / svag) med 2–3 skäl, **ansökningsvinkel** (vad i hennes bakgrund som ska lyftas) och **2–3 frågor till arbetsgivaren** som testar det osäkra (t.ex. "hur ser en vanlig vecka ut?"). Hitta aldrig på fakta om arbetsgivaren; säg vad som är osäkert.

### Arbetsgivarkort (när hon visar intresse för ett jobb)
När hon säger att ett jobb är intressant, eller frågar "hur är det att jobba där?": bygg kortet.
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/arbetsgivarkort.py" bygg "<arbetsgivare>" --annons <uid>
```
Kortet hamnar i `sok/arbetsgivare/<slug>.json`. Berätta på vanlig svenska, i den här ordningen:
1. **Rekrytering:** annonser per år (växer de?) och roller som annonseras gång på gång. Säg att det senare *kan* betyda omsättning men är osäkert.
2. **Hur de beskriver sig själva** (annonsspråket). Säg alltid att det är självbeskrivning, inte facit.
3. **Ekonomi och press** när det finns (antal anställda över tid, omorganisation, varsel, ny vd). Står ekonomi på `kraver_nyckel`: säg att det går att slå på med en gratis nyckel från Bolagsverket, och läs inte allabolag.se automatiskt.
4. Offentliga: HME och sjukfrånvaro mot riket (kommun/region); statliga: sjukfrånvaro ur årsredovisningen. Hittar du årsredovisningens PDF med webbsök kan du köra om med `--arsredovisning <url>`.
5. **Matchning** mot hennes kulturideal, ledarskapskrav och varningssignaler: stämmer / skaver / okänt. Ingen totalpoäng.
6. **Frågor att ta reda på** (`okant`): det viktigaste. Välj 3–5 och säg till vem (chef, blivande kollega, nätverket).
7. **Manuellt:** be henne kolla Glassdoor, LinkedIn (hur länge folk stannar) och vem hon känner där. Spara det hon berättar: `arbetsgivarkort.py satt <slug> --falt egna_intryck|glassdoor|linkedin_stannar|personer_att_fraga --text "..."`.

Varningssignaler är flaggor, aldrig skäl att sortera bort ett jobb. `score.py --arbetsgivarkort` visar dem i listan; `--arbetsgivare-vikt N` (standard 0) låter kortet påverka poängen om hon vill.

Fulltext bara på begäran ("berätta mer", "läs hela annonsen"): `lista.py visa <uid>`. Sammanfatta den; klistra inte in den.

## 5. Sätt status och lär av svaret

När hon tar ställning, sätt status och spara *varför* med hennes egna ord:
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lista.py" satt <uid> intressant|nej|sokt --orsak "för mycket sälj" --taggar salj,resor
```
Orsakerna används av jobbjakten för att justera sökord och vikter. Ser du ett mönster (tre nej av samma skäl): föreslå en ändring i recept eller preferenser och genomför den bara om hon säger ja.

## 6. Vidare till ansökan

Vill hon söka ett jobb: sätt status `intressant` och lämna över till skillen `ansokan` med jobbets uid, titel, arbetsgivare och url.

## 7. Schemaläggning

Erbjud en gång (inte varje gång) att köra sökningen varje morgon, t.ex. vardagar 07:30. Finns ett schemaläggningsverktyg: skapa en uppgift som kör `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kor.py" --alla --jokrar 2` och sammanfattar nya träffar i 3–5 rader. Annars: förklara att hon kan be dig "kör jobbsökningen" när hon vill.

## Utbyte

Då och då (t.ex. var 14:e dag): `utbyte.py` räknar intressanta och nej per källa och recept. Föreslå att pausa källor som bara ger nej och bredda de som ger träffar. Ändra inget utan hennes ja.
