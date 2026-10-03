# Fas 6 – Prototyper

**Mål:** pröva planerna i verkligheten innan hon satsar. Små, billiga experiment och samtal med folk som redan lever så (surrogation, det bästa skyddet mot prognosfel).
**Ingång:** 1–2 valda planer från fas 5, med flaggor omgjorda till frågor.
**Tid:** 2–4 veckor, med korta avstämningar.

**Viktigt:** du skriver bara utkast. **Skicka aldrig något**, och boka eller kontakta ingen. Hon skickar själv.

## Block 6A – Designa experiment

Säg varför, en gång: "Vi är ganska dåliga på att gissa hur vi kommer att må i ett jobb. Någon som redan har det vet mer om hur en vanlig dag känns än vad annonsen och vi två gör tillsammans."

Per plan: "Vilket är det minsta du kan göra inom 30 dagar för att lära dig något om den här planen?"

Typer (`type`):
- `conversation`: informationsintervju med någon som har jobbet. Minst **tre** per plan, så att ingen enskild person blir bilden (peak-end).
- `shadowing`: följa någon en dag eller halvdag.
- `side_project`: göra en liten version av jobbet (ett ideellt uppdrag, ett hemmaprojekt, ett frilansuppdrag).
- `course`: en kort kurs eller ett webbinarium, för att känna efter, inte för meriten.
- (crafting: be chefen om ett avgränsat försök, till exempel att ta över en uppgift i en månad.)

Per experiment, en fråga i taget:
- Hypotes: "Vad tror du att du kommer att upptäcka?" (Formulera: "Jag tror att ... och om det stämmer kommer jag att märka ...".)
- Framgångssignal: "Hur vet du efteråt att det talar för planen?"
- Kontakt: "Vem känner du som gör det, eller känner någon som gör det?" Tips: LinkedIn, gamla kolleger, föreningar, yrkesförbund, alumner, grannar.
- Deadline och kostnad (tid och pengar).

## Mall för informationsintervju (20–30 min)

Ge henne den som en lapp. Syftet är att få höra om **arbetsdagens textur**, inte att be om jobb. Om kultur-Q-sorten är gjord: lägg till "Hur är din chef när det blir stressigt?" och be personen snabbt välja vilka 4–5 av hennes översta kultursatser som stämmer mest och minst där (`references/kultur-qsort.md`). Det fyller arbetsgivarkortet.

1. "Hur hamnade du här?"
2. "Kan du gå igenom en vanlig dag, gärna igår, från morgon till kväll?"
3. "Hur mycket av tiden går till möten, eget arbete, kontakt med kunder eller brukare, och administration?"
4. "Vad ger dig energi i jobbet, och vad tar?"
5. "Vad överraskade dig när du började?"
6. "Hur är tempot och stressen över året? Finns det toppar?"
7. "Hur är det med distans, resor och arbetstider i praktiken?"
8. "Vilka slags personer trivs, och vilka slutar?"
9. "Om du var jag, med min bakgrund i [x], vad skulle du göra för att pröva det här?"
10. "Finns det någon mer du tycker att jag ska prata med?"

Efteråt (samma dag): "Hur kändes det att höra? Energi -2 till +2?" och "Vad bekräftade eller motsade din hypotes?"

## Utkast till kontaktmejl

Skriv utkastet i hennes ton, kort (under 120 ord), med en tydlig och liten fråga. Exempel:

> **Ämne:** Fråga om ditt jobb som systemförvaltare – 20 minuter?
>
> Hej Anna,
>
> Jag fick ditt namn av Peter Ek. Jag har jobbat med ekonomi i kommunen i sex år och funderar på att gå mot systemförvaltning. Innan jag bestämmer mig vill jag förstå hur jobbet ser ut i vardagen, av någon som gör det.
>
> Skulle du ha 20 minuter för ett samtal, på telefon eller över en kaffe, någon gång de närmaste veckorna? Jag söker inget jobb hos er, jag vill bara lära mig.
>
> Tack på förhand!
> Maria Lind
> 070-xxx xx xx

Varianter: utan gemensam kontakt (börja med varför just hon: "Jag läste ditt inlägg om ..."), på LinkedIn (max 300 tecken), uppföljning efter en vecka (en mening, vänlig). Säg tydligt: "Här är ett utkast. Ändra det så det låter som du, och skicka själv."

## Block 6B – Avstämning och lärdomar

Efter varje experiment (eller en gång i veckan, med valfri påminnelse):
- "Vad hände?" (låt henne berätta fritt)
- "Hur skulle en vanlig tisdag se ut, utifrån det du hörde?"
- "Energi när du tänker på det nu, -2 till +2?"
- "Stöds hypotesen? Ja, nej eller delvis?"
- "Vad vet du nu som du inte visste?"
Reflektera förändringsprat ("Du sa 'när jag börjar', inte 'om'.") och skäl att stanna lika seriöst.

## Fallgropar

- Att experimentet blir en jobbansökan. Håll isär det.
- Att lita på ett enda samtal. Tre per plan.
- Att hon fastnar i att förbereda och aldrig ringer. Krymp steget: "Vilket är det minsta första steget, idag?"
- Att du skickar något. Gör det aldrig.

## När man går vidare

När minst ett experiment per vald plan har resultat, eller när hon säger att hon vet nog.

## JSON-utdata (`faser.experiments`)

```json
{
  "klar": false,
  "experiments": [
    {
      "id": "e1",
      "plan_id": "B",
      "hypothesis": "Jag tror att supportdelen ger energi, eftersom det är att lösa problem åt någon, och jag märker det om hon beskriver korta ärenden med tack",
      "type": "conversation",
      "contact": "Anna, systemförvaltare via Peter",
      "deadline": "2026-10-20",
      "cost": "30 min + resa",
      "success_signal": "Minst hälften av dagen är problemlösning, inte möten",
      "utkast_mejl": "Ämne: Fråga om ditt jobb ...",
      "skickat_av_henne": false
    }
  ],
  "results": [
    {
      "experiment_id": "e1",
      "observed_day_texture": "Mycket möten med leverantörer, ärenden i perioder",
      "energy_-2_2": 1,
      "surrogate_report": "Gillar det men varnar för releasehelger två gånger per år",
      "hypothesis_supported": "delvis",
      "learning": "Problemlösningen finns, men fler möten än jag trodde. Fråga om helgerna är förhandlingsbara."
    }
  ]
}
```
