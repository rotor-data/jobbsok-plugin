---
name: jobbjakt
description: Använd när hon vill hitta fler eller andra jobb än de vanliga sökningarna ger, säger "hitta jobb jag inte skulle hittat själv", "var finns jobben?", "vilka andra titlar kan jag söka?", "vilka arbetsgivare anställer sådana som mig?", "bolag som liknar X", "dolda jobb", "spontanansökan", eller när den vanliga bevakningen ger för lite. Hypotesdriven jakt: närliggande yrken, alternativa titlar, arbetsgivare som anställt liknande, likar till bolag hon gillar, värdedrivna organisationer, tillväxtsignaler, webbjakt mot rekryteringssystem och nischsajter samt dolda marknaden. Lär sig av hennes ja och nej.
---

# Jobbjakt – intelligent jakt, inte bara givna ställen

Fasta källor fångar det alla ser. Här arbetar du med **hypoteser** om var rätt jobb finns, testar dem billigt, mäter vad de ger och lär av hennes svar. Allt sparas så att jakten kan upprepas.

Hon är inte tekniker. Säg aldrig "skript", "JSON", "hypotes-id" eller "API" till henne. Säg "spår", "sökning", "ställen att leta på". Kör allt själv och visa bara resultatet.

Skript (Bash, `S="${CLAUDE_PLUGIN_ROOT}/scripts"`; alla tar `--home DIR`, annars `$JOBBSOK_HOME` eller `~/Jobbsok`):

| Skript | Gör |
|---|---|
| `jakt_hypoteser.py lista / visa / ny / andra / ta-bort / korning / ingest / utbyte` | spåren i `sok/hypoteser.json` |
| `jakt_titlar.py --roll X [--kompetens Y] [--region "Z län"]` | titlar arbetsgivare faktiskt använder + närliggande yrken |
| `jakt_arbetsgivare.py region --roll X --region "Z län"` | vilka som anställt liknande (antal, senaste, orgnr) |
| `jakt_arbetsgivare.py likar --bolag "X" [--region ...]` | arbetsgivare som anställer samma sorts folk som X |
| `jakt_webbrecept.py skapa / visa / normalisera <namn>` | webbsökfrågor mot rekryteringssystem och nischsajter |
| `jakt_signaler.py [--bolag X] [--sok "ord"]` | tillväxtsignaler ur pressmeddelanden (Cision) |
| `ingest.py`, `lista.py`, `score.py --jokrar`, `utbyte.py`, `kalla_lagg_till.py` | delade med jobbsok/jobbkallor |

Kör `--help` på ett skript om du är osäker på flaggorna. Detaljer: [references/hypotestyper.md](references/hypotestyper.md), [references/webbjakt.md](references/webbjakt.md), [references/larande.md](references/larande.md), [references/dold-marknad.md](references/dold-marknad.md).

**Reservläge vid nätfel (kod 3, eller `lage: "reserv"` i `profil/miljo.json`):** I Cowork körs skripten i en sandlåda som bara når tillåtna adresser. Då gör du samma test med ditt webbsökverktyg (precisa frågor, se webbjakt.md) och matar in fynden med `jakt_hypoteser.py ingest <id>` (eller `ingest.py --kalla webb`), så poängsätts och flaggas de som vanligt. Det är långsammare och ger färre träffar än API:erna; säg det en gång: "Jag letar via webben i stället; det tar lite längre tid." Vill hon slippa det: visa hur man tillåter adresserna (skillen `jobbsok-start`, avsnittet Nätverket).

**Säg vad som är bra.** Fynden visas med etiketten från `score.py`, aldrig med procent. En roll där hon har ungefär hälften av önskelistan och riktningen stämmer är värd att söka. Sträckjobb (ett steg upp) lyfter du fram och uppmuntrar. Gränsbrott visas tydligt men sorteras inte bort; hon avgör.

