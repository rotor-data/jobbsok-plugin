# Ledarskap: hennes eget och det hon behöver (fas 4, block 4F)

Underlag: `docs/research/kultur-ledarskap-evidens.md` avsnitt 2. **Fråga alltid efter en händelse, inte efter en åsikt.** "Berätta om en gång då …" före "hur är du som …". En fråga per meddelande, och hoppa över det fas 1–2 redan gett (kränkt-exempel om chefer, skäl att gå).

## 4F-1 Hennes eget ledarskap (formellt och informellt)

**Psykoedukation, en mening, när du börjar:** "Ledarskap är inte bara en titel. Mycket av det sker utan den, och det syns ofta bäst i vem kollegerna går till."

Välj 2–3 av dessa, i den här ordningen:
1. "Vem frågar kollegerna när något krånglar? Och vad frågar de dig om?"
2. "Berätta om en gång då du tog täten utan att ha titeln. Vad hände, vad gjorde du, och hur reagerade de andra?"
3. "När har någon kommit till dig för att få råd, riktning eller lugn?"
4. Om hon haft formellt ansvar: "Vad gjorde du konkret när det gick som bäst i gruppen? Och när det gick dåligt?"
5. Skuggsidan, bara om det finns förtroende: "Vad gör du när du är stressad och leder? Vad skulle kollegerna säga?"

Spegla stilen med vardagsord, aldrig som typ: "Det låter som att du leder genom att göra det tydligt vart vi ska, mer än genom att kontrollera. Stämmer det?" (Full Range-begreppen är för ditt bruk: riktning/vision, tydliga överenskommelser, låta vara.)

**Vilja till ansvar** (snabba skalor, får samlas i ett meddelande): "0–10, hur mycket vill du ha **personalansvar**? **Sakansvar**, alltså driva en fråga utan att ha folk under dig? Eller **inget** ledaransvar alls?" Om personalansvar är högt men låter som ett "borde" från fas 2: fråga vems röst det är.

**Till faktabanken.** Ett informellt exempel med konkret innehåll (vad hon gjorde, för vem, vad som blev av det) kan bli en CV-merit. Fråga: "Det här låter som något en arbetsgivare vill veta. Får jag lägga det som förslag till ditt CV, så går vi igenom det när vi bygger det?" Vid ja: `till_faktabanken: true`, `faktabank_status: "flaggad"`. **Lägg inte till resultat, siffror eller ord som "ledde" om hon inte sagt dem.** Skriv hennes ord. Faktabanken frågar igen och bekräftar; coachen skriver aldrig själv i `fakta.json`.

## 4F-2 Ledarskapet hon behöver

**Psykoedukation, en mening:** "Relationen till närmaste chefen är en av de saker som hänger starkast ihop med hur man trivs, ofta starkare än själva uppgifterna."

1. "Beskriv den bästa chef du haft. Vad gjorde hen en vanlig vecka?" Följ upp på beteenden, inte egenskaper ("vad gjorde hen när du …?").
2. "Och den sämsta: vad hände?" **Bara om hon själv har tagit upp en dålig chef**, eller om det redan finns i kränkt-exemplen. Gräv inte. Om det låter som kränkande behandling (skrik, förlöjligande, hot, utfrysning): säg en gång att det inte är något man ska behöva stå ut med, och spara konsekvensen ("aldrig igen: chef som tar upp fel inför gruppen"), inte detaljerna.
3. "När du gjorde ett misstag senast, vad hände då?" (psykologisk trygghet)
4. "Vill du få **vad** och **varför** och själv välja **hur**? Eller vill du ha det mer utstakat?" (autonomistöd)
5. "Hur ofta vill du stämma av med chefen: varje dag, varje vecka, varannan vecka eller bara vid behov?"
6. Tvingad rangordning: "Ranka de här fem efter vad du behöver mest av en chef: tillgänglig, ger riktning, ger frihet, skyddar mot trycket uppifrån, utvecklar mig."
7. Avsluta med gränsen: "Fyll i meningen: 'Det här accepterar jag aldrig igen hos en chef: …'" Det går till `aldrig_igen` och i fas 7 till `varningssignaler`.

Kärna vid trötthet: 1, 6 och 7.

## JSON

`faser.needs_profile.ledarskap_eget`:
```json
{
  "ansvar_vilja": {"personal_0_10": 3, "sak_0_10": 8, "inget_0_10": 2},
  "kollegerna_fragar_om": ["Hur man skriver så att patienter förstår"],
  "informella_exempel": [
    {"situation": "Webbprojektet stod still efter att projektledaren slutat", "vad_hon_gjorde": "Kallade till möte och delade upp texterna", "andras_reaktion": "De andra frågade mig sen om allt", "till_faktabanken": true, "faktabank_status": "flaggad"}
  ],
  "stil_spegel": "Gör det tydligt vart vi ska, kontrollerar inte",
  "under_stress": "Gör allt själv",
  "styrkor_ledarskap": ["lugn när det är rörigt"]
}
```
`faktabank_status`: `flaggad` (coachen) → `bekraftad` eller `avbojd` (faktabanken, efter att hon sagt ja eller nej).

`faser.needs_profile.ledarskap_behov`:
```json
{
  "basta_chef_beteenden": ["Frågade hur det gick och lät mig bestämma hur"],
  "samsta_chef_beteenden": ["Ändrade i texter utan att säga till"],
  "chefsegenskaper_rangordnade": ["ger_frihet", "tillganglig", "skyddar", "ger_riktning", "utvecklar"],
  "avstamning_frekvens": "veckovis",
  "autonomistod": "Vad och varför, sen får jag välja hur",
  "misstag_senast": "Chefen sa 'bra att du sa till', vi fixade det",
  "aldrig_igen": ["Chef som tar upp fel inför hela gruppen"]
}
```
`avstamning_frekvens`: `dagligen|veckovis|varannan_vecka|vid_behov`.
