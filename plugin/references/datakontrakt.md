# Datakontrakt – gemensamt för alla skills och skript

Datarot: `$JOBBSOK_HOME`, med standardvärdet `~/Jobbsok`. Alla skript tar `--home` och läser annars miljövariabeln eller standardvärdet. Alla JSON-filer är UTF-8 och har `"schema_version": 1`. JSON Schema (draft 2020-12) ligger i `schemas/<namn>.schema.json` i pluginen. `scripts/validate.py <fil>` väljer schema efter filnamnet (och efter mappen för `recept/` och `webbrecept/`).

Språk: textfält som kan behövas på två språk är objekt `{"sv": "...", "en": "..."}`, där båda nycklarna är valfria. Det kallas nedan **Txt**.

## profil/fakta.json  (schema: fakta)
```json
{
  "schema_version": 1,
  "person": { "namn": "", "titel": Txt, "ort": "", "epost": "", "telefon": "", "lankar": [{"etikett":"LinkedIn","url":""}], "foto": "profil/foto.jpg|null", "korkort": "B|null" },
  "sammanfattning_rad": Txt,
  "roller": [{
    "id": "r1", "arbetsgivare": "", "titel": Txt, "ort": "", "start": "YYYY-MM", "slut": "YYYY-MM|null",
    "beskrivning": Txt,
    "meriter": [{
      "id": "r1-m1",
      "text": Txt,                         // en rad: verb + vad + resultat
      "kort": Txt,                         // valfri kortversion
      "siffror": [{"varde": "30 %", "betydelse": "kortare ledtid", "kalla": "egen_uppgift|dokumenterat"}],
      "belagg": "verifierat|egen_uppgift",
      "taggar": ["kompetens-id eller fri tagg"],
      "omfattning": "team 6 pers, budget 2 mkr"
    }]
  }],
  "utbildning": [{"id":"u1","skola":"","program":Txt,"start":"YYYY","slut":"YYYY|null","merit":Txt}],
  "kurser":     [{"id":"k1","namn":Txt,"utfardare":"","ar":"YYYY"}],
  "sprak":      [{"sprak":"Svenska","niva":"modersmål|flytande|god|grundläggande"}],
  "kompetenser":[{"id":"c1","namn":Txt,"taxonomi_id":"string|null","niva":"expert|van|grund","taggar":[]}],
  "ideella":    [{"id":"i1","organisation":"","roll":Txt,"start":"YYYY","slut":"YYYY|null","text":Txt}],
  "referenser": [{"namn":"","roll":"","kontakt":"","relation":""}],   // lämnas ut "på begäran" som standard
  "aldrig_pastaa": ["fritext: saker som inte får påstås"]
}
```
Personnummer, ålder och civilstånd lagras aldrig.

## profil/coach.json  (schema: coach)
`{"schema_version":1,"faser":{"intake":{...},"identity":{...},"energy_log":{...},"needs_profile":{...},"options":{...},"experiments":{...},"decision":{...}},"status":{"aktuell_fas":"intake","senast":"ISO-datum"}}`
Fältinnehållet beskrivs i `docs/research/coaching.md` (fas-JSON). Schemat är tillåtande: `additionalProperties: true` inne i faserna.
Valfria tillägg (gamla filer validerar fortfarande):
- `faser.identity.arbetsidentitet`: `{"jag_pa_jobbet_mening","roller":[{"roll","mer_eller_mindre"}],"best_self_teman":[{"tema","kallor_antal","exempel"}],"best_self_portratt","styrkor":[],"mojliga_jag":{}}`
- `faser.needs_profile.kultur_profil`: `{"instrument":"kultur-qsort-18-v1","datum","ideal":{"topp":["s10",…4],"botten":[…4]},"senaste_jobb":{"arbetsplats","topp","botten"},"storsta_glapp":[{"sats","ideal":1-3,"senaste":1-3,"hennes_ord"}],"insikter":[],"dealbreakers":[]}`. Sats-id `s1`–`s18` definieras i `skills/karriarcoach/references/kultur-qsort.md` och delas med arbetsgivarkortet.
- `faser.needs_profile.ledarskap_eget`: `{"ansvar_vilja":{"personal_0_10","sak_0_10","inget_0_10"},"kollegerna_fragar_om":[],"informella_exempel":[{"situation","vad_hon_gjorde","andras_reaktion","till_faktabanken":bool,"faktabank_status":"flaggad|bekraftad|avbojd","fakta_id"}],"stil_spegel","under_stress","styrkor_ledarskap":[]}`. Faktabanken läser poster med `till_faktabanken: true` och `faktabank_status: "flaggad"`, bekräftar med henne och sätter `bekraftad` (+ `fakta_id` = merit-id) eller `avbojd`.
- `faser.needs_profile.ledarskap_behov`: `{"basta_chef_beteenden":[],"samsta_chef_beteenden":[],"chefsegenskaper_rangordnade":["tillganglig|ger_riktning|ger_frihet|skyddar|utvecklar"],"avstamning_frekvens":"dagligen|veckovis|varannan_vecka|vid_behov","autonomistod","misstag_senast","aldrig_igen":[]}`
- `uppfoljning` (toppnivå): `{"baslinje":{"datum","klarhet_0_10","tilltro_0_10","nojdhet_nu_0_10"},"efter_coachning":{…samma,"forstadd_0_10"},"nytt_jobb":[{"manad":3,"trivsel_0_10","kultur_qsort":{"topp","botten"},"chef_utrymme_0_10","valja_igen":bool}]}`
- `status.samtalsform` (fritt): hur hon vill att samtalet förs.