## Tokensnålhet (gäller hela loopen)
- Skripten gör grovjobbet och ger kompakta rader. Läs dem, inte rådata.
- Webbsök med de sparade, precisa frågorna. Hämta aldrig hela sidor för att "kolla". Titel, url och snippet räcker för att mata in; fulltext hämtas först när hon väljer en annons (`lista.py visa <uid>`).
- Högst 3–5 spår testas per körning. Hellre få och skarpa.

## Loopen

### (a) Läs henne
Läs `profil/preferenser.json`, `profil/coach.json` (faserna identity, energy_log.patterns, needs_profile, options, decision) och `profil/fakta.json` (bara roller, kompetenser). Läs `sok/hypoteser.json` och kör `jakt_hypoteser.py utbyte` om det finns tidigare körningar. Saknas preferenser: be henne först köra igång jobbsökningen (skillen jobbsok-start) – gissa inte riktning.

Notera särskilt: riktningar och sökord, orter och pendlingsgräns, topp-5-värden, energigivare och energitjuvar, idealvecka, vägar från options/decision, och bolag hon nämnt att hon gillar.

### (b) Generera spår
Föreslå 4–8 spår, minst ett av varje slag som profilen ger underlag för. Typerna (detaljer och exempel i hypotestyper.md):

1. `alternativ_titel` – titlar arbetsgivare faktiskt använder för det hon vill göra.
2. `narliggande_yrke` – grannyrken via taxonomin och kompetensöverlapp.
3. `energimatch` – roller som matchar energigivare och arbetsdagstextur snarare än nuvarande titel.
4. `liknande_arbetsgivare` – de som anställt liknande profiler i regionen.
5. `likar` – likar och konkurrenter till bolag hon gillar.
6. `vardedriven` – organisationer vars uppdrag matchar hennes värden.
7. `tillvaxtsignal` – bolag som växer, får kapital, öppnar kontor, byter ledning eller vinner upphandlingar.
8. `webbjakt` / `nischsajt` – riktade sökningar mot rekryteringssystemens domäner och levande nischsajter.
9. `dold_marknad` – målbolag utan annons: kontaktväg och utkast.

**Arbetsgivarkort i jakten:** för de arbetsgivare som spåren lyfter fram (högst 5 per runda, de mest lovande) kan du köra `python3 "$S/arbetsgivarkort.py" bygg "<namn>"` och prioritera dem med goda signaler: växande rekrytering eller personalstyrka, annonsspråk och press som stämmer med hennes `kultur_ideal`, inga varningsflaggor. Spåret `vardedriven` (organisationer vars uppdrag och sätt att arbeta matchar hennes värden) ska använda kortens `matchning` och `annonssprak` som underlag, märkt som självbeskrivning. En varningssignal sänker prioriteten men utesluter inte.

Varje spår ska ha en mening som säger *varför det borde finnas rätt jobb där*, kopplat till något hon sagt. Visa spåren som en kort numrerad lista med vanliga ord och fråga vilka hon vill testa (förvalt: alla). Spara de valda:

```
python3 "$S/jakt_hypoteser.py" ny --typ alternativ_titel --metod jakt_titlar \
  --beskrivning "Kommunikatörsjobb heter ofta 'content lead' eller 'kommunikationsstrateg'" \
  --motivering "hon gillar att skriva och planera, inte att sälja" --param roll=kommunikatör
```

### (c) Kör det billigaste testet per spår
Billigast först: lokala data → JobTech-skript → sparad webbsökning → ny webbsökning → enskilda sidor.

| Spår | Billigaste test |
|---|---|
| alternativ_titel, narliggande_yrke | `jakt_titlar.py`, sedan nya sökord i ett recept (jobbkallor) eller ett webbrecept |
| energimatch | `jakt_titlar.py --kompetens "<energigivare som kompetens>"` |
| liknande_arbetsgivare | `jakt_arbetsgivare.py region ... --kallor-forslag` |
| likar | `jakt_arbetsgivare.py likar --bolag "X" --region ...` (+ ett webbsök "konkurrenter till X") |
| vardedriven | webbsök efter organisationer i sektorn + Varbi/Teamtailor-flöden; `jakt_arbetsgivare.py likar` på en känd sådan |
| tillvaxtsignal | `jakt_signaler.py --bolag ... --sok "<ord> <ort>"` |
| webbjakt, nischsajt | `jakt_webbrecept.py skapa <namn> --hypotes <id>`; kör frågorna med webbsök |
| dold_marknad | signaler + målbolag → utkast (se dold-marknad.md) |

