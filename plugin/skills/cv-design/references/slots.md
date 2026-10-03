# Platser för innehållet (slot-attribut)

En egen mall är vanlig HTML där några element har data-attribut. De talar om var hennes innehåll ska in. Allt annat (klasser, CSS, extra `<div>`-ar) är fritt. Renderas av `scripts/mall_slots.py`; samma escaping som `render.py`.

## Attributen

| Attribut | Gör | Exempel |
|---|---|---|
| `data-slot="sökväg"` | Elementets text blir värdet. På `<img>` blir det `src`. Tomt värde = elementet tas bort. | `<h1 data-slot="person.namn">` |
| `data-slot-rubrik` | Sektionens rubrik (svenska eller engelska efter `cv.json.sprak`). | `<h2 data-slot-rubrik>` |
| `data-sektion="nyckel"` | Behållare för en sektion. Tas bort om sektionen saknas i cv.json. | `<section data-sektion="kompetenser">` |
| `data-repeat="lista"` | Elementet upprepas en gång per objekt. Ha bara **ett** exempel. | `<li data-repeat="punkter">` |
| `data-repeat="sektion:nyckel"` | Upprepas per post i den sektionen, var som helst i mallen. | `<article data-repeat="sektion:erfarenhet">` |
| `data-repeat="sektioner"` | Allmän sektion: alla sektioner som inte har en egen `data-sektion`. | |
| `data-if="sökväg"` | Tas bort om värdet saknas. `not sökväg` går också. | `<img data-if="person.foto" data-slot="person.foto">` |
| `data-href="url"` | Sätter `href` från värdet (länkar i kontaktraden). | |

Sektionsnycklar: `profil`, `erfarenhet`, `utbildning`, `kompetenser`, `sprak`, `kurser`, `ideella`, `referenser`, `ovrigt`.

## Sökvägar

- **Person**: `person.namn`, `person.titel`, `person.foto`, `person.epost`, `person.telefon`, `person.ort`; lista `person.kontakt` med `text`, `url`, `etikett`.
- **Sektion** (inne i `data-sektion` eller `data-repeat="sektioner"`): `rubrik`; listor `poster`, `grupper`, `stycken`; villkor `ar_poster`, `ar_lista`, `ar_text`.
- **Post** (inne i `data-repeat="poster"`): `titel`, `organisation`, `ort`, `plats` (organisation + ort), `period`, `text`; lista `punkter`.
- **Grupp** (kompetenser, språk): `etikett`, `rad` (posterna med " · "); lista `poster`.
- **Strängar** i en lista (punkter, stycken, poster): elementets text blir strängen. `data-slot="."` går också.
- `data-slot="profil"` på toppnivå: hela profiltexten i ett element.
- **Brev**: `person.*`, `mottagare.bolag`, `mottagare.namn`, lista `mottagare.adress_rader`, `datum`, `rubrik`, lista `stycken`, `halsning`.
- `titel` på `<title>`: dokumentets titel ("Namn – CV").

## Ordning och säkerhetsnät

- Sektioner som ligger i samma förälder ordnas efter `design.json.sektioner` (eller variantens `sektioner`). Importen sätter ordningen från hennes design.
- Saknar mallen plats för något som finns i innehållet (en sektion, en roll, punkter, en grupps etikett) läggs det till i en enkel standardform. Inget tappas, men det kan se annorlunda ut. `mall_kontroll.py` visar det.
- En post med många punkter får `data-lang` och får då brytas mellan sidor; andra poster hålls ihop (`break-inside: avoid`).
- Mallens CSS får `tokens.css`-variablerna före sig (`--farg-accent`, `--font-rubrik`, `--storlek-brod` …), så `design_tool.py set` och `token_overrides` i varianter fungerar om mallen använder dem.

## Minsta exempel

```html
<header>
  <h1 data-slot="person.namn">Namn</h1>
  <ul><li data-repeat="person.kontakt"><a data-slot="text">e-post</a></li></ul>
</header>
<section data-sektion="erfarenhet">
  <h2 data-slot-rubrik>Erfarenhet</h2>
  <article data-repeat="poster">
    <h3 data-slot="titel">Titel</h3> <span data-slot="period">2021 – nu</span>
    <p data-slot="plats">Arbetsgivare, ort</p>
    <ul><li data-repeat="punkter">Punkt</li></ul>
  </article>
</section>
<section data-repeat="sektioner">
  <h2 data-slot-rubrik>Rubrik</h2>
  <p data-repeat="stycken">Text</p>
</section>
```
