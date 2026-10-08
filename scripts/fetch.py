"""Download free images from Wikimedia Commons for Bildningsresan.

Reads requests/request.json and writes out/<id>/ with the image files and a
manifest.json describing each one (caption, author, license, source page).
Uses only the standard library, so the workflow needs no install step.

Request format (every key optional except "id"):
{
  "id": "2026-10-08-a",                      unique per request; names the output folder
  "thumb": 360,                              width of candidate previews
  "width": 1280,                             width of chosen files
  "articles": [{"wiki": "en", "title": "Xi_Jinping", "limit": 15}],
                                             images used in a Wikipedia article, as previews
  "searches": [{"q": "Great Hall of the People", "limit": 8}],
                                             Commons file search, as previews
  "files": ["File:Xi Jinping 2019.jpg"]      exact Commons files, at full "width"
}
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "BildningsresanBot/1.0 (https://github.com/lucaslarss0n/bildningsresan-bilder)"
COMMONS = "https://commons.wikimedia.org/w/api.php"
KEEP_MIME = {"image/jpeg", "image/png", "image/webp", "image/svg+xml", "image/gif", "image/tiff"}


def get(url, binary=False, tries=3):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data.decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - retried, then reported
            if n == tries - 1:
                raise
            time.sleep(2 + 3 * n)


def api(params):
    params = dict(params, format="json", formatversion="2")
    return get(COMMONS + "?" + urllib.parse.urlencode(params))


def text(v):
    """Commons metadata values are HTML; keep the words only."""
    v = re.sub(r"<[^>]+>", " ", v or "")
    return re.sub(r"\s+", " ", html.unescape(v)).strip()


def info(titles, width):
    """imageinfo for up to 50 Commons file titles, in the order given."""
    out = {}
    for i in range(0, len(titles), 50):
        d = api({"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "imageinfo",
                 "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(width)})
        norm = {x["from"]: x["to"] for x in d.get("query", {}).get("normalized", [])}
        pages = {p["title"]: p for p in d.get("query", {}).get("pages", [])}
        for t in titles[i:i + 50]:
            p = pages.get(norm.get(t, t))
            if p and not p.get("missing") and p.get("imageinfo"):
                out[t] = p
    return out


def entry(title, page, caption=None):
    ii = page["imageinfo"][0]
    m = ii.get("extmetadata", {})
    g = lambda k: text(m.get(k, {}).get("value"))
    return {
        "name": page["title"],
        "caption": caption,
        "description": g("ImageDescription")[:600] or None,
        "date": g("DateTimeOriginal") or None,
        "artist": g("Artist") or None,
        "credit": g("Credit")[:300] or None,
        "license": g("LicenseShortName") or None,
        "licenseUrl": g("LicenseUrl") or None,
        "attributionRequired": g("AttributionRequired") or None,
        "page": ii.get("descriptionurl"),
        "mime": ii.get("mime"),
        "origWidth": ii.get("width"),
        "origHeight": ii.get("height"),
        "width": ii.get("thumbwidth"),
        "height": ii.get("thumbheight"),
        "_url": ii.get("thumburl") or ii.get("url"),
    }


def slug(s):
    s = re.sub(r"^File:", "", s)
    s = re.sub(r"\.[A-Za-z0-9]+$", "", s)
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:70] or "bild"


def article_files(wiki, title, limit):
    """Images an article shows, with the article's own captions."""
    url = "https://%s.wikipedia.org/api/rest_v1/page/media-list/%s" % (wiki, urllib.parse.quote(title, safe=""))
    items = get(url).get("items", [])
    res = []
    for it in items:
        if it.get("type") != "image" or not it.get("title"):
            continue
        cap = (it.get("caption") or {}).get("text")
        res.append(("File:" + re.sub(r"^[^:]+:", "", it["title"]), text(cap) or None))
        if len(res) >= limit:
            break
    return res


def search_files(q, limit):
    d = api({"action": "query", "list": "search", "srnamespace": "6", "srsearch": q, "srlimit": str(limit)})
    return [(x["title"], None) for x in d.get("query", {}).get("search", [])]


def main():
    req = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "requests/request.json"))
    rid = re.sub(r"[^A-Za-z0-9_-]", "", str(req["id"]))
    thumb, width = int(req.get("thumb", 360)), int(req.get("width", 1280))
    outdir = os.path.join("out", rid)
    os.makedirs(outdir, exist_ok=True)
    manifest = {"id": rid, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items": [], "errors": []}

    groups = []  # (kind, source, [(title, caption)], width)
    for a in req.get("articles", []):
        try:
            groups.append(("candidate", "%s:%s" % (a.get("wiki", "en"), a["title"]),
                           article_files(a.get("wiki", "en"), a["title"], int(a.get("limit", 15))), thumb))
        except Exception as e:  # noqa: BLE001
            manifest["errors"].append("article %s: %s" % (a.get("title"), e))
    for s in req.get("searches", []):
        try:
            groups.append(("candidate", "search:" + s["q"], search_files(s["q"], int(s.get("limit", 8))), thumb))
        except Exception as e:  # noqa: BLE001
            manifest["errors"].append("search %s: %s" % (s.get("q"), e))
    files = [f if f.startswith("File:") else "File:" + f for f in req.get("files", [])]
    if files:
        groups.append(("file", "files", [(f, None) for f in files], width))

    seen = set()
    for kind, source, pairs, w in groups:
        try:
            pages = info([t for t, _ in pairs], w)
        except Exception as e:  # noqa: BLE001
            manifest["errors"].append("info %s: %s" % (source, e))
            continue
        for t, cap in pairs:
            p = pages.get(t)
            if not p:
                manifest["errors"].append("not on Commons: %s" % t)
                continue
            e = entry(t, p, cap)
            key = (kind, e["name"])
            if key in seen or e["mime"] not in KEEP_MIME:
                continue
            seen.add(key)
            ext = ".png" if e["_url"].lower().endswith(".png") else ".jpg"
            fname = "%s-%02d-%s%s" % (kind[0], len(manifest["items"]) + 1, slug(e["name"]), ext)
            try:
                data = get(e.pop("_url"), binary=True)
                open(os.path.join(outdir, fname), "wb").write(data)
                e.update(kind=kind, source=source, path=fname, bytes=len(data))
                manifest["items"].append(e)
            except Exception as ex:  # noqa: BLE001
                manifest["errors"].append("download %s: %s" % (t, ex))
            time.sleep(0.3)

    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w"), ensure_ascii=False, indent=1)
    print("%d items, %d errors" % (len(manifest["items"]), len(manifest["errors"])))


if __name__ == "__main__":
    main()
