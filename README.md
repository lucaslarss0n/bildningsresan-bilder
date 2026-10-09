# bildningsresan-bilder

Verktyg för bilderna i Bildningsresan. Sidan får bara visa bilder som ligger i dess egen bildlagring, så bilderna hämtas eller ritas här och laddas sedan upp dit.

Två körningar använder repot. "Bildningsresan bilder" (Claude Code) hämtar foton, kartor och konstverk från Wikimedia Commons. "Bildningsresan morgon" (Cowork) når inte Wikimedia och ritar bara egna figurer.

## Hämta bilder från Commons

Kräver att körningen når commons.wikimedia.org och upload.wikimedia.org.

Skriv en begäran till en fil och kör `python3 scripts/fetch.py <filen>`.

```json
{
  "id": "2026-10-09-a",
  "thumb": 360,
  "width": 1200,
  "articles": [{"wiki": "en", "title": "Xi_Jinping", "limit": 15}],
  "searches": [{"q": "Persepolis Apadana relief", "limit": 8}],
  "files": ["File:Exact name on Commons.jpg"]
}
```

- `id` namnger mappen med resultatet. Använd ett nytt för varje begäran (datum plus bokstav).
- `articles` ger de bilder som en Wikipedia-artikel visar, med artikelns egna bildtexter, som förhandsbilder i bredden `thumb`. Det är oftast det bästa stället att leta. Svenska (`"wiki": "sv"`) och engelska artiklar har ofta olika bilder.
- `searches` söker i Commons och ger förhandsbilder. Bra för kartor, byggnader, föremål och konstverk.
- `files` hämtar exakta filer i bredden `width`, för de bilder du har valt.

Resultatet hamnar i `out/<id>/`. `manifest.json` har en post per bild med `name`, `caption` (Wikipedias bildtext), `description`, `date`, `artist`, `license`, `licenseUrl`, `page` (Commons-sidan), `width`, `height` och `path`. Filer från `articles` och `searches` har `kind: "candidate"` och börjar på `c-`, filer från `files` har `kind: "file"` och börjar på `f-`.

Arbeta i två steg. Begär först förhandsbilder och titta på dem med Read, gärna som ett kontaktark hopklistrat med Pillow, och kontrollera att varje bild visar det bildtexten säger. Begär sedan de valda med `files` i en ny begäran. Hoppa över en bild om `license` saknas.

## Rita en egen figur

```
npm install            # en gång per körning
node scripts/figure.mjs figur.html /tmp/fig/namn
```

`figur.html` innehåller bara figurens egen markup, gärna med en `<style>`. Ramen är 600 px bred, typsnittet är Hanken Grotesk, och färgerna ska tas från variablerna `--bg --fg --muted --line --box --strong --a1 --a2 --a3 --a4`, så att samma figur blir rätt i både ljust och mörkt läge. Skriptet ger `namn-light.jpg` och `namn-dark.jpg` och skriver ut deras mått som JSON. Titta på båda med Read innan du laddar upp dem. Texten i figuren ska vara minst 13 px, eftersom den visas i ungefär 350 px bredd på en telefon. `examples/` har en figur att utgå från.

## Till sidan

1. Förminska foton till högst 1200 px bredd (stående bilder högst 900 px) och spara som JPEG, kvalitet 82, med Pillow. Figurer laddas upp som de är.
2. Ladda upp med Artifact-verktyget: `asset: true`, `url` = Bildningsresans artifact, `file_paths` = filerna. Svaret ger ett id per fil.
3. Skriv ämnets fält `images` enligt körningens instruktion.
