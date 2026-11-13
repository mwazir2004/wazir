#!/usr/bin/env python3
"""
Builds a static, multi-page test website for GitHub Pages.

Everything (images, videos, HTML pages, sitemap) is generated locally, so the
site has no external media dependencies and every asset is unique and stable.

Requirements: Python 3.9+, Pillow (pip install pillow), ffmpeg on PATH.
Usage:        python generate.py [--out docs] [--images-per-gallery 8] [--base-url https://USER.github.io/REPO]
"""
import argparse, colorsys, html, math, os, random, shutil, subprocess, sys
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SITE_NAME = "Ridgeline Field Notes"
AUTHOR = "Ines Varga"  # fictional

GALLERIES = [
    ("coastal-fog",   "Coastal fog",   "Headlands and sea stacks disappearing into morning fog.",
     [(196, 214, 222), (232, 236, 238)], [(70, 92, 104), (30, 44, 54)], True),
    ("high-desert",   "High desert",   "Mesas, dry washes and long shadows at the edge of the day.",
     [(240, 178, 122), (250, 226, 190)], [(150, 82, 52), (58, 32, 30)], False),
    ("alpine-dawn",   "Alpine dawn",   "First light on granite and snowfields above the tree line.",
     [(250, 196, 180), (196, 214, 240)], [(120, 132, 168), (36, 42, 66)], False),
    ("river-valleys", "River valleys", "Braided rivers, gravel bars and green valley floors.",
     [(176, 210, 210), (226, 238, 230)], [(84, 128, 104), (22, 56, 44)], True),
    ("night-ridges",  "Night ridges",  "Ridgelines under moonlight and the last blue of dusk.",
     [(20, 30, 64), (64, 84, 140)], [(30, 40, 70), (6, 10, 22)], False),
    ("autumn-passes", "Autumn passes", "Larch and aspen turning gold on the high passes.",
     [(244, 214, 150), (248, 238, 214)], [(196, 120, 40), (70, 40, 20)], False),
]

VIDEO_TITLES = [
    "Fog rolling over the headland", "Shadows crossing the mesa", "Alpenglow timelapse",
    "Clouds over the valley", "Moonrise behind the ridge", "Wind in the larches",
    "Drive over the pass", "Last light on the coast",
]

CAMERAS = ["Fujifilm X-T5", "Nikon Z6 II", "Sony A7 IV", "Canon R6", "Leica Q2"]
LENSES = ["24mm f/2.8", "35mm f/1.8", "70-200mm f/4", "16-35mm f/4", "50mm f/2"]

PARAGRAPHS = [
    "We left the trailhead before five, headlamps on, and reached the saddle just as the sky started to change colour. The wind dropped for about ten minutes and that was the window.",
    "Most of the frames from this trip were made within twenty minutes of sunrise. After that the light flattens out and the ridges lose their layers, so the rest of the day goes to scouting.",
    "Fog is unpredictable here. Some mornings it sits below the cliffs like a second ocean; other mornings it swallows everything and there is nothing to photograph but the sound of the surf.",
    "I carry one body and two lenses on longer walks. A wide lens for the foreground and a short telephoto for compressing the ridgelines into flat bands of tone.",
    "The road over the pass closes with the first heavy snow, usually in late October. We made it across two days before the gate went down.",
    "Back at camp the light went blue and then grey, and the only thing left to do was cook, check the cards and plan the next morning's route.",
    "The river changes course every spring. Gravel bars that were islands last year are now part of the bank, and the channels braid differently every visit.",
    "Night shooting means long exposures, cold fingers and a lot of waiting. The moon came over the ridge at 21:40 and lit the snowfield for almost an hour.",
]

JOURNAL_TITLES = [
    "Three mornings on the headland", "Scouting the mesa country", "Before the pass closes",
    "Notes on photographing fog", "A week of braided rivers", "Waiting for moonrise",
]


# --------------------------------------------------------------------------- images

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ridge_profile(rng, width, base, amp, roughness=0.55):
    """Midpoint-displacement ridge line, returns list of y values of length width."""
    n = 1
    while n < width:
        n *= 2
    pts = [0.0] * (n + 1)
    pts[0], pts[n] = rng.uniform(-1, 1), rng.uniform(-1, 1)
    step, scale = n, 1.0
    while step > 1:
        half = step // 2
        for i in range(half, n, step):
            pts[i] = (pts[i - half] + pts[i + half]) / 2 + rng.uniform(-scale, scale)
        step, scale = half, scale * roughness
    m = max(abs(p) for p in pts) or 1
    return [base + amp * pts[int(x * n / width)] / m for x in range(width)]


