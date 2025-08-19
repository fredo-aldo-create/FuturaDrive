#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto Concept Car Generator (GitHub Actions friendly)

- Jour pair => supercar ; Jour impair => berline de luxe (date Europe/Paris)
- Génère 3 images via OpenAI Images API:
  01: avant 3/4 ; 02: arrière 3/4 ; 03: intérieur (cockpit / côté conducteur)
- Nomme les images: AAAA-MM-JJ-<slug>-01.jpg (02/03 idem) -> /images
- Crée l'article HTML: AAAA-MM-JJ-<slug>.html -> /articles (template intégré + lightbox)
- Met à jour /index.html : insère une carte entre <!-- FEED:start --> et <!-- FEED:end -->
  avec image 01, lien article, titre et méta (date, tag)
"""

import os, re, json, random, base64
from datetime import datetime
from pathlib import Path

# Dossiers
ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT / "images"
ARTICLES_DIR = ROOT / "articles"
TEMPLATES_DIR = ROOT / "templates"
INDEX_FILE = ROOT / "index.html"
OPTIONAL_TEMPLATE = TEMPLATES_DIR / "article_template.html"

TIMEZONE = "Europe/Paris"

# OpenAI
OPENAI_MODEL_IMAGE = "gpt-image-1"
OPENAI_IMAGE_SIZE = "1536x1024"
OPENAI_IMAGE_FORMAT = "b64_json"
IMAGE_EXT = ".png"

# ----- Timezone -----
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

def now_paris():
    if ZoneInfo:
        return datetime.now(ZoneInfo(TIMEZONE))
    return datetime.utcnow()  # fallback si zoneinfo indispo

# ----- Utils -----
def ensure_dirs():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    return text

def save_b64(path: Path, b64: str):
    path.write_bytes(base64.b64decode(b64))

# ----- Naming & specs -----
SYLLABLES = [
    "Aely","Orion","Veyra","Celest","Hydra","Aeon","Kaly","Nyra",
    "Solin","Vestra","Elios","Ophir","Zyra","Lumen","Icar","Nexa",
    "Arion","Eidos","Nova","Kaelis","Astra","Lyra","Seraph","Valk"
]

def invent_name(car_type: str) -> str:
    core = "".join(random.sample(SYLLABLES, k=2))
    suffix = " One" if car_type == "sport" else " Lux"
    return f"{core}{suffix}"

def random_specs(car_type: str) -> dict:
    if car_type == "sport":
        zero100 = round(random.uniform(2.6, 3.2), 1)
        vmax = random.randint(310, 340)
        power_hp = random.randint(750, 900)
        seats = 2
        tag = "Supercar"
    else:
        zero100 = round(random.uniform(3.8, 4.8), 1)
        vmax = random.randint(260, 300)
        power_hp = random.randint(500, 680)
        seats = 4
        tag = "Berline"
    autonomy = random.randint(700, 950)
    dims = {
        "length": round(random.uniform(4.75, 5.25), 2),
        "width": round(random.uniform(1.90, 2.02), 2),
        "height": round(random.uniform(1.23, 1.47), 2),
        "wheelbase": round(random.uniform(2.75, 3.05), 2),
    }
    return dict(zero100=zero100, vmax=vmax, power_hp=power_hp, autonomy=autonomy,
                seats=seats, tag=tag, dims=dims)

# ----- Prompts images (anti-lookalike) -----
def base_style(unique_hint: str) -> str:
    return (
        "Ultra-realistic photo of a high-end concept car with a UNIQUE visual identity that DOES NOT resemble existing brands "
        "(no badges, no brand-identifiable grille), futuristic clean surfacing, aerodynamic sculpture, premium materials, "
        "sharp details, photographic rendering, subtle reflections. " + unique_hint
    )



# ----- Couleurs & environnements -----
CAR_COLORS = [
    "metallic red", "pearl white", "deep midnight blue",
    "emerald green metallic", "champagne gold", "graphite black matte",
    "copper orange", "satin purple", "turquoise cyan",
    "silver-blue metallic"
]


ENVIRONMENTS = [
    "modern minimal urban setting in soft daylight",
    "futuristic city skyline at dusk",
    "coastal road at golden hour",
    "mountain pass with snowy peaks in background",
    "desert highway under bright sunlight",
    "forest road with misty atmosphere",
    "luxury villa driveway in sunny weather",
    "industrial port with containers and cranes",
    "night cityscape with neon reflections" 
]

def random_color():
    return random.choice(CAR_COLORS)

def random_env():
    return random.choice(ENVIRONMENTS)

def prompt_front(kind: str, name: str, paint: str, backdrop: str) -> str:
    body = "low-slung hypercar proportions" if kind == "sport" else "long luxury sedan proportions"
    return (
        base_style("distinctive LED signature; unique front graphics.")
        + f"\nShot: dynamic front three-quarter view; Body: {body}; "
          f"Backdrop: {backdrop}; "
          f"Paint: {paint}; Wheels: turbine-inspired; "
          f"Vehicle name: {name}."
    )

def prompt_rear(kind: str, name: str, paint: str, backdrop: str) -> str:
    tail = "sculpted diffuser with continuous light bar" if kind == "sport" else "elegant clean trunk line with light bar"
    return (
        base_style("bespoke taillight contour; no logos.")
        + f"\nShot: low-angle rear three-quarter view; Tail: {tail}; "
          f"Backdrop: {backdrop}; "
          f"Paint: {paint}; "
          f"Vehicle name: {name}."
    )

def prompt_interior(kind: str, name: str, paint: str) -> str:
    mode = random.choice([
        "cockpit close-up from driver's seat",
        "interior seen from outside through the open driver door, left side"
    ])
    return (
        f"High-end luxury interior with subtle accents matching the exterior paint ({paint}), "
        "vegan leather, basalt-fiber inlays, brushed metal, wide AR HUD, panoramic curved display, "
        f"{mode}, natural daylight, photo-real, no logos.\nVehicle name: {name}."
    )

# ----- OpenAI images -----
def openai_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except Exception:
        import openai
        return openai

def gen_image_b64(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI()
    print(f"[i] Image size = {OPENAI_IMAGE_SIZE}")   
    res = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=OPENAI_IMAGE_SIZE,
        n=1,
    )
    return res.data[0].b64_json



# ----- HTML template (intégré, lightbox incluse) -----
DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ MODEL }} — Concept Car</title>
  <meta name="description" content="{{ MODEL }} : concept à pile à combustible hydrogène. 0–100 km/h {{ ZERO100 }} s, Vmax {{ VMAX }} km/h, {{ AUTONOMY }} km d’autonomie." />
  <style>
    :root{ --bg:#0f172a; --card:#0b1223; --text:#e5e7eb; --muted:#94a3b8; --accent:#22d3ee; --accent-2:#a78bfa; --ring:#38bdf8; --radius:18px; --shadow-lg:0 20px 40px rgba(0,0,0,.35); }
    *{box-sizing:border-box} html,body{height:100%}
    body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Inter,Arial,sans-serif;color:var(--text);background:linear-gradient(135deg,#0b1223,var(--bg));}
    a{color:var(--accent)}
    header{position:sticky;top:0;z-index:50;backdrop-filter:saturate(160%) blur(10px);background:linear-gradient(180deg,rgba(2,6,23,.78),rgba(2,6,23,.35));border-bottom:1px solid rgba(148,163,184,.15)}
    .wrap{max-width:1100px;margin-inline:auto;padding:16px 20px}
    .row{display:flex;align-items:center;gap:10px;justify-content:space-between}
    .breadcrumb{display:flex;align-items:center;gap:8px;color:var(--muted);text-decoration:none}
    .breadcrumb:hover{color:var(--text)}
    .actions{display:flex;gap:8px}
    .btn{appearance:none;border:1px solid rgba(148,163,184,.18);color:var(--text);background:linear-gradient(180deg,#0b1223,#0f172a);padding:8px 12px;border-radius:12px;cursor:pointer;font-weight:500}
    .btn:hover{border-color:rgba(56,189,248,.45)} .btn:focus-visible{outline:none;box-shadow:0 0 0 3px var(--ring)}
    .hero{position:relative}
    .hero .imgwrap{position:relative;border-radius:22px;overflow:hidden;border:1px solid rgba(148,163,184,.15);box-shadow:var(--shadow-lg)}
    .hero img{width:100%;height:420px;object-fit:cover;display:block;background:#111;cursor:pointer;}
    .hero .overlay{position:absolute;inset:0;background:linear-gradient(180deg,transparent 20%,rgba(2,6,23,.65) 75%,rgba(2,6,23,.9) 100%);pointer-events:none;}
    .hero .title{position:absolute;left:22px;bottom:20px;right:22px;display:flex;flex-wrap:wrap;align-items:flex-end;gap:10px}
    h1{margin:0;font-size:clamp(24px,4.4vw,44px);letter-spacing:.2px}
    .badge{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;background:rgba(34,211,238,.15);border:1px solid rgba(56,189,248,.45);font-weight:600;color:#e0fbff}
    .content{display:grid;grid-template-columns:1.2fr .8fr;gap:22px;margin-top:24px}
    @media (max-width:980px){.content{grid-template-columns:1fr}}
    .card{background:linear-gradient(135deg,#0b1223,var(--card));border:1px solid rgba(148,163,184,.15);border-radius:var(--radius);padding:18px}
    .grid{display:grid;gap:12px}
    .specs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
    .spec{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border:1px solid rgba(148,163,184,.12);border-radius:14px;background:rgba(2,6,23,.35)}
    .muted{color:var(--muted)}
    .gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}
    .gallery img{width:100%;height:180px;object-fit:cover;border-radius:14px;border:1px solid rgba(148,163,184,.15);cursor:pointer;}
    .kpi{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid rgba(148,163,184,.12);border-radius:14px;background:rgba(2,6,23,.35)}
    .list{margin:0;padding-left:18px}.list li{margin:6px 0}
    @media print{*{-webkit-print-color-adjust:exact;print-color-adjust:exact}.actions{display:none!important}header,aside{position:static!important}.hero .imgwrap{box-shadow:none!important}.hero .overlay{display:none!important}body{background:#fff!important;color:#111!important}.card{background:#fff!important;border:1px solid #ddd!important}}
    .lightbox{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;align-items:center;justify-content:center;z-index:9999}
    .lightbox img{max-width:90%;max-height:90%;border-radius:8px;box-shadow:0 10px 40px rgba(0,0,0,.6)}
    .lightbox.active{display:flex}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <div class="row">
        <a class="breadcrumb" href="/index.html" aria-label="Retour à l'accueil">← Accueil</a>
        <div class="actions">
          <button class="btn" id="copyBtn" title="Copier la fiche">Copier</button>
          <button class="btn" id="printBtn" title="Imprimer">Imprimer</button>
        </div>
      </div>
    </div>
  </header>

  <main class="wrap">
    <section class="hero">
      <div class="imgwrap">
        <img src="{{ IMG01 }}" alt="{{ MODEL }} — vue avant" class="zoomable" />
        <div class="overlay"></div>
        <div class="title">
          <h1>{{ MODEL }}</h1>
          <span class="badge">⚡ Pile à combustible H<sub>2</sub></span>
          <span class="badge">🔋 {{ AUTONOMY }} km</span>
        </div>
      </div>
    </section>

    <section class="content">
      <article class="card">
        <h2>Aperçu</h2>
        <p><strong>{{ MODEL }}</strong> est une {{ KIND_FR }} à hydrogène. Elle associe pile à combustible et batterie tampon haute puissance pour des accélérations élevées, tout en ne rejetant que de la vapeur d’eau.</p>

        <h3 style="margin-top:18px">Performances clés</h3>
        <div class="specs">
          <div class="spec"><span class="muted">0–100 km/h</span><strong>{{ ZERO100 }} s</strong></div>
          <div class="spec"><span class="muted">Vitesse max</span><strong>{{ VMAX }} km/h</strong></div>
          <div class="spec"><span class="muted">Puissance système</span><strong>~{{ POWER_HP }} ch (est.)</strong></div>
          <div class="spec"><span class="muted">Autonomie (est.)</span><strong>{{ AUTONOMY }} km</strong></div>
        </div>

        <div class="grid" style="margin-top:16px">
          <div class="card">
            <h3>Groupe motopropulseur</h3>
            <ul class="list">
              <li>Pile à combustible H<sub>2</sub> ~150 kW continus</li>
              <li>Batterie tampon Li-ion haute puissance</li>
              <li>Deux moteurs électriques (AWD, vectorisation de couple)</li>
              <li>Réservoirs H<sub>2</sub> 700 bar</li>
              <li>Ravitaillement H<sub>2</sub> ~3 min</li>
            </ul>
          </div>
          <div class="card">
            <h3>Châssis & Aéro</h3>
            <ul class="list">
              <li>Monocoque carbone-aluminium</li>
              <li>Suspension pilotée</li>
              <li>Aérodynamique active</li>
              <li>Freins carbo-céramique</li>
            </ul>
          </div>
          <div class="card">
            <h3>Intérieur & Finitions</h3>
            <ul class="list">
              <li>Cuir vegan premium, fibre de basalte</li>
              <li>AR HUD + écran panoramique incurvé</li>
              <li>Audio 3D immersif</li>
              <li>Assistant IA prédictif</li>
            </ul>
          </div>
          <div class="card">
            <h3>Assistances & Gadgets</h3>
            <ul class="list">
              <li>Aides L3, caméras 360°, vision nocturne</li>
              <li>DVR 4K, clé smartphone, reconnaissance faciale</li>
              <li>OTA</li>
            </ul>
          </div>
        </div>

        <h3 style="margin-top:18px">Galerie</h3>
        <div class="gallery">
          <img src="{{ IMG02 }}" alt="{{ MODEL }} — vue arrière" class="zoomable" />
          <img src="{{ IMG03 }}" alt="{{ MODEL }} — intérieur" class="zoomable" />
        </div>
      </article>

      <aside>
        <div class="kpi" aria-label="Sièges">
          <div>🪑</div><div><div class="muted">Places</div><strong>{{ SEATS }}</strong></div>
        </div>
        <div class="kpi" aria-label="Transmission">
          <div>⚙️</div><div><div class="muted">Transmission</div><strong>Intégrale (AWD)</strong></div>
        </div>
        <div class="kpi" aria-label="Émissions">
          <div>💨</div><div><div class="muted">Émissions</div><strong>Vapeur d’eau uniquement</strong></div>
        </div>
        <div class="card">
          <h3>Dimensions (estim.)</h3>
          <ul class="list">
            <li>Longueur : {{ DIM_LENGTH }} m</li>
            <li>Largeur : {{ DIM_WIDTH }} m</li>
            <li>Hauteur : {{ DIM_HEIGHT }} m</li>
            <li>Empattement : {{ DIM_WB }} m</li>
          </ul>
        </div>
      </aside>
    </section>
  </main>

  <div class="lightbox" id="lightbox"><img src="" alt="Aperçu" id="lightbox-img"></div>

  <script>
    document.getElementById('printBtn')?.addEventListener('click', () => window.print());
    document.getElementById('copyBtn')?.addEventListener('click', async () => {
      const header = document.querySelector('header')?.cloneNode(true);
      const main = document.querySelector('main')?.cloneNode(true);
      header?.querySelector('.actions')?.remove();
      main?.querySelectorAll('.overlay').forEach(el => el.remove());
      const docFrag = `<article>${header?header.outerHTML:""}${main?main.outerHTML:""}</article>`.trim();
      const tmp = document.createElement('div'); tmp.innerHTML = docFrag;
      tmp.querySelectorAll('script,style,noscript').forEach(el=>el.remove());
      const plain = tmp.innerText.replace(/\\n{3,}/g,'\\n\\n').trim();
      try{
        if(navigator.clipboard && window.ClipboardItem){
          const item = new ClipboardItem({'text/html': new Blob([docFrag],{type:'text/html'}), 'text/plain': new Blob([plain],{type:'text/plain'})});
          await navigator.clipboard.write([item]);
        }else{ await navigator.clipboard.writeText(plain); }
        const btn = document.getElementById('copyBtn'); btn.textContent='Copié !'; setTimeout(()=>btn.textContent='Copier',1200);
      }catch(e){ alert('Impossible de copier automatiquement.'); }
    });

    // Lightbox
    const lb = document.getElementById('lightbox'), lbImg = document.getElementById('lightbox-img');
    document.querySelectorAll('.zoomable').forEach(img=>{
      img.addEventListener('click',()=>{ lbImg.src = img.src; lb.classList.add('active'); });
    });
    lb.addEventListener('click',()=>{ lb.classList.remove('active'); lbImg.src=""; });
  </script>
</body>
</html>
"""

