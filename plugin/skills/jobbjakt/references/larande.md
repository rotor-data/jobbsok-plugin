# Lärande – från hennes ja och nej till bättre jakt

## Vad som sparas
- `lista.py satt <uid> <status> --orsak "..." --taggar a,b` → `bedomning_json` i jobb.sqlite. Orsaken med hennes ord, taggarna korta och återanvändbara (`sälj`, `för-junior`, `pendling`, `fel-bransch`, `rätt-uppdrag`, `skrivande`).
- `jakt_hypoteser.py utbyte` → `utbyte` per spår och `orsaker` (vanligaste nej- och ja-orsakerna per spår) samt `forslag`.
- `utbyte.py` → `sok/utbyte.json` per källa, recept och hittad_via.

## Regler för förslag (skriptet föreslår, du formulerar, hon bestämmer)
| Läge | Förslag |
|---|---|
| ≥2 körningar utan fynd | beskär eller byt metod (t.ex. från webbrecept till jakt_arbetsgivare) |
| ≥5 bedömda och <10 % intressanta | beskär |
| ≥3 bedömda och ≥30 % intressanta | bredda: fler titlar ur `jakt_titlar`, fler orter, `likar` till de bästa arbetsgivarna |
| Samma nej-orsak ≥3 gånger | föreslå ändring i preferenser.json (exkludera_ord, exkludera_arbetsgivare, hårda gränser) eller receptets filter |
| Samma ja-orsak ≥2 gånger | föreslå nytt spår som bygger på orsaken (t.ex. "rätt uppdrag" → vardedriven) |

## Så ändrar du (bara efter ja)
- **Exkludera ord:** preferenser.json → `riktningar[].exkludera_ord` och receptets `filter.exkludera_ord`.
- **Exkludera arbetsgivare:** `exkludera_arbetsgivare`.
- **Nya sökord/titlar:** `riktningar[].sokord`, receptets `jobtech.q`, och webbreceptet (`jakt_webbrecept.py skapa <samma namn> ...` skriver om frågorna och behåller körningshistoriken).
- **Nya yrken:** `riktningar[].yrkes_id` / receptets `occupation-name`.
- **Spårets status:** `jakt_hypoteser.py andra <id> --status beskuren|pausad|aktiv`.
- Validera efter ändring: `validate.py <fil>`.

Formulera varje förslag som en fråga med ett konkret svar: "Tre nej för 'för mycket sälj'. Ska jag sortera bort annonser med *säljare* och *account manager*? (ja/nej)". En ändring per fråga. Gör inget i tysthet.

## Varning för överanpassning
- Två nej är inget mönster. Vänta på tre.
- Beskär inte ett spår som bara körts en gång.
- Jokrar räknas inte mot utbytet för ett spår – de ska få vara utanför.
- Om allt blir nej: fråga om riktningen har ändrats, i stället för att skruva på filtren (pröva karriärcoachens syntes).
