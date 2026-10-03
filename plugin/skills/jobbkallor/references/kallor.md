# Källor – referens för jobbkallor och jobbsok

Kontrollerat 2026-10-01. Fullständig research: `docs/research/jobbkallor.md` och `docs/research/jobbsajter.md` i repot.

## Typer i kallor.json och hur de hämtas

| typ | Vad | Hämtning | Försvunna annonser |
|---|---|---|---|
| jobtech | Platsbanken via JobTech JobSearch | via recept, inkrementellt med `published-after` från `senast_kord` (−1 h marginal), 100 per sida, högst 2000 | stängs när deadline passerat |
| teamtailor_rss | `https://{bolag}.teamtailor.com/jobs.rss` eller egen domän + `/jobs.rss` | hela flödet, ETag | stängs |
| lever | `api.lever.co/v0/postings/{bolag}?mode=json` (EU: `api.eu.lever.co`) | hela | stängs |
| ashby | `api.ashbyhq.com/posting-api/job-board/{bolag}` | hela | stängs |
| greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | hela | stängs |
| smartrecruiters | `api.smartrecruiters.com/v1/companies/{id}/postings` | hela (≤1000) | stängs |
| workday | `POST {tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` | best effort (≤400), inofficiellt | stängs |
| rss | generisk RSS/Atom, t.ex. Varbi `https://{kund}.varbi.com/what:rssfeed/`, We Work Remotely | hela flödet | stängs (Varbi-RSS kan sakna äldre annonser) |
| json_api | JSON-lista med `falt`-mappning (Remote OK) | hela | stängs |
| sitemap | nya annons-URL:er ur sitemap (The Hub); bara nya sidor hämtas, JSON-LD tolkas | ≤`max_nya` per körning | stängs när URL:en försvinner |
| pagehash | karriärsida utan flöde; med `lankmonster` blir varje annonslänk en träff, annars en "sidan har ändrats"-träff | hela sidan, robots.txt följs | stängs |
| sok_url | sparad sökning på en jobbsajt (filter i querysträngen) | annonslänkar plockas ut | stängs |
| mejl | LinkedIn, Indeed m.fl.: jobbaviseringar i mejl eller inklistrade länkar | hämtas inte; `ingest.py` | – |

Fältet `distans`: 0 på plats, 1 hybrid, 2 helt distans. Källor med `signal: true` (Cision) hamnar i `sok/signaler.json`.

## Regler

- User-Agent `jobbsok-plugin/0.1 (personlig jobbsökning)`, högst 1 anrop per sekund och värd, robots.txt följs för webbsidor och flöden.
- LinkedIn, Indeed, Glassdoor och Jobbland: aldrig automatiskt (villkor eller `Disallow: /`). Mejlavisering eller inklistrade länkar.
- MFN: `Disallow: *.rss$`, används inte. Remotive: `Disallow: /api/*`, används inte automatiskt.
- Döda: Blocket Jobb, StepStone.se, Jobbdirekt. Jobbsafari, Indeed m.fl. aggregatorer ger mest dubbletter av Platsbanken.
- ReachMee har inget öppet flöde; de annonserna finns oftast i Platsbanken.
- Bemanningsföretag (Academic Work, Randstad, Poolia, Wise m.fl.) läses via JobTech med `q=<bolag>` eller `employer=<orgnr>`.

## Taxonomi

- `occupation-name` = yrkesbenämning, `occupation-group` = SSYK nivå 4 (taxonomitypen `ssyk-level-4`), `municipality` = kommun, `region` = län.
- `taxonomi_sok.py` cachar hela listan per typ i `cache/taxonomy/`.

## Skript

| Skript | Gör |
|---|---|
| `kalla_lagg_till.py <url> [--namn] [--typ mejl] [--prova]` / `--lista` / `--pausa` / `--aktivera` / `--ta-bort` | lägger till och sköter källor |
| `upptack_ats.py <url>` | identifierar rekryteringssystem, föreslår källpost (skriver inget) |
| `taxonomi_sok.py <typ> <etikett>…` | taxonomi-id |
| `malbolag.py [--yrke/--yrkesgrupp/--q] [--kommun/--region] [--ar 3]` | arbetsgivare rankade efter antal annonser (Historical) |
| `fetch.py --recept <namn>` / `--alla-bevakade` | hämtar |
| `ingest.py [--kalla webb] [--hittad-via id] < poster.json` | lägger in poster från webbsök, mejl eller länkar |
| `kor.py --alla` | fetch → dedupe → score → lista (det som schemaläggs) |