def render(tpl: str, ctx: dict) -> str:
    out = tpl
    for k, v in ctx.items():
        out = out.replace("{{ " + k + " }}", str(v))
    return out

# ----- index.html FEED insertion -----
FR_MONTHS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]

def format_date_fr(dt: datetime) -> str:
    return f"{dt.day} {FR_MONTHS[dt.month-1]} {dt.year}"

def make_card_block(article_rel: str, img_rel: str, title: str, meta_tag: str, dt: datetime) -> str:
    date_str = format_date_fr(dt)
    return f"""
      <article class="card">
        <a class="thumb" href="{article_rel}" aria-label="Lire : {title}">
          <img src="{img_rel}" alt="{title}">
          <span class="badge">Hydrogène</span>
        </a>
        <div class="card-body">
          <h2 class="title">{title}</h2>
          <p class="excerpt">Concept à pile à combustible : 0–100 en quelques secondes, autonomie longue, design unique.</p>
          <div class="meta">
            <span>{date_str}</span><span>•</span><span>{meta_tag}</span>
          </div>
          <a class="link" href="{article_rel}">Lire</a>
        </div>
      </article>
    """.rstrip()

def insert_card_into_index(index_path: Path, card_html: str):
    html = index_path.read_text(encoding="utf-8")
    start = html.find("<!-- FEED:start -->")
    end = html.find("<!-- FEED:end -->")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("Marqueurs FEED introuvables dans index.html")
    
    # on met la nouvelle carte juste après <!-- FEED:start -->
    insertion_point = start + len("<!-- FEED:start -->")
    new_html = html[:insertion_point] + "\n      " + card_html + html[insertion_point:]
    index_path.write_text(new_html, encoding="utf-8")


