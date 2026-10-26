"""Download free images from Wikimedia Commons for Bildningsresan.

Reads the request file given as the first argument and writes out/<id>/ with
the image files and a manifest.json describing each one (caption, author,
license, source page). Run it as: python3 scripts/fetch.py <request file>
Uses only the standard library, so there is nothing to install.

Request format (every key optional except "id"):
{
  "id": "2026-10-08-a",                      unique per request; names the output folder
  "thumb": 360,                              width of candidate previews (rounded up to a standard width)
  "width": 1280,                             width of chosen files (rounded up to a standard width)
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
# Wikimedia rate limits (429) thumbnails in other widths, so widths are rounded up to one of these.
STANDARD_WIDTHS = [120, 250, 330, 500, 960, 1280, 1920, 3840]
ORIGINAL_MAX_BYTES = 25_000_000  # largest original to download when a thumbnail is refused


def standard_width(w):
    return next((s for s in STANDARD_WIDTHS if s >= w), STANDARD_WIDTHS[-1])


BACKOFF = [10, 30, 60, 90]  # seconds; Commons rate limits (429) need long pauses


def wait_for(e, n):
    """Seconds to wait before retry n: Retry-After when the server gives one."""
    after = getattr(e, "headers", None) and e.headers.get("Retry-After")
    if after and after.strip().isdigit():
        return min(int(after), 60)
    return BACKOFF[min(n, len(BACKOFF) - 1)]


def get(url, binary=False, tries=5):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data.decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - retried, then reported
            code = getattr(e, "code", None)
            if n == tries - 1 or code in (400, 403, 404):
                raise
            delay = wait_for(e, n) if code in (429, 503) else 2 + 3 * n
            print("retry in %ds after %s" % (delay, e), file=sys.stderr)
            time.sleep(delay)


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
        "_orig": ii.get("url"),
        "_bytes": ii.get("size") or 0,
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
    thumb = standard_width(int(req.get("thumb", 360)))
    width = standard_width(int(req.get("width", 1280)))
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
            url, orig, size = e.pop("_url"), e.pop("_orig"), e.pop("_bytes")
            try:
                try:
                    data = get(url, binary=True, tries=3)
                except Exception:  # noqa: BLE001
                    # Wikimedia sometimes refuses to render a new thumbnail; the original
                    # file is served from cache, so take it when it is not too large.
                    if (kind != "file" or not orig or orig == url or size > ORIGINAL_MAX_BYTES
                            or e["mime"] in ("image/svg+xml", "image/tiff")):
                        raise
                    url, data = orig, get(orig, binary=True, tries=3)
                    e.update(original=True, width=e["origWidth"], height=e["origHeight"])
                ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
                ext = ext if ext in (".png", ".gif", ".webp", ".tif", ".tiff") else ".jpg"
                fname = "%s-%02d-%s%s" % (kind[0], len(manifest["items"]) + 1, slug(e["name"]), ext)
                open(os.path.join(outdir, fname), "wb").write(data)
                e.update(kind=kind, source=source, path=fname, bytes=len(data))
                manifest["items"].append(e)
            except Exception as ex:  # noqa: BLE001
                manifest["errors"].append("download %s: %s" % (t, ex))
            time.sleep(1)

    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w"), ensure_ascii=False, indent=1)
    print("%d items, %d errors" % (len(manifest["items"]), len(manifest["errors"])))


if __name__ == "__main__":
    main()
