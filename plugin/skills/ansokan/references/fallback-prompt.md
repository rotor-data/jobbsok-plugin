# Fallback: promptmall utan connector

Används när skrivconnectorn saknas eller slutar svara. Mallen är komplett: du kan köra den själv, eller ge den till henne att klistra in i en annan AI-tjänst. Oavsett vem som skriver körs svaret alltid genom `antiai.py` och `sparbarhet.py` (SKILL.md, steg 7).

Fyll i allt inom `{{ }}`. Ta bort det block som inte gäller (CV eller brev). Skriv prompten på ansökans språk om den ska kopieras till en annan tjänst; behåll JSON-nycklarna som de är.

Säg till henne om hon ska kopiera: "Klistra in hela texten nedan i tjänsten, och klistra sedan in svaret här så kontrollerar jag det."

---

## Mallen

```text
DIN ROLL
{{ROLL}}

UPPGIFT
Skriv {{VAD: "texterna till ett CV" | "ett personligt brev och ett kort följemejl"}} på {{SPRÅK: svenska | engelska}} till annonsen nedan, för {{NAMN}}.

ANNONSEN
<<<
{{annons.md, hela}}
>>>

VINKEL
{{analys.json → vinkel}}

FAKTA – DET ENDA DU FÅR BYGGA PÅ
Varje rad har ett id. Använd inget annat underlag. Allt här får användas, men aldrig motsägas eller förstärkas.
{{en rad per vald merit: "r1-m1 | Lagret AB, lagerledare 2021–nu | Minskade ledtiden med 30 % genom nytt plocksystem | siffror: 30 % (kortare ledtid) | omfattning: team 6 pers"}}
{{utbildning, kurser, kompetenser och språk på samma sätt, med id}}

GRÄNSER – FÅR ALDRIG STÅ I TEXTEN
- Inga siffror, titlar, ansvar, arbetsgivare, verktyg eller resultat som inte står under FAKTA.
- Inga löften om framtida resultat. Ingen ålder, inget civilstånd, inget personnummer.
{{varje rad i fakta.json → aldrig_pastaa}}
{{varje lucka i analys.json: "Påstå inte erfarenhet av X."}}
- Inga ursäkter för luckor: inte "även om jag saknar", "tyvärr", "jag har inte … men", "jag lär mig gärna", "jag är medveten om att". Annonser är önskelistor.
- Ord som inte får förekomma: {{rost.json → aldrig_ord, kommaseparerat}}

SKRIVREGLER
1. Konkret före abstrakt. Säg vad hon gjorde och vad det gav. Använd en siffra från FAKTA där den finns, annars omfattningen; aldrig ett stort adjektiv i stället för en siffra.
2. Aktiv form och "jag" i brevet. I CV:t börjar meritrader med verb i preteritum, utan "jag".
3. Annonsens egna ord får speglas där de är sanna: {{analys.json → nyckelord}}.
4. Inga mallfraser. Skriv aldrig sådant som skulle kunna stå i vilken ansökan som helst:
   - ingresser om tiden eller världen ("i dagens samhälle", "i en tid då", "in today's world"),
   - tomma avslutningar ("sammanfattningsvis", "avslutningsvis", "jag är övertygad om att", "ser fram emot möjligheten", "in conclusion", "I am confident"),
   - jobbansökningsklyschor ("brinner för", "passionerad", "gedigen erfarenhet", "resultatinriktad", "lagspelare", "passionate about", "proven track record", "team player"),
   - stora bilder och hype ("spelade en avgörande roll", "banade väg", "sömlös", "i världsklass", "mervärde", "pivotal role", "cutting-edge").
   Byt dem mot det hon faktiskt gjorde.
5. Modeord får inte klumpa ihop sig: högst ett per mening. Det gäller ord som språkmodeller överanvänder, till exempel säkerställa, möjliggöra, optimera, effektivisera, främja, navigera, heltäckande, proaktiv, dynamisk, skalbar, strategisk / delve, leverage, foster, streamline, robust, seamless, pivotal, enhance, empower, comprehensive.
6. Högst EN kontrastfigur i hela texten. Det gäller alla former där man först säger vad något inte är och sedan vad det är: "inte X, utan Y", "inte X, men Y", "inte bara X utan Y", "Det är inte X. Det är Y", "inte X – det är Y", "Vi gör inte X. Vi gör Y", "Mindre X, mer Y" och engelska motsvarigheter ("not X, but Y", "It's not about X, it's about Y", "We don't just X, we Y", "Less X, more Y"). Säg hellre poängen rakt. Vanlig berättelse är tillåten: "Bussen kom inte, men en kollega körde mig" har ett nytt subjekt och en ny handling, och "utan att" är ingen kontrast.
7. Inget metaprat: texten ska inte peka på sig själv ("det är värt att notera", "det viktiga är att", "det är där min styrka ligger", "vill jag understryka", "it's worth noting").
8. Verb före substantiv. Skriv "planerade och följde upp" i stället för "ansvarade för planering och uppföljning". Aldrig tre substantiverade verb (planering, samordning, tydlighet) i samma mening. Inga trippellistor av egenskaper ("strukturerad, driven och engagerad"); visa en egenskap med en merit i stället.
9. Garderingar: {{GARDERINGAR: inga alls för klarspråk | högst en per stycke annars}}. Med gardering menas "kan komma att", "skulle kunna", "möjligen", "eventuellt", "kanske", "det kan vara". "Jag kan leda" är förmåga och okej. Högst ett tungt bindeord (dessutom, vidare, därtill, därmed, moreover, furthermore) i hela texten.
10. Variera meningslängden: blanda korta och långa meningar. Inga ihåliga sammanfattningar, inga utropstecken, inga emojis.
11. Inga påståenden som FAKTA inte bär: antal år bara som startår eller exakt uträknat, inga egenskaper ("strukturerad", "håller tidsplanen") som ingen merit visar, inga verktyg eller kanaler som inte står under FAKTA.
12. Brevets första mening nämner något konkret ur ANNONSEN; senast andra meningen kopplar det till en merit under FAKTA. Ingen öppning som går att återanvända till en annan arbetsgivare, ingen känsla som öppning ("kände igen mig", "blev glad"), inget "Jag söker tjänsten som".
13. Brevet är 250–400 ord. Följ strukturen i brev-och-mejl.md: öppning, starkaste ska-kravet, andra ska-kravet, ev. saknat HÅRT krav med närmaste belagda erfarenhet, konkret avslut.
14. Luckor i önskelistan (kravtyp onskat): {{analys.json → luckor med kravtyp onskat, kommaseparerat}}. Nämn dem inte, eller högst i en saklig mening som visar närmaste erfarenhet. Bara saknade hårda krav bemöts: {{analys.json → luckor med kravtyp hart, eller "inga"}}.

GRANSKNING INNAN DU SVARAR
Läs texten en gång till och rätta: språkriktighet, anglicismer, luddighet, syftning (varje "det"/"detta" måste ha något tydligt att syfta på), kollokation och register, funktion per element (varje mening ska göra något), struktur och balans, AI-kadens, interna motsägelser, självbärighet (läsaren ska förstå utan förkunskap). Syftning, motsägelser och funktion per element får aldrig lämnas.

SVARSFORMAT
Svara ENDAST med JSON, utan förklaring före eller efter.
{{SVARSFORMAT}}
```