## import/
Underlag som hon lagt dit (gammalt CV, LinkedIn-ZIP). `import/<fil>.anteckning.md` = faktabankens notering om hur det gamla CV:t såg ut (layout, längd, språk) – läses av cv-design.

## profil/det-har-vet-vi.md
Coachens löpande syntes, "Det här vet vi om dig", skriven i hennes egna ord (markdown). Den läses av jobbsök, jakt och ansökan som underlag för vinklar.

## profil/preferenser.json  (schema: preferenser)
```json
{
  "schema_version": 1,
  "riktningar": [{"namn":"","yrkes_id":["taxonomi-id"],"sokord":["..."],"exkludera_ord":["..."]}],
  "orter": [{"namn":"Uppsala","kommun_id":"","region_id":""}],
  "hårda_gränser": {"max_pendling_min":45,"pendling_satt":"kollektivt","max_resdagar_manad":2,"distans_dagar":{"min":0,"max":5},"lonegolv_manad":null,"anstallningsform":["tillsvidare","visstid"],"omfattning":["heltid"]},
  "varden_topp5": [""],
  "vitaminer": {"variation":{"min":0,"max":10},"autonomi":{},"social_kontakt":{},"arbetsbelastning":{}},
  "arbetsdag": {"idealvecka":[{"aktivitet":"","timmar":0}],"energigivare":[],"energitjuvar":[]},
  "kompetens_id": ["taxonomi-id"],
  "exkludera_arbetsgivare": [],
  "sprak_ansokan": ["sv","en"],
  "rollkort_vikter": {"varden":3,"arbetsdag":3,"harda_granser":2,"glapp":1,"marknad":1,"kultur":1,"ledarskap":1}
}
```
Valfritt, skrivs av coachen i fas 7: `"kultur_ideal": {"instrument":"kultur-qsort-18-v1","topp":["s10",…],"botten":[…]}`, `"ledarskap_krav": {"ansvar":"ingen|sak|personal","chefsegenskaper_topp3":[],"avstamning_frekvens":"","krav":["hennes ord"]}`, `"varningssignaler": ["hennes ord"]`. Läses av jobbsökningen, arbetsgivarkortet och rollkorten.
`rollkort_vikter` är valfritt (standardvärdena ovan). Vikterna styr matrisen i `rollkort.py jamfor`. Hon får ändra dem, och 0 betyder att dimensionen inte räknas.

## profil/rost.json
`{"schema_version":1,"gillade_formuleringar":[],"aldrig_ord":[],"tonblandningar":[{"namn":"","personas":[{"id":"","namn":"Kim","vikt":0.7}],"anvand_till":"brev"}],"smyra":{"kim_persona_id":{"sv":null,"en":null}}}`

