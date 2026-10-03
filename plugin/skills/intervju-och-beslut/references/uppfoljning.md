# Steg 4 – Uppföljning efter 3 och 6 månader

Syftet är dubbelt: att hon ser om valet blev som hon trodde, och att metoden kan utvärderas (n=1, en uppföljning och inte evidens; se `docs/research/kultur-ledarskap-evidens.md` avsnitt 5, "Mät själva").

## Påminnelse

När hon tackat ja (steg 3): erbjud en gång två påminnelser, 3 och 6 månader efter startdatum, med Coworks schemalagda uppgifter. Skapa dem bara om hon säger ja. Texten: "Det har gått <3|6> månader i nya jobbet. Vill du göra den korta uppföljningen (10 minuter)? Säg 'uppföljning nya jobbet'." Säg vad som schemalagts och hur hon stänger av det. Spara `beslut.json` → `uppfoljning_paminnelser` med datumen.

## Samtalet (kort, ca 10 minuter)

1. Öppet: "Hur är det?" Reflektera.
2. Trivsel 0–10.
3. **Kultur-Q-sorten för det faktiska jobbet**, samma 18 satser och metod (`skills/karriarcoach/references/kultur-qsort.md`): fyra mest, fyra minst.
4. Chefsfrågan: "Min chef ger mig utrymme och backar mig", 0–10.
5. "Skulle du välja samma igen?" (ja, nej, vet inte, med hennes ord).
6. Hårda gränser i praktiken: hur lång är pendlingen egentligen, hur många resdagar blev det?

## Jämför med prognosen

Ur `beslut.json` → `prognos`: förväntad trivsel, förväntad Q-sort och chefsutrymme. Visa skillnaderna sakligt:
- glappet ideal mot faktiskt jobb (antal satser i hennes topp som hamnade i toppen nu), jämfört med glappet ideal mot förra jobbet (`kultur_profil.senaste_jobb`),
- prognos mot utfall för trivsel och chef.

Blev det sämre: utforska utan att döma valet ("Vad är det som skaver?"). Erbjud job crafting (coachens fas 5) innan nytt byte. Tecken på utmattning: coachens regel.

## Spara

`profil/coach.json` → `uppfoljning.nytt_jobb[]` enligt coachens schema (format i `docs/research/kultur-ledarskap-evidens.md` avsnitt 7):

```json
{"manad": 3, "datum": "YYYY-MM-DD", "arbetsgivare": "", "mapp": "ansokningar/<mapp>",
 "trivsel_0_10": 0, "kultur_qsort": {"instrument": "kultur-qsort-18-v1", "topp": [], "botten": []},
 "chef_utrymme_0_10": 0, "valja_igen": true,
 "pendling_faktisk_min": null, "resdagar_faktisk_manad": null,
 "jamfort_med_prognos": {"trivsel_diff": 0, "chef_diff": 0, "ideal_topp_traff_nu": 0, "ideal_topp_traff_forra": 0},
 "hennes_ord": ""}
```

Läs filen, lägg till posten (skriv aldrig över tidigare), validera `coach.json`. Rör inget annat i coach.json.