def landscape_layers(seed, sky, land, w, h, fog):
    """Returns (sky_image, [(layer_rgba, depth)...]) so videos can scroll layers independently."""
    rng = random.Random(seed)
    sky_img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(sky_img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=lerp(sky[0], sky[1], y / h))
    # sun or moon
    r = int(h * rng.uniform(0.05, 0.09))
    cx, cy = int(w * rng.uniform(0.2, 0.8)), int(h * rng.uniform(0.18, 0.42))
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse([cx - r * 3, cy - r * 3, cx + r * 3, cy + r * 3], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(r))
    sky_img = Image.composite(Image.new("RGB", (w, h), (255, 246, 226)), sky_img, glow)
    ImageDraw.Draw(sky_img).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 248, 232))

    layers = []
    count = rng.randint(4, 6)
    for i in range(count):
        t = i / (count - 1)
        color = lerp(lerp(sky[0], land[0], 0.55), land[1], t)
        base = h * (0.42 + 0.42 * t)
        amp = h * (0.10 + 0.06 * rng.random()) * (1.1 - 0.5 * t)
        prof = ridge_profile(rng, w, base, amp)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon([(0, h)] + [(x, prof[x]) for x in range(w)] + [(w - 1, h)], fill=color + (255,))
        if fog and i < count - 1:
            band = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            fy = int(base + amp * 0.6)
            ImageDraw.Draw(band).rectangle([0, fy - h // 18, w, fy + h // 18], fill=sky[1] + (150,))
            layer = Image.alpha_composite(layer, band.filter(ImageFilter.GaussianBlur(h // 30)))
        layers.append((layer, t))
    return sky_img, layers


def render_landscape(seed, gallery, w, h, label):
    _, _, _, sky, land, fog = gallery
    sky_img, layers = landscape_layers(seed, sky, land, w, h, fog)
    img = sky_img.convert("RGBA")
    for layer, _ in layers:
        img = Image.alpha_composite(img, layer)
    img = img.convert("RGB")
    # small corner ID, handy when checking which asset a crawler picked up
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", max(12, h // 60))
    except OSError:
        font = ImageFont.load_default()
    d.text((w - 12, h - 10), label, fill=(255, 255, 255), font=font, anchor="rb")
    return img


def save_image(img, out_dir, stem):
    os.makedirs(out_dir, exist_ok=True)
    img.save(f"{out_dir}/{stem}.jpg", quality=84, optimize=True, progressive=True)


# --------------------------------------------------------------------------- videos

def has_encoder(name):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return name in out


def render_video(seed, gallery, out_dir, stem, label, seconds=6, fps=24, w=640, h=360):
    """Parallax pan across wide landscape layers, piped to ffmpeg as raw frames."""
    os.makedirs(out_dir, exist_ok=True)
    W = w * 2
    sky_img, layers = landscape_layers(seed, gallery[3], gallery[4], W, h, gallery[5])
    frames = seconds * fps
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
    except OSError:
        font = ImageFont.load_default()

    def frame(i):
        p = i / frames
        f = sky_img.crop((int(p * w * 0.1), 0, int(p * w * 0.1) + w, h)).convert("RGBA")
        for layer, depth in layers:
            off = int(p * w * (0.15 + 0.85 * depth))
            f = Image.alpha_composite(f, layer.crop((off, 0, off + w, h)))
        f = f.convert("RGB")
        ImageDraw.Draw(f).text((w - 8, h - 6), f"{label}  {i:03d}", fill=(255, 255, 255), font=font, anchor="rb")
        return f

    targets = [("mp4", ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-movflags", "+faststart"])]
    raw = b"".join(frame(i).tobytes() for i in range(frames))
    made = []
    for ext, args in targets:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", *args, f"{out_dir}/{stem}.{ext}"]
        subprocess.run(cmd, input=raw, check=True)
        made.append(ext)
    return made


# --------------------------------------------------------------------------- html

def e(s):
    return html.escape(s, quote=True)


def page(title, description, body, depth, og_image=None, extra_head="", scripts=""):
    p = "../" * depth
    og = f'<meta property="og:image" content="{p}{og_image}">' if og_image else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | {SITE_NAME}</title>
<meta name="description" content="{e(description)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
{og}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,700&family=Literata:ital,opsz,wght@0,7..72,400;1,7..72,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{p}assets/css/style.css">
<link rel="icon" href="{p}assets/favicon.svg" type="image/svg+xml">
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <a class="brand" href="{p}index.html">{SITE_NAME}</a>
  <nav aria-label="Main">
    <a href="{p}galleries/index.html">Galleries</a>
    <a href="{p}videos/index.html">Videos</a>
    <a href="{p}journal/index.html">Journal</a>
    <a href="{p}about.html">About</a>
  </nav>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <p>{SITE_NAME} is a test site with generated images and videos. Nothing here is a real photograph.</p>
  <p><a href="{p}contact.html">Contact</a> <a href="{p}sitemap.xml">Sitemap</a></p>
</footer>
{scripts}
</body>
</html>
"""


def picture(prefix, stem, alt, sizes=None, lazy=True):
    loading = ' loading="lazy" decoding="async"' if lazy else ""
    return f'<img src="{prefix}{stem}.jpg" width="1600" height="1067" alt="{e(alt)}"{loading}>'


def video_tag(prefix, stem, formats, title):
    return f"""<video controls preload="metadata" playsinline width="640" height="360" aria-label="{e(title)}">
  <source src="{prefix}{stem}.mp4#t=0.1" type="video/mp4">
  <a href="{prefix}{stem}.mp4">Download the video</a>
</video>"""


def write(out, rel, content):
    path = os.path.join(out, rel)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# --------------------------------------------------------------------------- build

def build(out, per_gallery, base_url):
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    here = os.path.dirname(os.path.abspath(__file__))
    shutil.copytree(os.path.join(here, "static"), os.path.join(out, "assets"))
    rng = random.Random(42)
    pages = []

    # photos
    photos = {}
    for gi, g in enumerate(GALLERIES):
        slug = g[0]
        photos[slug] = []
        for n in range(1, per_gallery + 1):
            stem = f"{slug}-{n:02d}"
            label = f"RFN-{gi + 1}-{n:02d}"
            print("image", stem)
            img = render_landscape(gi * 1000 + n, g, 1600, 1067, label)
            save_image(img, os.path.join(out, "media/photos", slug), stem)
            photos[slug].append({
                "stem": stem, "n": n, "label": label,
                "title": f"{g[1]}, frame {n}",
                "camera": rng.choice(CAMERAS), "lens": rng.choice(LENSES),
                "shutter": rng.choice(["1/60", "1/125", "1/250", "1/500", "2s", "15s"]),
                "aperture": rng.choice(["f/4", "f/5.6", "f/8", "f/11"]),
                "iso": rng.choice([64, 100, 200, 400, 1600, 3200]),
                "date": (date(2025, 1, 1) + timedelta(days=rng.randint(0, 600))).isoformat(),
            })

    # videos
    videos = []
    for vi, title in enumerate(VIDEO_TITLES):
        g = GALLERIES[vi % len(GALLERIES)]
        stem = f"clip-{vi + 1:02d}"
        print("video", stem)
        fmts = render_video(5000 + vi, g, os.path.join(out, "media/videos"), stem, f"RFN-V{vi + 1:02d}")
        videos.append({"stem": stem, "title": title, "gallery": g, "formats": fmts, "slug": f"clip-{vi + 1:02d}"})

    # home
    hero = photos[GALLERIES[2][0]][0]
    gal_links = "\n".join(
        f'<li><a href="galleries/{g[0]}.html"><img src="media/photos/{g[0]}/{photos[g[0]][0]["stem"]}.jpg" width="480" height="320" alt="" loading="lazy"><span>{e(g[1])}</span></a></li>'
        for g in GALLERIES)
    vid_links = "\n".join(
        f'<li><a href="videos/{v["slug"]}.html"><video src="media/videos/{v["stem"]}.mp4#t=0.1" preload="metadata" muted playsinline width="640" height="360" aria-hidden="true"></video><span>{e(v["title"])}</span></a></li>'
        for v in videos[:4])
    home = f"""
<section class="hero" style="background-image:url('media/photos/{GALLERIES[2][0]}/{hero["stem"]}.jpg')">
  <h1>Ridgelines, fog and first light</h1>
  <p>Landscape work from coasts, deserts and mountain passes, by {AUTHOR}.</p>
</section>
<section class="band">
  <h2>Galleries</h2>
  <ul class="tiles">{gal_links}</ul>
</section>
<section class="band">
  <h2>Recent videos</h2>
  <ul class="tiles wide">{vid_links}</ul>
  <p><a href="videos/index.html">All videos</a></p>
</section>
<section class="band feature">
  <h2>Featured frame</h2>
  <figure>{picture("media/photos/" + GALLERIES[0][0] + "/", photos[GALLERIES[0][0]][2]["stem"], photos[GALLERIES[0][0]][2]["title"])}
  <figcaption>{e(photos[GALLERIES[0][0]][2]["title"])}</figcaption></figure>
</section>"""
    write(out, "index.html", page("Home", "Landscape photography and short films from coasts, deserts and mountains.", home, 0,
                                  og_image=f"media/photos/{GALLERIES[2][0]}/{hero['stem']}.jpg"))
    pages.append("index.html")

    # galleries index + gallery pages + photo pages
    rows = ""
    for g in GALLERIES:
        strip = "".join(f'<img src="../media/photos/{g[0]}/{p["stem"]}.jpg" width="480" height="320" alt="" loading="lazy">'
                        for p in photos[g[0]][:4])
        rows += f'<li class="gallery-row"><a href="{g[0]}.html"><div class="strip">{strip}</div><h2>{e(g[1])}</h2><p>{e(g[2])} {len(photos[g[0]])} photographs.</p></a></li>\n'
    write(out, "galleries/index.html", page("Galleries", "All photo galleries.", f'<h1 class="page-title">Galleries</h1><ul class="gallery-list">{rows}</ul>', 1))
    pages.append("galleries/index.html")

    for g in GALLERIES:
        items = "".join(
            f'<li><a href="{g[0]}/{p["stem"]}.html"><img src="../media/photos/{g[0]}/{p["stem"]}.jpg" '
            f'width="1600" height="1067" alt="{e(p["title"])}" loading="lazy"></a></li>'
            for p in photos[g[0]])
        body = f'<h1 class="page-title">{e(g[1])}</h1><p class="lede">{e(g[2])}</p><ul class="grid">{items}</ul><p><a href="index.html">All galleries</a></p>'
        write(out, f"galleries/{g[0]}.html", page(g[1], g[2], body, 1, og_image=f"media/photos/{g[0]}/{photos[g[0]][0]['stem']}.jpg"))
        pages.append(f"galleries/{g[0]}.html")

        lst = photos[g[0]]
        for i, p in enumerate(lst):
            prev_ = f'<a rel="prev" href="{lst[i - 1]["stem"]}.html">Previous</a>' if i > 0 else "<span></span>"
            next_ = f'<a rel="next" href="{lst[i + 1]["stem"]}.html">Next</a>' if i < len(lst) - 1 else "<span></span>"
            pre = f"../../media/photos/{g[0]}/"
            body = f"""
<article class="photo">
  <figure>{picture(pre, p["stem"], p["title"], sizes="100vw", lazy=False)}</figure>
  <div class="photo-meta">
    <h1>{e(p["title"])}</h1>
    <dl>
      <dt>Gallery</dt><dd><a href="../{g[0]}.html">{e(g[1])}</a></dd>
      <dt>Camera</dt><dd>{p["camera"]}, {p["lens"]}</dd>
      <dt>Exposure</dt><dd>{p["shutter"]} at {p["aperture"]}, ISO {p["iso"]}</dd>
      <dt>Date</dt><dd><time datetime="{p["date"]}">{p["date"]}</time></dd>
      <dt>Asset ID</dt><dd>{p["label"]}</dd>
    </dl>
    <p><a href="{pre}{p["stem"]}.jpg" download>Download full size (JPEG)</a></p>
    <nav class="pager" aria-label="Photo">{prev_}{next_}</nav>
  </div>
</article>"""
            write(out, f"galleries/{g[0]}/{p['stem']}.html",
                  page(p["title"], f"{g[1]} photograph {p['n']}.", body, 2, og_image=f"media/photos/{g[0]}/{p['stem']}.jpg"))
            pages.append(f"galleries/{g[0]}/{p['stem']}.html")

    # videos
    cards = "".join(
        f'<li><a href="{v["slug"]}.html"><video src="../media/videos/{v["stem"]}.mp4#t=0.1" preload="metadata" muted playsinline width="640" height="360" aria-hidden="true"></video><span>{e(v["title"])}</span></a></li>'
        for v in videos)
    write(out, "videos/index.html", page("Videos", "Short landscape films.", f'<h1 class="page-title">Videos</h1><ul class="tiles wide">{cards}</ul>', 1))
    pages.append("videos/index.html")
    for i, v in enumerate(videos):
        others = "".join(f'<li><a href="{o["slug"]}.html">{e(o["title"])}</a></li>' for o in videos if o is not v)
        body = f"""
<article class="video-page">
  <h1>{e(v["title"])}</h1>
  {video_tag("../media/videos/", v["stem"], v["formats"], v["title"])}
  <p class="lede">A six-second parallax study from the {e(v["gallery"][1].lower())} series. Asset ID RFN-V{i + 1:02d}.</p>
  <h2>More videos</h2><ul class="plain">{others}</ul>
</article>"""
        extra = f'<meta property="og:video" content="../media/videos/{v["stem"]}.mp4">'
        write(out, f"videos/{v['slug']}.html", page(v["title"], f"Video: {v['title']}.", body, 1, extra_head=extra))
        pages.append(f"videos/{v['slug']}.html")

    # journal (mixes inline images, a JS lazy-loaded image and an embedded video)
    posts = []
    for j, title in enumerate(JOURNAL_TITLES):
        g = GALLERIES[j % len(GALLERIES)]
        pick = rng.sample(photos[g[0]], 3)
        paras = rng.sample(PARAGRAPHS, 5)
        v = videos[j % len(videos)]
        d_ = (date(2026, 3, 1) + timedelta(days=j * 23)).isoformat()
        slug = f"post-{j + 1:02d}"
        pre = f"../media/photos/{g[0]}/"
        body = f"""
<article class="post">
  <h1>{e(title)}</h1>
  <p class="date"><time datetime="{d_}">{d_}</time></p>
  <p>{paras[0]}</p>
  <figure>{picture(pre, pick[0]["stem"], pick[0]["title"])}<figcaption>{e(pick[0]["title"])}</figcaption></figure>
  <p>{paras[1]}</p>
  <p>{paras[2]}</p>
  <figure><img class="js-lazy" data-src="{pre}{pick[1]['stem']}.jpg" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" width="1600" height="1067" alt="{e(pick[1]['title'])}">
  <noscript><img src="{pre}{pick[1]['stem']}.jpg" alt="{e(pick[1]['title'])}"></noscript>
  <figcaption>{e(pick[1]['title'])}</figcaption></figure>
  <p>{paras[3]}</p>
  <figure>{video_tag("../media/videos/", v["stem"], v["formats"], v["title"])}<figcaption>{e(v["title"])}</figcaption></figure>
  <p>{paras[4]}</p>
  <div class="bg-figure" role="img" aria-label="{e(pick[2]['title'])}" style="background-image:url('{pre}{pick[2]['stem']}.jpg')"></div>
  <p><a href="index.html">All journal entries</a></p>
</article>"""
        write(out, f"journal/{slug}.html", page(title, paras[0][:150], body, 1,
                                                og_image=f"media/photos/{g[0]}/{pick[0]['stem']}.jpg",
                                                scripts='<script src="../assets/js/lazy.js" defer></script>'))
        pages.append(f"journal/{slug}.html")
        posts.append((slug, title, d_, f"{pre}{pick[0]['stem']}.jpg"))
    lst = "".join(f'<li><a href="{s}.html"><img src="{t}" width="480" height="320" alt="" loading="lazy"><span>{e(ti)}</span><time datetime="{d}">{d}</time></a></li>'
                  for s, ti, d, t in posts)
    write(out, "journal/index.html", page("Journal", "Field notes from recent trips.", f'<h1 class="page-title">Journal</h1><ul class="journal-list">{lst}</ul>', 1))
    pages.append("journal/index.html")

    # about / contact / 404
    about_img = photos[GALLERIES[3][0]][1]
    write(out, "about.html", page("About", "About this site.", f"""
<article class="post"><h1>About</h1>
<figure>{picture("media/photos/" + GALLERIES[3][0] + "/", about_img["stem"], about_img["title"])}</figure>
<p>{AUTHOR} is a fictional landscape photographer. Every image and video on this site was generated by a script, so the media is unique, free to reuse and safe for testing.</p>
<p>{PARAGRAPHS[3]}</p></article>""", 0))
    write(out, "contact.html", page("Contact", "Get in touch.", """
<article class="post"><h1>Contact</h1>
<p>For prints and licensing, write to <a href="mailto:hello@example.com">hello@example.com</a>.</p></article>""", 0))
    pages += ["about.html", "contact.html"]
    write(out, "404.html", page("Page not found", "Page not found.",
                                '<article class="post"><h1>Page not found</h1><p>The page you asked for is not here. Try the <a href="/">home page</a> or the galleries.</p></article>', 0))

    # crawl helpers
    open(os.path.join(out, ".nojekyll"), "w").close()
    base = (base_url or "https://USERNAME.github.io").rstrip("/")
    urls = "\n".join(f"  <url><loc>{base}/{p}</loc></url>" for p in pages)
    write(out, "sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n')
    write(out, "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    print(f"\nDone: {len(pages)} pages, {sum(len(v) for v in photos.values())} photos, {len(videos)} videos -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs")
    ap.add_argument("--images-per-gallery", type=int, default=8)
    ap.add_argument("--base-url", default="")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    build(a.out, a.images_per_gallery, a.base_url)