## design/design.json  (schema: design)
```json
{
  "schema_version": 1, "version": 3, "namn": "Lugn klassisk",
  "layout": "klassisk|sidokolumn|kompakt|portratt|egen:<namn>",
  "tokens": {
    "font_rubrik": "Source Serif 4", "font_brod": "Source Sans 3",
    "storlek_brod_pt": 10.5, "storlek_namn_pt": 24, "storlek_rubrik_pt": 13,
    "radavstand": 1.3, "farg_text": "#1d1d1f", "farg_accent": "#2f5d62", "farg_dampad": "#5f6368",
    "marginal_mm": 18, "sektion_luft_mm": 6, "visa_foto": false,
    "rubrik_stil": "linje|versaler|vanlig|accentstreck"
  },
  "sektioner": ["profil","erfarenhet","utbildning","kompetenser","sprak","kurser","ideella"],
  "historik": [{"version":2,"datum":"","andring":""}],
  "varianter": {"stram": {"layout": "egen:stram", "token_overrides": {"farg_accent": "#333333"}, "sektioner": ["profil","erfarenhet","utbildning"], "beskrivning": "myndighet"}},
  "standardvariant": "standard"
}
```
Typsnitt måste finnas lokalt i `templates/fonts/`, med OFL-licens. Om de saknas används en systemfallback.
`varianter` och `standardvariant` är valfria. En variant lägger `layout`, `token_overrides` och `sektioner` ovanpå designen; den väljs per ansökan med `cv.json.design_variant`, annars `standardvariant`. `layout: "egen:<namn>"` = egen mall från Claude Design i `design/mallar/<namn>/` (`mall.html`, valfri `brev.html`, `mall.css`, `assets/`, `mall.json` med version och osäkra fynd, `versioner/v<N>/`). Slot-attributen står i `skills/cv-design/references/slots.md`. Exportpaketet till Claude Design ligger i `design/till-claude-design/` (+ `.zip`), briefen i `design/brief.md`.

## ansokningar/<YYYY-MM-DD>-<bolag>-<roll>/
- `annons.md`: annonsens fulltext + källa-URL + deadline överst
- `analys.json`: `{"schema_version":1,"krav":[{"krav":"","typ":"ska|meriterande|underforstatt","kravtyp":"hart|onskat","matchar":["r1-m1"],"lucka":false,"kommentar":""}],"nyckelord":[],"vinkel":"","fragor_till_arbetsgivaren":[],"sprak":"sv|en"}`. `kravtyp` är valfritt (saknas = `onskat`): `typ` säger hur annonsen formulerar kravet, `kravtyp` om det stänger dörren. Bara `hart` + `lucka:true` bemöts i brevet; luckor i önskelistan nämns inte, eller i en saklig mening med närmaste erfarenhet.
- `cv.json` (schema: cv), dvs. det som renderas:
```json
{
  "schema_version": 1, "sprak": "sv", "design_version": 3, "design_variant": "stram",
  "person": {"namn":"","titel":"","ort":"","epost":"","telefon":"","lankar":[],"foto":null},
  "profil": "2–4 meningar",
  "sektioner": [
    {"id":"erfarenhet","typ":"erfarenhet","rubrik":"Erfarenhet","poster":[{"titel":"","organisation":"","ort":"","period":"2021 – nu","text":"","punkter":["..."],"kalla":["r1-m1"]}]},
    {"id":"utbildning","typ":"utbildning","rubrik":"Utbildning","poster":[...]},
    {"id":"kompetenser","typ":"lista","rubrik":"Kompetenser","grupper":[{"etikett":"","poster":["..."]}]},
    {"id":"ovrigt","typ":"text","rubrik":"Övrigt","text":""}
  ]
}
```
`design_variant` (valfritt) väljer en variant i `design.json.varianter`; saknas den används `standardvariant`. `id` (valfritt) är en av `profil|erfarenhet|utbildning|kompetenser|sprak|kurser|ideella|referenser|ovrigt` och matchar `design.json.sektioner`, som styr ordningen. Varje `punkter`-rad har en matchande källa i `kalla`, som spårar till merit-id i fakta.json.
- `brev.json`: `{"schema_version":1,"sprak":"sv","mottagare":{"namn":"","bolag":"","adress":""},"datum":"","rubrik":"","stycken":["..."],"halsning":"Vänliga hälsningar","ton":{"personas":[{"namn":"Kim","vikt":0.7}]},"kalla_per_stycke":[["r1-m1"]]}`
  `brev.json` har ingen `person`: `render.py brev` tar brevhuvud och underskrift från `cv.json` i samma mapp, annars från `profil/fakta.json`.
