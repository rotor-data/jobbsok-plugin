---
name: jobbkallor
description: Sätter upp och fyller på var jobben ska letas, alltså Platsbanken via JobTech, målbolagens karriärsidor, Varbi-flöden, jobbsajter och jobbaviseringar i mejl, och sparar det som källor och sökrecept. Använd första gången jobbsökningen ska komma igång, och när hon säger "var ska vi leta", "lägg till ett ställe", "spara den här sidan", "bevaka X", "bevaka karriärsidan hos ...", "jag vill ha jobb från LinkedIn", "målbolag", "pausa/ta bort en källa" eller klistrar in en karriärsida eller en jobbsajt-sökning.
---

# Jobbkällor

Du sätter upp var jobben hämtas. Hon är inte teknisk. Visa aldrig JSON, id:n, filnamn eller skriptutdata. Säg vad du gör i en mening i taget och bekräfta med vanliga ord vad som bevakas och hur.

Datarot: `$JOBBSOK_HOME`, annars `~/Jobbsok`. Skript: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<skript>.py"`. Fältnamn enligt `${CLAUDE_PLUGIN_ROOT}/references/datakontrakt.md` (avsnitt sok/). Bakgrund om källorna: `references/kallor.md`.

## Snabbfall: hon vill spara ett ställe

När hon nämner eller klistrar in en sida ("spara den här", "bevaka Region Uppsalas jobb", en länk till en karriärsida eller en sökning på en jobbsajt): lägg till den direkt, utan att fråga först.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kalla_lagg_till.py" "<url>" --namn "<bolag/sajt>" --prova
```

Läs `beskrivning` och `provhamtning` i svaret och bekräfta i en mening, t.ex. "Klart, jag bevakar Teamtailor-flödet hos Bolaget. Där finns 12 jobb just nu." Tolkning:
- **Flöde hittat** (teamtailor_rss, lever, ashby, greenhouse, smartrecruiters, workday, rss): det bästa läget, eftersom alla jobb kommer med automatiskt.
- **pagehash med lankmonster:** "jag läser sidan varje gång och plockar ut nya annonslänkar".
- **pagehash utan lankmonster:** "jag säger till när sidan ändras". Jobblistor som byggs med JavaScript syns inte; säg det om provhämtningen bara ger en träff.
- **sok_url:** hennes sökning med filter är sparad och nya annonslänkar plockas ut.
- **mejl** (LinkedIn, Indeed, Glassdoor): förklara att sajten inte får läsas automatiskt och hjälp henne skapa en jobbavisering där (se nedan).
- **Fel "blockerar automatisk hämtning":** erbjud mejlavisering (`--typ mejl`) eller att du tittar med webbverktyget när hon ber om det.

Hon hittar själv en sajt som bara har mejlaviseringar: `kalla_lagg_till.py "<url>" --namn "<sajt>" --typ mejl`.

Lista, pausa och ta bort: `kalla_lagg_till.py --lista`, `--pausa <id>`, `--aktivera <id>`, `--ta-bort <id>` (flyttas till `kallor_borttagna.json`, så inget försvinner). Använd namnen i samtalet, aldrig id:n.

## Första inventeringen (en gång, fylls på sedan)

1. **Läs profilen:** `profil/preferenser.json` (riktningar, orter, hårda gränser) och `profil/coach.json` om den finns. Saknas preferenser: be skillen `karriarcoach` ta fram dem först, eller fråga kort om yrke och ort.
2. **Taxonomi-id:** slå upp yrken, yrkesgrupper, kommuner och län:
   `taxonomi_sok.py yrke "kommunikatör"`, `taxonomi_sok.py yrkesgrupp "informatörer"`, `taxonomi_sok.py kommun Uppsala`, `taxonomi_sok.py region Uppsala`.
   Välj de träffar som stämmer, fråga henne bara vid verklig tvekan ("menar du kommunikatör eller marknadskommunikatör?"). Skriv in id:na i `preferenser.json` (`yrkes_id`, `kommun_id`, `region_id`).
3. **JobTech-källan och recept:** se till att `sok/kallor.json` har posten `af` (typ jobtech). Skapa ett recept per riktning i `sok/recept/<namn>.json`: `occupation-name` och/eller `occupation-group`, `municipality`/`region`, eventuellt `q` med de titlar arbetsgivare faktiskt använder, `remote` om distans är aktuellt, och `filter.min_poang` (börja på 50). Ett recept med en yrkesgrupp fångar mer än ett med fritext.
4. **Förval:** öppna `${CLAUDE_PLUGIN_ROOT}/templates/kallor-forval.json` och erbjud de som passar henne i en kort lista (t.ex. Varbi för universitet och regioner hon vill till, Jurek för ekonomi/HR/juridik, distanssajter bara vid distansönskemål, The Hub vid startupintresse, Cision-signaler för dolda marknaden). Hon väljer. Kopiera valda poster till `kallor.json` med `"aktiv": true`, `"tillagd_av": "jobbkallor"` och dagens datum. Remotive används inte automatiskt (robots.txt förbjuder API:t).
5. **Målbolag:** kör `malbolag.py --ar 3` (läser yrken och orter ur preferenserna) och visa de 10–15 arbetsgivare som annonserat flest liknande jobb, med antal per år i klartext. Fråga vilka hon vill följa och vilka egna favoriter hon har. Lägg till karriärsidan för varje valt bolag med `kalla_lagg_till.py <url> --namn <bolag>` (hitta URL:en med webbsök om hon inte har den). Varbi-bolag får sitt RSS-flöde automatiskt.
6. **LinkedIn och Indeed:** skrapas aldrig. Hjälp henne skapa jobbaviseringar på sajterna med samma filter som recepten. Finns Gmail-kopplingen läser skillen `jobbsok` aviseringsmejlen; annars klistrar hon in länkar. Registrera dem som typ `mejl`.
7. **Avsluta** med en sammanfattning i 3–5 rader: vad som bevakas, hur ofta och vad hon behöver göra själv (t.ex. skapa aviseringen på LinkedIn). Erbjud att köra sökningen direkt (skillen `jobbsok`).

## Dolda marknaden

- **Signaler:** med Cision aktiv sparas pressmeddelanden med ord som "förvärvar", "utser", "etablerar" i `sok/signaler.json`. Lyft de som rör hennes målbolag eller bransch, med en mening om varför det kan betyda rekrytering. MFN läses inte automatiskt (robots.txt förbjuder det).
- **Kontaktmejl och spontanansökan:** för ett målbolag utan annons föreslår du en kontaktväg (ansvarig chef eller rekryterare via bolagets sida, eller en gemensam kontakt) och skriver ett kort utkast byggt på hennes faktabank. **Skicka aldrig något.** Utkastet visas för henne; hon skickar själv, eller ber uttryckligen om ett mejlutkast.
- Säg "en betydande andel av jobben tillsätts utan annons", inte "70–80 %" (siffran är dåligt belagd).

## Nät saknas

Ger ett skript `NÄTFEL` (kod 3) är sandlådans nät begränsat. Gör då samma sak med webbverktygen: sök och läs sidorna själv, och lägg in hittade jobb med `ingest.py --kalla webb --hittad-via <recept>` (JSON på stdin, se skriptets hjälptext). Säg bara "jag letar på webben i stället den här gången".