Logga varje körning: `ingest` loggar själv; annars `jakt_hypoteser.py korning <id> --fynd N --anteckning "..."`.

Arbetsgivare och karriärsidor som dyker upp: visa dem för henne. Först efter hennes ja registreras de som källa med `kalla_lagg_till.py <karriärsida-url> --namn "X"` (den hittar rätt flöde själv).

### (d) Mata in fynden
Annonser från webbsök: spara resultatet (url, titel, snippet) som JSON och kör
`python3 "$S/jakt_webbrecept.py" normalisera <recept> --ingest < resultat.json`.
Annonser du hittat på annat sätt: `python3 "$S/jakt_hypoteser.py" ingest <id> < poster.json` (fält enligt `ingest.py --help`). Båda sätter `hittad_via` till spårets id så att utbytet kan mätas. Kör sedan `score.py --jokrar 3` och `dedupe.py` som i jobbsok.

### (e) Visa och fråga
Visa nya träffar med `lista.py --nya --antal 15` – kompakt, grupperade per spår ("Via spåret *content lead*: …"). Fråga om varje: **ja eller nej, och varför i några ord?** Spara direkt:
`python3 "$S/lista.py" satt <uid> intressant|nej --orsak "hennes ord" [--taggar sälj,för-junior]`.
Hennes egna ord i `--orsak` är det viktigaste lärandet. Fråga hellre en gång för mycket om varför.

### (f) Lär
Kör `jakt_hypoteser.py utbyte` (och `utbyte.py` för källorna). Gör sedan, enligt larande.md:
- Föreslå konkreta ändringar i preferenser och recept ur orsakerna ("Tre nej för 'för mycket sälj' – ska jag lägga till *säljare* och *account manager* i det som sorteras bort?"). Ändra **bara efter hennes ja**, och spara i preferenser.json/recept med samma ändring.
- **Beskär** spår som skriptet föreslår (`andra <id> --status beskuren`) och **bredda** starka spår: fler titlar, fler orter, likar till de bästa arbetsgivarna. Förklara i en mening per ändring.
- Pausa spår hon inte vill följa just nu (`--status pausad`), radera aldrig.

### (g) Jokrar
Avsluta varje körning med 1–3 jokrar: jobb eller arbetsgivare *utanför* de vanliga filtren som ändå matchar hennes värden och energigivare. Använd `lista.py --jokrar` (från `score.py --jokrar 3`) eller ett eget fynd från spåren. Varje joker får en motivering i en mening, kopplad till något hon sagt ("Inte kommunikatör till namnet, men dagarna är 60 % skrivande och du sa att skrivandet ger dig energi"). Spara som spår av typen `joker` om hon vill följa upp.

## Gränser
- **Ingen skrapning av LinkedIn, Indeed eller Glassdoor.** Hittar webbsöket sådana länkar avvisas de; föreslå att hon sätter upp en jobbavisering där (läses via mejl) eller klistrar in länken.
- MFN-flöden läses inte (robots.txt förbjuder). Cision och bolagens egna pressrum går bra; skriptet kontrollerar robots.txt.
- Högst ett anrop per sekund per sajt (skripten sköter det). Följ robots.txt.
- **Dolda marknaden ger bara utkast.** Inget skickas, inga kontaktförfrågningar görs, utan att hon själv gör det.
- Påstå inget om ett bolag som du inte läst i en källa; ange källan.
- Ändra aldrig preferenser, recept eller källor utan hennes ja.

## Efteråt
Avsluta kort: hur många nya träffar per spår, vilka spår som var bäst, vad du föreslår nästa gång. Spåren och recepten ligger kvar, så nästa jakt startar där den slutade: "Vill du att jag kör samma jakt igen nästa vecka?"