- `mejl.md` (saknas när ansökan görs i formulär och det inte finns någon kontaktperson), `cv.pdf`, `brev.pdf`, `cv.html`, `brev.html`
- `logg.json`: `{"schema_version":1,"bolag":"Region Uppsala","roll":"Kommunikatör","deadline":"YYYY-MM-DD|null","annons_url":"|null","jobb_uid":"uid i jobb.sqlite|null","status":"utkast|skickad|intervju|nej|erbjudande","skickad":null,"kanal":"formular|mejl","kontakt":"","foljupp_datum":null,"anteckningar":[]}`. `bolag`, `roll`, `deadline`, `annons_url` och `jobb_uid` skrivs av ansokan när mappen skapas; översikten läser dem i första hand.
- `intervju.json` (schema: intervju), skrivs av intervju-och-beslut: `{"schema_version":1,"bolag":"","roll":"","arbetsgivarkort":"sok/arbetsgivare/<slug>.json|null","skapad":"YYYY-MM-DD","uppdaterad":"","vinkel":"","omgangar":[{"nr":1,"datum":"","tid":"","format":"plats|video|telefon","plats":"","traffar":[{"namn":"","roll":""}],"ta_med":[],"restid_min":null}],"fragor_troliga":[{"id":"f1","fraga":"","typ":"krav|lucka|brev|standard|ledarstil|motivation","varfor":"","star":{"situation":"","uppgift":"","handling":"","resultat":""},"kalla":["r1-m1"],"lucka_hantering":"","status":"klar|saknar_exempel|ovad"}],"ledarstil":{"svar":"","kalla":["r1-m1"],"kalla_coach":["ledarskap_eget.informella_exempel[0]"]},"fragor_att_stalla":[{"id":"q1","fraga":"","testar":"kultur:s10|ledarskap:<falt>|varningssignal:<text>|okant:<falt i arbetsgivarkortet>|textur:|analys:","prioritet":1,"varfor":"","svar":null}],"arbetsprov":{"forekommer":false,"typ":"urvalsfragor|skrivprov|hemuppgift|case|presentation|annat","instruktion":"","deadline":null,"plan":[],"fil":null},"ovning":[{"datum":"","fraga_id":"f1","bra":"","skarpa":""}],"tackmejl":{"fil":"tackmejl.md","status":"mall|utkast|skickat_av_henne"},"debrief":[{"omgang":1,"datum":"","sag_horde":[],"tolkningar":[],"svar_pa_fragor":[{"fraga_id":"q1","svar":"","undvikande":false}],"chef":{"lmx":"","autonomistod":"","psykologisk_trygghet":""},"kultur_qsort":{"instrument":"kultur-qsort-18-v1","topp":["s10"],"botten":[],"kalla":"intervju","sakerhet":"lag|medel|hog"},"fit_mot_ideal":{"overlapp_topp":0,"konflikt":[],"kommentar":""},"varningssignaler_nya":[{"signal":"","belagg":"","allman":false}],"vill_vidare_0_10":null,"sakerhet_bild_0_10":null,"hennes_ord":"","arbetsgivarkort_uppdaterat":false}]}`. `fragor_att_stalla` har högst 8 poster. `kalla` är merit-id i fakta.json. Q-sortens sats-id (`s1`–`s18`) följer `skills/karriarcoach/references/kultur-qsort.md`.
- `intervju.md` (hennes fusklapp) och `tackmejl.md` (utkast som hon skickar själv; går genom `antiai.py`).
- `beslut.json` (schema: beslut), i mappen för erbjudandet som utlöste beslutet: `{"schema_version":1,"datum":"","alternativ":[{"id":"a1","typ":"erbjudande|stanna|fortsatta_soka","mapp":"ansokningar/<mapp>|null","bolag":"","roll":"","rollkort":"sok/rollkort/stanna.json|null","arbetsgivarkort":null,"villkor":{"lon_manad":null,"anstallningsform":"","omfattning":"","start":null,"slut":null,"pendling_min":null,"pendling_satt":"","pendling_belagg":"provat|beraknat|uppgift|okant","resdagar_manad":null,"distans_dagar":null,"ovrigt":[]}}],"dimensioner":[{"dimension":"kultur|ledarskap|arbetsdag|harda_granser|lon|utveckling","ideal":"","ideal_kalla":["preferenser.kultur_ideal"],"per_alternativ":[{"alternativ":"a1","beskrivning":"","mot_ideal":"nara|delvis|langt|okant","belagg":"egen_upplevelse|intervju|arbetsgivarkort|annons|scb|rollkort|coach|antagande","kallor":[]}]}],"lon":{"ssyk":"2432","scb_manadslon_medel":48400,"ar":2025,"region":"SE","sektor":"0","kalla":"SCB AM0110A/LonYrkeRegion4AN","lonegolv":null,"per_alternativ":[{"alternativ":"a1","lon_manad":null,"diff_scb_kr":null,"diff_scb_pct":null,"over_golv":null}]},"harda_granser_brott":[{"alternativ":"a1","grans":"max_pendling_min","varde":"","hennes_beslut":""}],"ambivalens":{"for":[{"alternativ":"a1","hennes_ord":""}],"emot":[],"beslutssakerhet_0_10":null},"prognosfel":[{"flagga":"titel|lon|fokalism|impact|pendling|chef","iakttagelse":"","hennes_svar":""}],"forhandling":{"alternativ":"a1","mal_lon":null,"golv":null,"underlag":[],"kalla":[],"formuleringar":[],"ovriga_villkor":[],"utfall":null},"beslut":{"val":"a1|null","datum":null,"hennes_ord":"","nasta_steg":[]},"prognos":{"trivsel_0_10":null,"chef_utrymme_0_10":null,"kultur_qsort":{"topp":[],"botten":[]}},"uppfoljning_paminnelser":[{"manad":3,"datum":"","schemalagd":false}]}`. Minst två alternativ, varav ett alltid är `stanna` (eller `fortsatta_soka` om hon är utan jobb). Ingen totalsumma lagras. `prognos` jämförs med `coach.json` → `uppfoljning.nytt_jobb[]` efter 3 och 6 månader (posten där får också `datum`, `arbetsgivare`, `mapp`, `pendling_faktisk_min`, `resdagar_faktisk_manad`, `jamfort_med_prognos`, `hennes_ord`).

