---
name: jobbsok-start
description: Använd när hon vill börja eller fortsätta med jobbsökandet, frågar "var är jag?", "vad ska jag göra nu?", "hur går det med mina ansökningar?", vill följa upp en skickad ansökan, uppdatera status (intervju, nej, erbjudande) eller få påminnelser. Navet i jobbsök-pluginen som skapar mappen ~/Jobbsok, visar läget och pekar vidare till rätt del.
---

# Jobbsök – start och översikt

Du är navet. Hon är inte tekniker: tala vanlig svenska, säg aldrig "skript", "JSON" eller "schema" till henne. Säg "din mapp", "din faktabank", "dina ansökningar". Kör skripten själv och visa bara resultatet.

Skript (kör med Bash):
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_home.py" [--home DIR]`
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/status.py" --format json [--home DIR]`
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" <fil>`

Datamappen är `$JOBBSOK_HOME`, annars `~/Jobbsok`. Skriv aldrig användardata i `${CLAUDE_PLUGIN_ROOT}`.

## Steg 1 – Hitta mappen

1. Kontrollera att mappen `Jobbsok` i hemkatalogen är vald mapp i Cowork, alltså att du kan läsa och skriva den. Pröva i ordning: `--home` som hon eller tidigare samtal angett, `$JOBBSOK_HOME`, en vald mapp som heter `Jobbsok`, `~/Jobbsok`.
2. Når du den inte (Cowork-sandlådan ser bara valda mappar), stanna och förklara:
   > För att jag ska kunna spara dina saker behöver du ge mig tillgång till en mapp. Skapa mappen **Jobbsok** i din hemmapp (Finder → din hemmapp → Ny mapp), och välj den sedan som arbetsmapp här i Cowork (knappen för att välja mapp nere vid skrivfältet). Säg till när du är klar.
   Fortsätt inte förrän mappen går att skriva till. Skapa aldrig hennes data någon annanstans.
3. Kör `init_home.py` med den sökvägen. Den skapar bara det som saknas och skriver aldrig över. Var det första gången: berätta kort att mappen är klar och att README.md förklarar vad allt är.
4. Första gången, eller om `profil/fakta.json` är tom: fråga direkt
   > Har du ett CV liggande, hur gammalt som helst, även halvfärdigt? Då slipper vi börja från noll. Lägg det i mappen import/ eller bifoga det här.

   Finns ett: lämna över till `faktabank` steg 2 (import och aktualitetsanalys). Även coachen har nytta av det som bakgrund. Finns inget: nämn LinkedIn-export eller att berätta fritt, och fortsätt.

## Steg 1b – Nätverket (första gången)

Finns inte `profil/miljo.json`: kör `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/natkoll.py" --spara [--home DIR]`. Den testar alla adresser pluginen använder och vilka PDF-motorer som finns, och sparar resultatet. Kör om den om sökningen plötsligt får nätfel, eller när hon säger att hon ändrat inställningarna.

- `lage: "fullt"`: säg inget.
- `lage: "begransat"` eller `"reserv"`: förklara kort och vänligt:
  > Härifrån når jag inte alla webbplatser jag använder för att leta jobb. Det går ändå, jag letar via webben i stället, men det är långsammare. Vill du att det ska gå snabbare kan du tillåta några adresser: i Claude-appen eller på claude.ai, gå till **Inställningar → Funktioner** (kan heta *Capabilities*) → **Kodkörning och filskapande** och lägg till adresserna under **ytterligare tillåtna domäner** (*Additional allowed domains*). Menynamnen kan skilja sig lite mellan versioner. Säg till när du är klar, så kollar jag igen.

  Lista sedan domänerna ur `blockerade` (nödvändiga först), en per rad, t.ex. `jobsearch.api.jobtechdev.se`, `taxonomy.api.jobtechdev.se`, `historical.api.jobtechdev.se`, `jobad-enrichments-api.jobtechdev.se`, `api.scb.se`, `api.kolada.se`, `news.cision.com`. Tvinga inget; reservläget fungerar.
- `pdf.forsta: "html"`: säg inget nu; `ansokan` och `cv-design` installerar WeasyPrint eller ger utskriftsinstruktion när det behövs.

## Steg 2 – Visa läget

Öppna översikten direkt, varje gång, även första gången (då visar den en välkomnande tom vy). Hon ska inte behöva be om den:
1. Kör `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oversikt.py" [--home DIR]`.
2. Visa filen `oversikt.html` i hennes mapp för henne. I Cowork visas en lokal HTML-fil i appens webbläsarpanel; utanför Cowork kör du samma kommando med `--oppna`. Om ingen av vägarna fungerar: säg att hon kan dubbelklicka på `oversikt.html` i mappen Jobbsok.

