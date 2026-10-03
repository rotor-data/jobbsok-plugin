# Personligt brev och följemejl

## Brevet

250–400 ord, 3–5 stycken, en sida. Under 250 ord blir brevet ett följebrev som inte säger något CV:t inte redan visar; räkna orden innan du kör kontrollerna. Skrivs på ansökans språk, i den ton hon valt (SKILL.md, steg 5).

**Byggs på `analys.json`:**
1. **Öppning (2–3 meningar):** första meningen nämner något konkret ur annonsen eller verksamheten (en arbetsuppgift, en målgrupp, ett uppdrag, en förändring de beskriver) med annonsens egna ord. Senast andra meningen kopplar det till något hon har gjort, med en merit ur faktabanken. Öppningen har alltså en källa i `kalla_per_stycke`.
   Börja aldrig med: "Jag söker (härmed) tjänsten som …", "När jag läste er annons …", en tidsingress, en allmän sanning ("Ett bra intranät är …") eller en känsla ("kände jag igen mig direkt", "ett av de roligaste …", "blev jag glad"). Testet: går meningen att klistra in i ett brev till en annan arbetsgivare utan ändring är den för allmän.
2. **Starkaste matchningen:** det `ska`-krav hon möter bäst. Säg kravet med annonsens ord, visa sedan meriten och dess resultat (siffra från `siffror` eller omfattning). Avsluta stycket med vad det betyder för just den här rollen, i en mening, utan att gissa om framtida resultat.
3. **Andra matchningen:** ytterligare ett `ska`-krav på samma sätt. Ber annonsen uttryckligen att ansökan ska visa hur hon motsvarar kravprofilen: gå igenom de 3–4 viktigaste `ska`-kraven i ordning, ett eller två per stycke, med annonsens formulering som ankare.
4. **Lucka – bara om ett hårt krav saknas (`kravtyp: "hart"` och `lucka: true`):** en eller två meningar. Nämn den närmaste belagda erfarenheten och hur den liknar kravet (eller när hon får legitimationen/behörigheten, om det är på väg). Säg aldrig att luckan inte finns.
   **Annonser är önskelistor.** Luckor i önskelistan (`kravtyp: "onskat"`, även `ska`-krav som "minst fem års erfarenhet") nämns inte alls, eller högst i en saklig mening som visar den närmaste erfarenheten ("På Region X skrev jag …"). Aldrig med ursäkt, förbehåll eller tomma löften: inte "även om jag saknar …", "jag har tyvärr inte …", "jag har inte arbetat med X men …", "jag lär mig gärna", "jag är medveten om att …". Rekryteraren läser det hon har; lyft det.
5. **Avslut (1–2 meningar):** något konkret hon vill prata om på en intervju, kopplat till rollen eller en fråga ur `fragor_till_arbetsgivaren`. Inte "berätta mer om mig själv", inte "Tack för att du läser".

**Spegla annonsens ord:**
- Välj 3–5 av `analys.json → nyckelord` som är sanna för henne och använd dem ordagrant (samma substantiv, samma böjning går att ändra) i brevet. Minst två av dem ska också stå i CV:ts profiltext. ATS och rekryterare letter efter annonsens ord, inte synonymer.
- Kopiera aldrig hela meningar ur annonsen, och spegla inget ord som inte är sant (ett nyckelord ur en lucka hör inte hemma i en mening om vad hon kan).

**Påståenden som måste kunna beläggas:**
- Antal år räknas fram ur `roller` (start/slut) och skrivs så att det går att kontrollera: "sedan 2014", "i fem år på Region X". Avrunda aldrig uppåt ("tio års erfarenhet" när det är tolv är också fel; skriv det exakta eller ange startåret).
- Personliga egenskaper ("strukturerad", "håller tidsplanen", "lyhörd") får bara stå om en merit visar dem, och då hellre som meriten än som adjektivet.
- Erfarenhet som bara antyds i faktabanken (ett verktyg, en plattform, en målgrupp) skrivs inte. Fråga henne och lägg in det i fakta.json först.

**Regler:**
- Varje stycke får en rad i `kalla_per_stycke` med de merit-id det bygger på. Bara avslutet utan sakpåståenden får `[]`.
- Upprepa inte CV:t rad för rad. Brevet säger varför, CV:t visar vad. Samma siffra får stå i båda, men brevet lägger till sammanhanget (vad problemet var, vad hon gjorde).
- Högst en antites i hela brevet. Inget metaprat. Inga utropstecken.
- Högst en tredjedel av meningarna börjar med "Jag".
- Brevhuvud och underskrift (namn, kontaktuppgifter) hämtas av `render.py` från `cv.json` i samma mapp; skriv dem inte i `stycken`.
- `mottagare`: kontaktperson från annonsen om den finns (rekryterande chef före kontaktperson för frågor), annars bara bolaget. `datum`: dagens datum. `halsning`: "Vänliga hälsningar" / "Kind regards"; namnet skrivs ut från `person`.
- `ton.personas`: det hon valde, med namn och vikt.

## Följemejlet (`mejl.md`)

Läs först i `annons.md` hur ansökan tas emot (`Ansökan via:` och annonsens sista stycken). Mejlet anpassas efter det:

- **Ansökan via mejl:** mejlet är ansökans följebrev. 3–4 meningar: vilken tjänst (med annonsens titel och eventuellt referensnummer), att CV och brev ligger bifogade, det enda starkaste skälet att läsa vidare, hur hon nås.
- **Ansökan via formulär eller jobbsida (det vanliga):** skriv inget "här kommer min ansökan". Finns en kontaktperson för frågor: skriv i stället ett kort mejl med **en riktig fråga** om tjänsten (ur `fragor_till_arbetsgivaren`), som hon kan skicka innan hon söker eller som uppföljning. Ingen bifogad fil. Säg till henne att ansökan själv görs i formuläret.
- **Ingen kontaktperson och inget mejl:** skriv inget mejl; säg det kort till henne.

Ton: som ett mejl till en kollega hon inte träffat. Hälsa med förnamn ("Hej Anna,"). Inga fraser som "Jag hoppas att allt är bra", "Tveka inte att höra av dig", "Ser fram emot att höra från dig". Telefonnummer står en gång, i signaturen. Ämnesraden säger vad mejlet gäller ("Fråga om tjänsten som …" eller "Ansökan: …").

```markdown
Ämne: <Ansökan: roll – namn | Fråga om tjänsten som roll>

Hej <förnamn, eller "Hej!">,

<2–4 meningar enligt fallet ovan.>

Vänliga hälsningar
<namn>
<telefon>
```

- Mejlet går genom `antiai.py` som allt annat.
- Du skickar aldrig mejlet. Hon kopierar texten och bifogar PDF:erna själv.

## Uppföljning

När `foljupp_datum` passerats utan svar: erbjud ett kort uppföljningsmejl i samma ton (2–3 meningar: frågar vänligt om processen, upprepar intresset med ett konkret skäl, inget tjat). Kör det genom `antiai.py`.