## sok/
- `kallor.json` (schema: kallor): `{"schema_version":1,"kallor":[{"id":"af","typ":"jobtech|teamtailor_rss|lever|ashby|greenhouse|smartrecruiters|workday|rss|json_api|sitemap|pagehash|sok_url|mejl","namn":"","url":"","aktiv":true,"anteckning":"","senast_hamtad":null,"etag":null,"hash":null,"tillagd_av":"anvandare|jobbkallor|jobbjakt","tillagd":"YYYY-MM-DD"}]}`
  - Valfria fält per typ: `kalla_url` (sidan användaren angav när flödes-URL:en skiljer sig), `instruktion` (mejl: hur aviseringen sätts upp), `lankmonster` (pagehash/sok_url: regex för annonslänkar, ger länklista-diff), `lista` + `falt` {id,titel,url,arbetsgivare,publicerad,ort,text,deadline} (json_api: punkt-sökvägar), `distans` 0/1/2, `monster` + `krav` + `max_nya` (sitemap), `arbetsgivare_ur_titel` (rss: "Bolag: Titel"), `min_intervall_h`, `signal` + `signalord` (skrivs till `signaler.json`, inte `jobb`), `sokord` (workday).
  - Typer: `sok_url` = sparad sökning på en jobbsajt med filtren i querysträngen; `rss` = generisk RSS/Atom (t.ex. Varbi `https://{kund}.varbi.com/what:rssfeed/`); `sitemap` = nya annons-URL:er ur en sitemap, bara nya sidor hämtas; `mejl` = hämtas inte, träffar kommer via aviseringsmejl eller inklistrade länkar (`ingest.py`).
  - ETag/Last-Modified sparas i `cache/http/`, inte i fältet `etag`. `hash` används av pagehash.
