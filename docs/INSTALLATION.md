# Så kommer du igång med Jobbsök

Jobbsök är ett tillägg till Claude som hjälper dig att söka jobb: ett samtal om vad du vill, en samling av dina meriter, ett snyggt CV, bevakning av nya jobb och ansökningar som skrivs för varje tjänst. Allt sparas i en mapp på din dator.

Du behöver appen **Claude** (för Mac eller Windows) och läget **Cowork**. Det tar ungefär tio minuter.

## 1. Installera tillägget

**Enklast – från GitHub (du behöver inget GitHub-konto):**
1. Öppna Claude och välj **Cowork**.
2. Gå till tilläggen (plugins) och välj att lägga till en marknadsplats. Klistra in adressen `rotor-data/jobbsok-plugin` (eller `https://github.com/rotor-data/jobbsok-plugin`).
3. Installera **jobbsok** därifrån. Nya versioner hämtas sedan därifrån.

**Alternativ – med fil:**
1. Ladda ner `jobbsok-<version>.plugin` under **Releases** på GitHub-sidan, eller använd filen du fått.
2. Öppna Claude, välj **Cowork**, dra filen in i chattfönstret och släpp den.
3. Claude visar vad tillägget innehåller. Klicka på **Installera** (eller **Godkänn**).

Menynamnen kan skilja sig något mellan versioner av appen.

## 2. Välj mappen Jobbsok

Allt du gör sparas i en mapp som heter **Jobbsok** i din hemmapp.

1. Skapa mappen om den inte finns: öppna Finder, gå till din hemmapp (huset i sidofältet), högerklicka och välj **Ny mapp**. Döp den till `Jobbsok` (utan å och ö).
2. I Cowork: klicka på mappsymbolen vid chattrutan och välj mappen **Jobbsok**.

Välj samma mapp varje gång du arbetar med jobbsökandet.

## 3. Slå på Smyra

Smyra hjälper Claude att skriva brev och CV-texter med rätt ton.

1. Klicka på **Inställningar** och sedan **Kopplingar** (Connectors).
2. Leta upp **Smyra** och klicka på **Anslut**. Logga in om du blir ombedd.

Fungerar det inte går det ändå bra: Claude skriver då texterna själv.

## 4. Slå på Claude in Chrome

Behövs för att Claude ska kunna hjälpa dig fylla i ansökningsformulär på webben.

1. Installera tillägget **Claude in Chrome** från Chrome Web Store i webbläsaren Chrome.
2. Logga in i tillägget med samma konto som i Claude-appen.
3. I Claude-appen: kontrollera under **Kopplingar** att Chrome är påslaget.

Claude skickar aldrig en ansökan åt dig. Du trycker alltid själv på skicka.

## 5. Säg första meningen

Skriv i Cowork:

> **Hjälp mig komma igång med jobbsökandet**

Claude ställer upp mappen och frågar sedan vad du vill börja med. Du kan alltid fråga "var är jag?" eller "vad ska jag göra nu?".

## Om något inte fungerar

### Mappen
- **Claude hittar inte mina filer:** kontrollera att mappen Jobbsok är vald som arbetsmapp (steg 2). I Cowork ser Claude bara mappar du valt. Välj om den och säg "kolla igen".

### Nätet
Claude kör sina hjälpprogram i en avskild miljö som bara når webbadresser som är tillåtna. Första gången testar Claude vilka som går att nå och sparar svaret.
- **"Härifrån når jag inte alla webbplatser":** det fungerar ändå, Claude letar via sin egen webbsökning (reservläget), men det är långsammare och hittar färre jobb.
- **För att slippa reservläget:** öppna **Inställningar → Funktioner** (kan heta *Capabilities*) i Claude-appen eller på claude.ai, gå till **Kodkörning och filskapande** och lägg till adresserna under **ytterligare tillåtna domäner** (*Additional allowed domains*). Menynamnen kan skilja sig mellan versioner. Adresserna:
  - `jobsearch.api.jobtechdev.se`, `taxonomy.api.jobtechdev.se` (behövs för sökningen)
  - `historical.api.jobtechdev.se`, `jobad-enrichments-api.jobtechdev.se` (yrkeskort, bättre matchning)
  - `api.scb.se` (löner), `api.kolada.se`, `news.cision.com` (arbetsgivarkort)
  - `pypi.org`, `files.pythonhosted.org` (för att kunna installera PDF-verktyget)
  Säg sedan "kolla nätet igen" till Claude.

### PDF
- **Inga PDF:er blir gjorda:** utan Chrome försöker Claude installera PDF-verktyget WeasyPrint. Går inte heller det får du en webbsida (cv.html, brev.html). Öppna den i Chrome, Safari eller Edge, välj **Arkiv → Skriv ut → Spara som PDF**, A4, marginaler Standard, och slå av **Sidhuvud och sidfot**. Kontrollera att CV:t blev högst två sidor och brevet en.