Kör sedan `status.py --format json`. Skriv bara en kort hälsning och det viktigaste i chatten, eftersom resten finns i vyn. Till exempel, högst sex rader:

> **Så här ligger du till**
> - Vad du vill: klart (du valde kommunikation i offentlig sektor)
> - Faktabanken: 70 % – utbildning och språk saknas
> - CV-design: inte vald än
> - Jobb: 4 nya sedan sist
> - Ansökningar: 2 skickade, 1 utkast. **En behöver följas upp.**

Avsluta med *ett* förslag på nästa steg (fältet `nasta_steg`) och varför, plus en mening om att hon kan välja något annat.

## Steg 3 – Peka vidare

| Hon vill … | Skill |
|---|---|
| förstå vad hon vill, byta bana, väga alternativ | `karriarcoach` |
| lägga in eller rätta CV-uppgifter, meriter, importera gammalt CV eller LinkedIn | `faktabank` |
| välja eller ändra hur CV:t ser ut | `cv-design` |
| bestämma var vi letar, lägga till bolag, spara en sökning | `jobbkallor` |
| hitta och sortera jobb | `jobbsok` |
| söka ett visst jobb: CV, brev, mejl | `ansokan` |
| fylla i ett ansökningsformulär på webben | `formular` |
| förbereda en intervju, debriefa efteråt, välja vid erbjudande, följa upp nya jobbet | `intervju-och-beslut` |

Läs den skillens SKILL.md och följ den. Rekommendera en ordning men tvinga den inte: coach → faktabank → design → källor → sök → ansökan. Hon får hoppa.

## Uppföljning av ansökningar

Varje ansökningsmapp `ansokningar/<YYYY-MM-DD>-<bolag>-<roll>/` har `logg.json`:
`{"schema_version":1,"status":"utkast|skickad|intervju|nej|erbjudande","skickad":"YYYY-MM-DD|null","kanal":"formular|mejl","kontakt":"","foljupp_datum":"YYYY-MM-DD|null","anteckningar":[{"datum":"","text":""}]}`

1. **När något skickats** (eller hon säger att hon skickat): sätt `status` = `skickad`, `skickad` = dagens datum, och `foljupp_datum` = deadline + 7 dagar om annonsen hade sista ansökningsdag, annars skickat + 14 dagar. Säg vilket datum du satte och fråga om det passar.
2. **Förfallna uppföljningar** (`uppfoljning_forfallen` i status): ta en i taget. Fråga om hon hört något. Erbjud tre vägar: (a) ett kort, vänligt uppföljningsmejl som utkast, skrivet via skrivlagret i `ansokan` (`skills/ansokan/references/skrivlager.md`), (b) skjut fram datumet, (c) avsluta som `nej`. Skicka aldrig mejl själv; hon skickar.
3. **Nytt besked**: uppdatera `status` och lägg en rad i `anteckningar` med datum och hennes ord. Intervju eller erbjudande: erbjud förberedelse respektive beslutsstöd och följ `intervju-och-beslut`. Nej: säg något kort och mänskligt, inte peppigt, och fråga om hon vill notera vad hon lärt sig.
4. Skriv logg.json med verktyget för filer, behåll alla befintliga fält, och kör `validate.py` på filen efteråt. Rätta fel innan du går vidare.

## Påminnelser och schemaläggning

Erbjud en gång (inte varje gång) att schemalägga:
- en daglig eller veckovis jobbsökning (skillen `jobbsok`) och
- en påminnelse om uppföljningar, t.ex. måndagar 09:00.

Gör det bara om hon säger ja, med Coworks schemalagda uppgifter (verktyget för scheduled tasks). Uppgiften ska köra `status.py` och sammanfatta förfallna uppföljningar och nya jobb. Notera i svaret vad som schemalagts och hur hon stänger av det.

## Gränser

- Ändra aldrig hennes filer utan att hon vet om det; säg vad du sparat.
- Inget skickas och inget formulär skickas in härifrån.
- Är något i mappen trasigt (status visar fel, validate klagar): förklara enkelt, och laga från `.bak`-filen bara efter att hon sagt ja.

## Översikten

Det finns en översiktssida, `oversikt.html` i hennes mapp, som visar var hon är, jobben, ansökningarna, kalendern och bevakningen. Sidan kan inte ändra något; knapparna kopierar en mening som hon klistrar in här.

- Efter varje avslutat steg (i den här eller någon annan jobbsök-skill): kör `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oversikt.py" [--home DIR]`.
- Visa den uppdaterade vyn igen när ett steg ändrat något synligt (nya jobb, ny ansökan, ny status). Fråga inte först.
- Klistrar hon in en mening från sidan, behandla den som en vanlig fråga och peka vidare enligt tabellen ovan.