- `kallor_borttagna.json`: samma form som kallor.json plus `borttagen` (datum). `kalla_lagg_till.py --ta-bort` flyttar hit; inget raderas.
- `recept/<namn>.json` (schema: recept): `{"schema_version":1,"namn":"","kallor":["af","x"],"jobtech":{"q":"","occupation-name":[],"occupation-group":[],"municipality":[],"region":[],"remote":null,"extra":{}},"filter":{"exkludera_ord":[],"exkludera_arbetsgivare":[],"min_poang":50},"senast_kord":null}`. `occupation-group` är SSYK nivå 4-id.
- `jobb.sqlite`: tabellen `jobb(uid TEXT PK, kalla, kalla_id, url, titel, arbetsgivare, orgnr, ort, kommun_id, distans INT, publicerad, deadline, anstallningsform, omfattning, kompetenser_json, utdrag, text_hash, dubblett_av, poang INT, poang_skal_json, status TEXT DEFAULT 'ny', forst_sedd, senast_sedd, bedomning_json, hittad_via)`. Status är `ny|intressant|nej|sokt|stangd`.
  - `distans`: 0 på plats, 1 hybrid, 2 helt distans, NULL okänt. `anstallningsform`: tillsvidare|visstid|vikariat|timanstallning|konsult|praktik|NULL. `omfattning`: heltid|deltid|NULL.
  - `kompetenser_json`: `[{"id":"taxonomi-id|null","namn":"","typ":"must|nice|enrich|yrke|yrkesgrupp"}]` (yrke/yrkesgrupp är annonsens yrkesklassning).
  - `bedomning_json`: `{"status":"","orsak":"","taggar":[],"datum":""}` från `lista.py satt`. `hittad_via`: recept-, webbrecept- eller hypotes-id, eller `bevakning`; sätts när jobbet först hittas.
  - `poang_skal_json`: `{"delar":{...},"avdrag":[],"uteslutet":[],"kompetens_traff":[],"kompetens_andel":0.5,"hart_krav_saknas":[]?,"granbrott":["vikariat","ort X utanför dina orter, pendling troligen över 45 min (uppskattning)"]?,"strackjobb":"orsak"?,"flaggor":[]?,"arbetsgivarkort":"slug"?,"matchning_etikett":"Stark matchning|Bra matchning – värd att söka|Sträckjobb – sök!|Möjlig – kolla <krav>|Svag","matchning_motivering":"","joker":true?,"joker_traff":[]?}`. Annonser är önskelistor: kompetensdelen bygger på träffar, bara hårda krav (legitimation, lagkrävd behörighet, körkort, säkerhetsprövning, medborgarskap, centralt språkkrav) flaggas. Etiketten är huvudbudskapet, inte täckningsgrad i procent. Delpoängen `arbetsgivare` finns bara med `score.py --arbetsgivare-vikt N` (standard 0).
