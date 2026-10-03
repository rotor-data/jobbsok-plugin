# fakta.json – format och exempel

Schema: `${CLAUDE_PLUGIN_ROOT}/schemas/fakta.schema.json`. Kontrakt: `${CLAUDE_PLUGIN_ROOT}/references/datakontrakt.md`.

**Txt** = `{"sv": "...", "en": "..."}`, båda valfria. Används för titel, beskrivning, meritens text/kort, program, kursnamn, kompetensnamn, sammanfattning.

```json
{
  "schema_version": 1,
  "person": {"namn": "", "titel": {"sv": ""}, "ort": "", "epost": "", "telefon": "",
             "lankar": [{"etikett": "LinkedIn", "url": ""}], "foto": null, "korkort": "B"},
  "sammanfattning_rad": {"sv": ""},
  "roller": [{
    "id": "r1", "arbetsgivare": "", "titel": {"sv": ""}, "ort": "", "start": "2021-03", "slut": null,
    "beskrivning": {"sv": ""},
    "meriter": [{
      "id": "r1-m1",
      "text": {"sv": "Verb + vad + resultat."},
      "kort": {"sv": "valfri kortversion"},
      "siffror": [{"varde": "30 %", "betydelse": "färre supportärenden", "kalla": "dokumenterat"}],
      "belagg": "verifierat",
      "taggar": ["taxonomi-id eller fri tagg"],
      "omfattning": "team 6 pers"
    }]
  }],
  "utbildning": [{"id": "u1", "skola": "", "program": {"sv": ""}, "start": "2011", "slut": "2014"}],
  "kurser": [{"id": "k1", "namn": {"sv": ""}, "utfardare": "", "ar": "2022"}],
  "sprak": [{"sprak": "Svenska", "niva": "modersmål"}],
  "kompetenser": [{"id": "c1", "namn": {"sv": ""}, "taxonomi_id": null, "niva": "van", "taggar": []}],
  "ideella": [],
  "referenser": [{"namn": "", "roll": "", "kontakt": "", "relation": ""}],
  "aldrig_pastaa": []
}
```

Regler som validatorn kontrollerar:
- Obligatoriskt: `schema_version` (= 1), `person.namn` (får vara tom text i början), `roller`.
- Roll: `id` som `r<n>`, `arbetsgivare`, `titel`, `start` (`YYYY-MM`), `meriter`. `slut` är `YYYY-MM` eller `null` (pågår).
- Merit: `id` som `<roll-id>-m<n>`, unikt i hela filen; `text`; `belagg` = `verifierat|egen_uppgift`.
- Siffra: `varde` och `kalla` = `egen_uppgift|dokumenterat`.
- Språknivå: `modersmål|flytande|god|grundläggande`. Kompetensnivå: `expert|van|grund`.
- År (utbildning, kurser, ideellt): `YYYY`.
- Okända fält avvisas (fånga stavfel). Personnummer m.m. har inget fält och ska inte läggas till.

Id-regler: nya roller får nästa lediga `r<n>`; ordningen i listan kan vara kronologisk oberoende av id. Byt aldrig id på något som finns.
