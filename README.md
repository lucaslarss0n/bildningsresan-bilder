# bildningsresan-bilder

Hämtar fria bilder från Wikimedia Commons till Bildningsresan och ritar egna figurer.
Morgonkörningen följer den här filen. Sidan Bildningsresan får bara visa bilder som
ligger i dess egen bildlagring, och morgonkörningens arbetsyta når inte Wikimedia.
GitHubs servrar gör det, så nedladdningen sker här.

## Hämta bilder från Commons

1. Klona repot (`git clone --depth 1`). Kör `git fetch origin main` och `git rebase origin/main`
   innan du pushar.
2. Skriv `requests/request.json` och pusha till `main`. Det startar jobbet *Hämta bilder*
   (`.github/workflows/fetch.yml`, `scripts/fetch.py`).

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

   - `id` måste vara nytt för varje begäran (datum plus bokstav).
   - `articles` ger de bilder som en Wikipedia-artikel visar, med artikelns egna bildtexter,
     som förhandsbilder i bredden `thumb`. Det är oftast det bästa stället att leta, eftersom
     Wikipedias redaktörer redan har valt ut de bästa bilderna. Svenska (`"wiki": "sv"`) och
     engelska artiklar har ofta olika bilder.
   - `searches` söker i Commons och ger förhandsbilder. Bra för kartor
     ("map Achaemenid Empire 500 BC"), byggnader, föremål och konstverk.
   - `files` hämtar exakta filer i bredden `width`, för de bilder du har valt.
3. Vänta på resultatet. Jobbet tar ungefär en minut. Kontrollera var tionde sekund, i högst
   fyra minuter:
   `git fetch --depth 1 origin out` och se om `origin/out` innehåller `<id>/manifest.json`
   (`git show origin/out:<id>/manifest.json`). Grenen `out` skrivs över varje gång, så det
   finns bara en begäran där åt gången.
4. Packa upp: `git worktree add /tmp/out origin/out` eller `git archive origin/out <id> | tar -x`.
   `manifest.json` har en post per bild med `name`, `caption` (Wikipedias bildtext),
   `description`, `date`, `artist`, `license`, `licenseUrl`, `page` (Commons-sidan), `width`,
   `height` och `path` (filen i mappen). Filer från `articles`/`searches` har `kind: "candidate"`
   och börjar på `c-`, filer från `files` har `kind: "file"` och börjar på `f-`.
5. Titta på förhandsbilderna med Read innan du väljer, gärna som ett kontaktark
   (klistra ihop dem med Pillow). Kontrollera att bilden visar det bildtexten säger.
6. Begär de valda filerna med `files` i en ny begäran (nytt `id`), och vänta igen.

Bara filer med en fri licens finns på Commons. Hoppa ändå över en bild om `license` saknas.

## Rita en egen figur

```
npm install            # en gång per körning
node scripts/figure.mjs figur.html /tmp/fig/namn
```

`figur.html` innehåller bara figurens egen markup, gärna med en `<style>`. Ramen är 600 px
bred, typsnittet är Hanken Grotesk, och färgerna ska tas från variablerna
`--bg --fg --muted --line --box --strong --a1 --a2 --a3 --a4`, så att samma figur blir rätt
i både ljust och mörkt läge. Skriptet ger `namn-light.jpg` och `namn-dark.jpg` och skriver
ut deras mått som JSON. Titta på båda med Read innan du laddar upp dem. Texten i figuren ska
vara minst 13 px (den visas i ungefär 350 px bredd på en telefon). `examples/` har en figur
att utgå från.

## Till sidan

1. Förminska foton till högst 1200 px bredd (stående bilder högst 900 px) och spara som JPEG,
   kvalitet 82, med Pillow.
2. Ladda upp med Artifact-verktyget: `asset: true`, `url` = Bildningsresans artifact,
   `file_paths` = filerna. Svaret ger ett id per fil.
3. Skriv ämnets fält `images` (se morgoninstruktionen).