- `hypoteser.json` (schema: hypoteser), skrivs av `jakt_hypoteser.py`: `{"schema_version":1,"hypoteser":[{"id":"h-001","typ":"narliggande_yrke|alternativ_titel|energimatch|liknande_arbetsgivare|likar|vardedriven|tillvaxtsignal|webbjakt|nischsajt|dold_marknad|joker","beskrivning":"","metod":"jakt_titlar|jakt_arbetsgivare|jakt_signaler|webbrecept|recept|malbolag|manuell","parametrar":{},"recept":null,"webbrecept":null,"motivering":"","skapad":"YYYY-MM-DD","andrad":"YYYY-MM-DD","status":"aktiv|pausad|beskuren","korningar":[{"datum":"ISO","fynd":0,"uid":[],"anteckning":""}],"senast_kord":"ISO","utbyte":{"fynd":0,"bedomda":0,"intressant":0,"sokt":0,"nej":0,"dubbletter":0,"andel":null,"beraknad":"YYYY-MM-DD"}}]}`. Borttagna flyttas till `hypoteser_borttagna.json`.
- `webbrecept/<namn>.json` (schema: webbrecept), skrivs av `jakt_webbrecept.py`: `{"schema_version":1,"namn":"","hypotes":"h-001|null","titlar":[],"orter":[],"plattformar":["teamtailor"],"nisch":[],"sajter":[],"fragor":[{"id":"q1","fraga":"site:teamtailor.com \"kommunikatör\" Uppsala","plattform":"teamtailor","titel":""}],"skapad":"","andrad":"","senast_kord":null,"korningar":[{"datum","resultat","poster","nya","avvisade"}]}`.
- `rollkort/<slug>.json` (schema: rollkort), skrivs av `rollkort.py`: ett kort per tänkbar riktning (3–5 st) plus alltid `stanna.json` ("stanna/forma om nuvarande jobb", typ `stanna`, byggt ur coach.json). Varje fält är `{"varde": ..., "kallor": [...]}`. En källa är `{"typ":"jobtech_historical|jobtech_search|taxonomi|scb|coach|det_har_vet_vi|preferenser|fakta|arbetsuppgift|annons|forskning|arbetsgivarkort|webb|manuell","url","parametrar","datum","annons_id":[],"fil","fas","falt"}`.
  - Toppnivå: `schema_version, slug, typ: marknad|stanna, titel, skapad, uppdaterad, roll {fraga, yrke_id, yrke, ssyk, yrkesgrupp_id, yrkesgrupp}, region {namn, id}, underlag {fran, annonser_historik, lasta_historik, oppna_nu, ...}`.
  - Marknadsfält (skript): `titlar` [{titel, annonser, arbetsgivare}], `arbetsgivare` [{namn, orgnr, annonser, oppna_nu, annons_id}], `volym` {per_ar [{ar, annonser, hela_aret}], trend, trend_procent, senaste_hela_ar, oppna_nu}, `arbetsuppgifter` [{tema, nyckelord, andel_annonser, annonser, exempel [{text, annons_id}], annons_id, sammanfattning?}], `krav` {must_have, nice_to_have: [{namn, id, typ, andel, annonser, annons_id}], fritext [{tema, typ: ska|meriterande, andel_annonser, exempel}]}, `annonser` (3 aktuella: {id, rubrik, arbetsgivare, ort, publicerad, sista_dag, url, anstallningsform, omfattning}), `lon` {ar, ssyk, matt, per_region {riket|<riksområde>: {alla|offentlig|privat: {manadslon_medel, ki95, antal_anstallda}}}} ur SCB AM0110A/LonYrkeRegion4AN (bara medelvärden; vid fel `varde: null` + `todo`), `lon_fack` (krok, manuellt), `yrkesklassning`.
  - Hennes ord (coachen, via `rollkort.py citat`): `passar_for_att` och `skav`, `varde: [{"text","citat","fas","falt"}]`. Citatet måste finnas ordagrant i coach.json på `faser.<fas>.<falt>`, eller i det-har-vet-vi.md (`fas: det-har-vet-vi`) eller preferenser.json (`fas: preferenser`).
  - `glapp` {har, osakert, saknas: [{krav, typ, andel, hart: bool, fakta: ["kompetenser[c1]", "roller[r1].meriter[r1-m1]"], annons_id}], sammanfattning {harda_krav {har, saknas, osakert}, onskelista {har, av}, tolkning}} (`rollkort.py glapp`). `hart` = legitimation, behörighet/certifiering, körkort, säkerhetsprövning eller centralt språkkrav; resten är arbetsgivarens önskelista och ger inget avdrag i matrisen. `vanlig_tisdag` (text; källor = arbetsuppgifter-index). `crafting` (bara stanna).
  - Krokar `kultur`, `ledarskap`, `arbetsidentitet`: `{"varde": null, "kallor": [], "status": "vantar|ifylld", "forvantat": {...}, "research": "docs/research/kultur-ledarskap-evidens.md"}`. Fylls med `rollkort.py satt <slug> --falt kultur --text '<json>' --kalla '<json>'`, som kräver källa.
  - `rollkort/_matris.json`: senaste `rollkort.py jamfor` (vikter, rader med dimensioner {poang 0–1|null, visa, belagg}). Härledd, inget schema.