# ----- Main -----
def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY manquante")

    ensure_dirs()
    now = now_paris()
    day = now.day
    car_type = "sport" if day % 2 == 0 else "berline"
    kind_fr = "supercar" if car_type == "sport" else "berline de luxe"

    # Nom + fichiers
    model_name = invent_name(car_type)
    slug = slugify(model_name)
    date_prefix = now.strftime("%Y-%m-%d")
    img01 = IMAGES_DIR / f"{date_prefix}-{slug}-01{IMAGE_EXT}"
    img02 = IMAGES_DIR / f"{date_prefix}-{slug}-02{IMAGE_EXT}"
    img03 = IMAGES_DIR / f"{date_prefix}-{slug}-03{IMAGE_EXT}"
    article = ARTICLES_DIR / f"{date_prefix}-{slug}.html"

    specs = random_specs(car_type)

    # Prompts & images (une seule couleur + un seul décor pour les 3 vues)
    paint = random.choice(CAR_COLORS)
    backdrop = random.choice(ENVIRONMENTS)
    
    p1 = prompt_front(car_type, model_name, paint, backdrop)
    p2 = prompt_rear(car_type, model_name, paint, backdrop)
    p3 = prompt_interior(car_type, model_name, paint)

    b64_1 = gen_image_b64(p1)
    save_b64(img01, b64_1)
    b64_2 = gen_image_b64(p2)
    save_b64(img02, b64_2)
    b64_3 = gen_image_b64(p3)
    save_b64(img03, b64_3)

    # Rendu HTML
    tpl = OPTIONAL_TEMPLATE.read_text(encoding="utf-8") if OPTIONAL_TEMPLATE.exists() else DEFAULT_TEMPLATE
    ctx = {
        "MODEL": model_name,
        "KIND_FR": kind_fr,
        "ZERO100": specs["zero100"],
        "VMAX": specs["vmax"],
        "POWER_HP": specs["power_hp"],
        "AUTONOMY": specs["autonomy"],
        "SEATS": specs["seats"],
        "DIM_LENGTH": specs["dims"]["length"],
        "DIM_WIDTH": specs["dims"]["width"],
        "DIM_HEIGHT": specs["dims"]["height"],
        "DIM_WB": specs["dims"]["wheelbase"],
        "IMG01": f"/images/{img01.name}",
        "IMG02": f"/images/{img02.name}",
        "IMG03": f"/images/{img03.name}",
    }
    html = render(tpl, ctx)
    article.write_text(html, encoding="utf-8")

    # Carte pour index.html
    card = make_card_block(
        article_rel=f"/articles/{article.name}",
        img_rel=f"/images/{img01.name}",
        title=f"{model_name} — Concept Car",
        meta_tag=specs["tag"],
        dt=now
    )
    if INDEX_FILE.exists():
        insert_card_into_index(INDEX_FILE, card)
    else:
        print("[!] index.html introuvable — carte non insérée.")

    print(f"[✓] Article: {article}")
    print(f"[✓] Images: {img01.name}, {img02.name}, {img03.name}")

if __name__ == "__main__":
    main()