## Roller

**Klarspråk (CV, och brev om hon väljer den tonen):**
> Du är en klarspråksskribent. Du skriver så att vem som helst förstår första gången, utan att läsa om. Korta, raka meningar. Vardagliga ord före fackord. Ett påstående per mening. Du garderar dig aldrig: står något i fakta säger du det rakt; står det inte där säger du det inte alls.

**Vald ton (brev och mejl):** skriv rollen ur hennes val. Har hon sparat en tonblandning i `rost.json`, utgå från den. Annars beskriv tonen med hennes ord. Blandning skrivs som vikter:
> Du skriver med en blandning av två röster. 70 %: {{beskrivning A}}. 30 %: {{beskrivning B}}. Den första bär strukturen och tydligheten; den andra färgar ordval och öppning. Grunden är alltid klarspråk: korta meningar, inga garderingar utan skäl.

## Svarsformat

**CV** (sätt in i `cv.json`; `person`, `sektioner[].typ`, perioder och organisationer fyller du själv från fakta.json, inte modellen):
```json
{
  "profil": "2–4 meningar",
  "meriter": {"r1-m1": "en rad: verb + vad + resultat", "r1-m2": "..."},
  "kompetensgrupper": [{"etikett": "kort rubrik", "poster": ["c1", "c4"]}]
}
```
`meriter`: exakt de id som stod under FAKTA, inga andra. `poster` i kompetensgrupper är kompetens-id; du skriver in namnen från fakta.json.

**Brev och mejl** (sätt in i `brev.json` och `mejl.md`):
```json
{
  "rubrik": "kort rubrik",
  "stycken": ["stycke 1", "stycke 2", "stycke 3", "stycke 4"],
  "kalla_per_stycke": [["r1-m1"], ["r1-m2", "u1"], ["r2-m1"], []],
  "mejl": {"amne": "Ansökan: <roll> – <namn> | Fråga om tjänsten som <roll>", "text": "2–4 meningar, efter hur ansökan tas emot (brev-och-mejl.md)"}
}
```
Ett tomt `[]` i `kalla_per_stycke` får bara förekomma för ett stycke helt utan påståenden om henne (t.ex. avslutet). `sparbarhet.py` ger då en varning, som du godkänner bara om stycket verkligen saknar sakpåståenden.

## Efter svaret

1. Kontrollera att svaret är giltig JSON och bara innehåller id som fanns under FAKTA. Annars: be om ett nytt svar med felet angivet.
2. Bygg filerna och kör kontrollerna i SKILL.md, steg 7.
3. Träffar: skriv om de berörda raderna själv (eller skicka träffarna tillbaka till samma tjänst med "Skriv om bara dessa rader: …"), och kör kontrollerna igen.