- `arbetsgivare/<slug>.json` (schema: arbetsgivarkort), skrivs av `arbetsgivarkort.py bygg <namn|orgnr> [--annons uid]`. Varje block har `status` (auto|manuellt|ifylld|saknas|kraver_nyckel|fel|ej_tillampligt) och `kalla` {typ: regel|jobtech_historical|annons|bolagsverket_ixbrl|cision|kolada|arsredovisning|manuell, url, parametrar, datum}.
  - Toppnivå: `schema_version, slug, arbetsgivare, orgnr (10 siffror|null), typ {varde: kommun|region|stat|privat|ideell, hur, kalla}, skapad, uppdaterad, annons {uid, titel}|null`.
  - `rekrytering` (JobTech Historical): `per_ar [{ar, annonser, hela_aret}], trend_senaste_hela_ar, upprepade_roller [{titel, annonser, halvar, forsta, senaste}], annonserad_roll, osakert: true, tolkning`. Upprepade roller är en osäker signal om omsättning.
  - `annonssprak`: `sjalvbeskrivning: true, varning, teman {tema: {traffar, per_1000_ord, ord}}, axlar [{axel, lutning -1..1|null, lasning}], agentiska_vs_kommunala, lon_angiven, chef_namngiven, mappning {mot: kultur-qsort|ocp, antyder_topp/antyder_botten | dimensioner}`.
  - `ekonomi` (Bolagsverkets värdefulla datamängder, iXBRL; kräver `JOBBSOK_BOLAGSVERKET_ID/SECRET`, annars `kraver_nyckel`): `per_ar [{ar, anstallda, omsattning, resultat}], anstallda_utveckling: vaxer|krymper|stabil`. allabolag.se används inte automatiskt.
  - `press` (Cision-nyhetsrum): `antal_pressmeddelanden, signaler [{datum, titel, url, kategorier: omorganisation|varsel|ny_vd|forvarv|tillvaxt}]` (senaste tre åren).
  - `offentligt`: `kolada` (kommun/region: `matt {total, motivation, ledarskap, styrning, sjukfranvaro_pct, andel_langa_pct: {senaste, serie, trend_3_matningar, riket_samma_ar, kalla}}`) och `arsredovisning` (stat: `sjukfranvaro_pct, belagg` via pdftotext, annars `manuellt`).
  - `manuellt {glassdoor, linkedin_stannar, personer_att_fraga, egna_intryck}`: `{varde, status, instruktion, datum?}`. Fylls med `arbetsgivarkort.py satt <slug> --falt X --text ...`; bevaras vid ombyggnad.
  - `okant`: intervjufrågor `[{fraga, varfor, till, kalla}]`. `matchning {stammer, skaver, okant, varningsflaggor}` mot preferenser `kultur_ideal`, `ledarskap_krav`, `varningssignaler` (läses tolerant). Ingen totalpoäng.
- `senaste_korning.json`: `{"forra_start","senaste_start","recept":[]}` (kor.py; styr `lista.py --nya`).
- `utbyte.json`: utbyte per källa, recept och hittad_via (utbyte.py).
- `signaler.json`: `{"schema_version":1,"signaler":[{"kalla","titel","url","publicerad","utdrag","sedd"}]}` (högst 500).
- `cache/taxonomy/*.json`, `cache/enrich/<text_hash>.json`, `cache/text/<text_hash>.txt` (annonsens fulltext), `cache/http/` (villkorliga anrop), `cache/sitemap/<kalla-id>.json` (sedda URL:er), `cache/malbolag/`, `cache/rollkort/` (JobTech-svar 7 dagar, SCB `scb-<ssyk>-<regioner>.json` 30 dagar)

- `profil/miljo.json` (skrivs av `natkoll.py --spara`): `{"schema_version":1,"testad":"","lage":"fullt|begransat|reserv|ej testad","domaner":[{"doman":"","status":"ok|blockerad|ej testad","nodvandig":true,"anvands_till":"","detalj":""}],"blockerade":[],"nodvandiga_blockerade":[],"pdf":{"chrome":true,"playwright":false,"weasyprint":false,"bild":"pdftoppm|sips|chrome|null","forsta":"chrome|playwright|weasyprint|html"}}`
- `poang_skal_json.granbrott`: brott mot `hårda_gränser` (anställningsform, omfattning, distans, ort/pendling). Flaggas, utesluts inte; etiketten blir "Bryter mot din gräns: …". `hårda_gränser.hemort` (valfritt, namn eller `{"namn","kommun_id"}`) styr pendlingsuppskattningen; annars första orten.

