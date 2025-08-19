#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto Concept Car Generator
- Every run: invents a high-end concept car with unique visual identity
- Even day => Sports car, Odd day => Luxury sedan (Europe/Paris date)
- Generates 3 realistic images via OpenAI Images API:
  01: front 3/4 (avant-diagonale)
  02: rear 3/4 (arrière)
  03: interior (cockpit OR driver's side from outside)
- Saves images to /images as AAAA-MM-JJ-<ModelName>-0X.jpg
- Creates an HTML article in /articles as AAAA-MM-JJ-<ModelName>.html
- Uses /templates/article_template.html if present; otherwise uses built-in template.
"""

import os
import re
import json
import random
from datetime import datetime
from pathlib import Path

# ---- Configuration ----
ROOT = Path(__file__).resolve().parents[1]          # project root (.. from /scripts/)
IMAGES_DIR = ROOT / "images"
ARTICLES_DIR = ROOT / "articles"
TEMPLATES_DIR = ROOT / "templates"
OPTIONAL_TEMPLATE = TEMPLATES_DIR / "article_template.html"

SITE_TITLE = "FuturaDrive"  # pour le breadcrumb si besoin
TIMEZONE = "Europe/Paris"   # heure locale pour le choix pair/impair et datation

# OpenAI
# Assure-toi d'avoir: export OPENAI_API_KEY="xxx"
OPENAI_MODEL_IMAGE = "gpt-image-1"  # modèle image courant
OPENAI_IMAGE_SIZE = "1792x1024"     # large (tu peux changer en "1024x1024")
OPENAI_IMAGE_FORMAT = "b64_json"    # on sauve ensuite en JPEG/PNG
IMAGE_EXT = ".jpg"

# ---- Lib pour timezone (Python 3.9+) ----
try:
    from zoneinfo import ZoneInfo  # standard lib (Py3.9+)
except Exception:
    ZoneInfo = None

# ---- Utilitaires ----
def today_paris():
    if ZoneInfo:
        return datetime.now(ZoneInfo(TIMEZONE))
    # fallback sans zoneinfo
    return datetime.utcnow()

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    return text

def ensure_dirs():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

def save_b64_image(b64_data: str, path: Path):
    import base64
    img_bytes = base64.b64decode(b64_data)
    path.write_bytes(img_bytes)

# ---- Nom et specs ----
SYLLABLES = [
    "Aely", "Orion", "Veyra", "Celest", "Hydra", "Aeon", "Kaly", "Nyra",
    "Solin", "Vestra", "Elios", "Ophir", "Zyra", "Lumen", "Icar", "Nexa",
    "Arion", "Eidos", "Nova", "Kaelis", "Astra", "Lyra", "Seraph", "Valk"
]

def invent_name(car_type: str) -> str:
    """Genère un nom de modèle unique, sans rappeler une marque existante."""
    core = "".join(random.sample(SYLLABLES, k=2))
    suffix = " One" if car_type == "sport" else " Lux"
    return f"{core}{suffix}"

def random_specs(car_type: str) -> dict:
    """Spécifications crédibles pour pile à combustible hydrogène."""
    if car_type == "sport":
        zero100 = round(random.uniform(2.6, 3.2), 1)
        vmax = random.randint(310, 340)
        power_hp = random.randint(750, 900)
        seats = 2
        tags = ["Supercar", "Hydrogène"]
    else:
        zero100 = round(random.uniform(3.8, 4.8), 1)
        vmax = random.randint(260, 300)
        power_hp = random.randint(500, 680)
        seats = 4
        tags = ["Berline", "Hydrogène"]

    autonomy = random.randint(700, 950)
    dimensions = {
        "length": round(random.uniform(4.75, 5.25), 2),
        "width": round(random.uniform(1.90, 2.02), 2),
        "height": round(random.uniform(1.23, 1.47), 2),
        "wheelbase": round(random.uniform(2.75, 3.05), 2),
    }
    return {
        "zero100": zero100,
        "vmax": vmax,
        "power_hp": power_hp,
        "autonomy": autonomy,
        "seats": seats,
        "tags": tags,
        "dimensions": dimensions
    }

# ---- Prompts d’images ----
def base_style_prompt(unique_hint: str) -> str:
    return (
        "Ultra-realistic high-resolution concept car photo, unique visual identity that DOES NOT resemble existing brands "
        "(no brand logos, no brand-identifiable grille), elegant futuristic surfacing, aerodynamic sculpture, crisp details, "
        "global illumination, photography-grade rendering, subtle reflections, premium materials, "
        f"signature light elements {unique_hint}."
    )

def prompt_front(car_type: str, brandless_name: str) -> str:
    angle = "front three-quarter view, dynamic angle"
    body = "low-slung hypercar proportions" if car_type == "sport" else "long luxury sedan proportions"
    unique_hint = "(distinctive LED signature, unique grille pattern, no badges)."
    backdrop = "modern minimal background, urban concrete wall with soft daylight"
    color = "metallic silver-blue paint with contrasting dark accents"
    wheels = "large turbine-inspired wheels"
    return (
        f"{base_style_prompt(unique_hint)}\n"
        f"Shot: {angle}; Body: {body}; Paint: {color}; Wheels: {wheels}; "
        f"Backdrop: {backdrop}. Vehicle name: {brandless_name}."
    )

def prompt_rear(car_type: str, brandless_name: str) -> str:
    angle = "rear three-quarter view, low angle"
    tail = "continuous light bar with sculpted diffuser" if car_type == "sport" else "elegant light bar, clean trunk line"
    unique_hint = "(unique taillight contour, no brand marks)."
    backdrop = "contemporary city backdrop, soft diffused light"
    return (
        f"{base_style_prompt(unique_hint)}\n"
        f"Shot: {angle}; Tail: {tail}; Backdrop: {backdrop}. Vehicle name: {brandless_name}."
    )

def prompt_interior(car_type: str, brandless_name: str) -> str:
    mode = random.choice(["cockpit close-up from driver's seat",
                          "interior seen from outside through the open driver door, left side"])
    materials = "vegan leather, basalt fiber inlays, brushed metal"
    ui = "wide AR HUD, curved panoramic display"
    return (
        f"High-end luxury interior, {mode}, {materials}, {ui}, minimal yet futuristic, "
        "natural daylight, photography look, no logos.\n"
        f"Vehicle name: {brandless_name}."
    )

# ---- OpenAI Images API ----
def openai_client():
    # Compatibilité avec openai>=1.0
    try:
        from openai import OpenAI
        return OpenAI()
    except Exception:
        # fallback pour anciens SDKs (non recommandé)
        import openai
        return openai

def generate_image_b64(prompt: str):
    client = openai_client()
    # Client moderne (OpenAI()) :
    if hasattr(client, "images"):
        result = client.images.generate(
            model=OPENAI_MODEL_IMAGE,
            prompt=prompt,
            size=OPENAI_IMAGE_SIZE,
            n=1,
            response_format=OPENAI_IMAGE_FORMAT,
        )
        # gpt-image-1: result.data[0].b64_json
        return result.data[0].b64_json
    # Fallback openai.images (v0.x)
    import openai as old
    resp = old.Image.create(
        prompt=prompt,
        n=1,
        size=OPENAI_IMAGE_SIZE,
        response_format="b64_json"
    )
    return resp["data"][0]["b64_json"]

# ---- HTML (template intégré, lightbox incluse) ----
DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ MODEL }} — Concept Car</title>
  <meta name="description" content="{{ MODEL }} : supercar/berline à pile à combustible hydrogène. 0–100 km/h en {{ ZERO100 }} s, {{ VMAX }} km/h, {{ AUTONOMY }} km d’autonomie." />
  <style>
    :root{
      --bg:#0f172a; --card:#0b1223; --text:#e5e7eb; --muted:#94a3b8;
      --accent:#22d3ee; --accent-2:#a78bfa; --ring:#38bdf8; --radius:18px;
      --shadow-lg:0 20px 40px rgba(0,0,0,.35);
    }
    *{box-sizing:border-box}
    html,body{height:100%}
    body{margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Inter,Arial,sans-serif; color:var(--text); background:linear-gradient(135deg,#0b1223, var(--bg));}
    a{color:var(--accent)}
    header{position:sticky; top:0; z-index:50; backdrop-filter:saturate(160%) blur(10px);
      background:linear-gradient(180deg, rgba(2,6,23,.78), rgba(2,6,23,.35)); border-bottom:1px solid rgba(148,163,184,.15)}
    .wrap{max-width:1100px; margin-inline:auto; padding:16px 20px}
    .row{display:flex; align-items:center; gap:10px; justify-content:space-between}
    .breadcrumb{display:flex; align-items:center; gap:8px; color:var(--muted); text-decoration:none}
    .breadcrumb:hover{color:var(--text)}
    .actions{display:flex; gap:8px}
    .btn{appearance:none; border:1px solid rgba(148,163,184,.18); color:var(--text); background:linear-gradient(180deg,#0b1223,#0f172a); padding:8px 12px; border-radius:12px; cursor:pointer; font-weight:500}
    .btn:hover{border-color:rgba(56,189,248,.45)}
    .btn:focus-visible{outline:none; box-shadow:0 0 0 3px var(--ring)}

    .hero{position:relative}
    .hero .imgwrap{position:relative; border-radius:22px; overflow:hidden; border:1px solid rgba(148,163,184,.15); box-shadow:var(--shadow-lg)}
    .hero img{width:100%; height:420px; object-fit:cover; display:block; background:#111; cursor:pointer;}
    .hero .overlay{
      position:absolute; inset:0;
      background:linear-gradient(180deg, transparent 20%, rgba(2,6,23,.65) 75%, rgba(2,6,23,.9) 100%);
      pointer-events:none;
    }
    .hero .title{position:absolute; left:22px; bottom:20px; right:22px; display:flex; flex-wrap:wrap; align-items:flex-end; gap:10px}
    h1{margin:0; font-size:clamp(24px,4.4vw,44px); letter-spacing:.2px}
    .badge{display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; background:rgba(34,211,238,.15); border:1px solid rgba(56,189,248,.45); font-weight:600; color:#e0fbff}

    .content{display:grid; grid-template-columns: 1.2fr .8fr; gap:22px; margin-top:24px}
    @media (max-width: 980px){ .content{grid-template-columns: 1fr} }

    .card{background:linear-gradient(135deg,#0b1223,var(--card)); border:1px solid rgba(148,163,184,.15); border-radius:var(--radius); padding:18px}
    .grid{display:grid; gap:12px}
    .specs{display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px}
    .spec{display:flex; align-items:center; justify-content:space-between; padding:12px 14px; border:1px solid rgba(148,163,184,.12); border-radius:14px; background:rgba(2,6,23,.35)}
    .muted{color:var(--muted)}

    .gallery{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:10px}
    .gallery img{width:100%; height:180px; object-fit:cover; border-radius:14px; border:1px solid rgba(148,163,184,.15); cursor:pointer;}

    .kpi{display:flex; align-items:center; gap:10px; padding:10px 12px; border:1px solid rgba(148,163,184,.12); border-radius:14px; background:rgba(2,6,23,.35)}
    .kpi strong{font-size:18px}

    .list{margin:0; padding-left:18px}
    .list li{margin:6px 0}

    @media print{
      *{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .actions{ display:none !important; }
      header, aside{ position: static !important; }
      .hero .imgwrap{ box-shadow: none !important; }
      .hero .overlay{ display:none !important; }
      body{ background:#fff !important; color:#111 !important; }
      .card{ background:#fff !important; border:1px solid #ddd !important; }
    }

    /* Lightbox */
    .lightbox{position:fixed; inset:0; background:rgba(0,0,0,.85); display:none; align-items:center; justify-content:center; z-index:9999}
    .lightbox img{max-width:90%; max-height:90%; border-radius:8px; box-shadow:0 10px 40px rgba(0,0,0,.6)}
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
        <p><strong>{{ MODEL }}</strong> est une {{ KIND_FR }} à hydrogène. Elle combine une pile à combustible de nouvelle génération avec une batterie tampon haute puissance pour des accélérations explosives, tout en ne rejetant que de la vapeur d’eau.</p>

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
              <li>Pile à combustible H<sub>2</sub>, env. 150 kW continus</li>
              <li>Batterie tampon Li-ion haute puissance (décharges brèves)</li>
              <li>Deux moteurs électriques (AWD, vectorisation de couple)</li>
              <li>Réservoirs H<sub>2</sub> 700 bar composite</li>
              <li>Ravitaillement H<sub>2</sub> ~3 min (station 700 bar)</li>
            </ul>
          </div>
          <div class="card">
            <h3>Châssis & Aéro</h3>
            <ul class="list">
              <li>Monocoque carbone-aluminium</li>
              <li>Suspension pilotée (Confort / Sport)</li>
              <li>Aérodynamique active (lame avant, aileron/volet)</li>
              <li>Freins carbo-céramique</li>
            </ul>
          </div>
          <div class="card">
            <h3>Intérieur & Finitions</h3>
            <ul class="list">
              <li>Cuir vegan premium, inserts en fibre de basalte</li>
              <li>Affichage tête haute AR + écran panoramique incurvé</li>
              <li>Système audio 3D immersif</li>
              <li>Assistant IA prédictif</li>
            </ul>
          </div>
          <div class="card">
            <h3>Assistances & Gadgets</h3>
            <ul class="list">
              <li>Aides L3, caméras 360°, vision nocturne</li>
              <li>Enregistreur 4K, clé smartphone, reconnaissance faciale</li>
              <li>Mises à jour OTA</li>
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
        <div class="card">
          <h3>Points forts</h3>
          <ul class="list">
            <li>Performances élevées sans émissions</li>
            <li>Design distinctif et matériaux durables</li>
            <li>Technologies immersives (AR, IA, audio 3D)</li>
          </ul>
        </div>
      </aside>
    </section>
  </main>

  <!-- Lightbox -->
  <div class="lightbox" id="lightbox">
    <img src="" alt="Aperçu" id="lightbox-img">
  </div>

  <script>
    document.getElementById('printBtn')?.addEventListener('click', () => window.print());
    document.getElementById('copyBtn')?.addEventListener('click', async () => {
      const header = document.querySelector('header')?.cloneNode(true);
      const main = document.querySelector('main')?.cloneNode(true);
      header?.querySelector('.actions')?.remove();
      main?.querySelectorAll('.overlay').forEach(el => el.remove());
      const docFrag = `<article>${header ? header.outerHTML : ''}${main ? main.outerHTML : ''}</article>`.trim();
      const plain = (() => {
        const tmp = document.createElement('div');
        tmp.innerHTML = docFrag;
        tmp.querySelectorAll('script, style, noscript').forEach(el => el.remove());
        return tmp.innerText.replace(/\\n{3,}/g, '\\n\\n').trim();
      })();
      try {
        if (navigator.clipboard && window.ClipboardItem) {
          const item = new ClipboardItem({
            'text/html': new Blob([docFrag], { type: 'text/html' }),
            'text/plain': new Blob([plain], { type: 'text/plain' })
          });
          await navigator.clipboard.write([item]);
        } else {
          await navigator.clipboard.writeText(plain);
        }
        const btn = document.getElementById('copyBtn');
        btn.textContent = 'Copié !';
        setTimeout(()=> btn.textContent = 'Copier', 1200);
      } catch (err){
        alert("Impossible de copier automatiquement.");
      }
    });

    // Lightbox
    const lb = document.getElementById('lightbox');
    const lbImg = document.getElementById('lightbox-img');
    document.querySelectorAll('.zoomable').forEach(img => {
      img.addEventListener('click', () => {
        lbImg.src = img.src;
        lb.classList.add('active');
      });
    });
    lb.addEventListener('click', () => {
      lb.classList.remove('active');
      lbImg.src = "";
    });
  </script>
</body>
</html>
"""

def render_template(context: dict) -> str:
    tpl = DEFAULT_TEMPLATE
    if OPTIONAL_TEMPLATE.is_file():
        tpl = OPTIONAL_TEMPLATE.read_text(encoding="utf-8")
    html = tpl
    for k, v in context.items():
        html = html.replace("{{ " + k + " }}", str(v))
    return html

# ---- Pipeline principal ----
def main():
    ensure_dirs()
    now = today_paris()
    day = now.day
    car_type = "sport" if day % 2 == 0 else "berline"
    kind_fr = "supercar" if car_type == "sport" else "berline de luxe"

    model_name = invent_name(car_type)
    model_slug = slugify(model_name)
    date_prefix = now.strftime("%Y-%m-%d")

    # Fichiers
    img01 = IMAGES_DIR / f"{date_prefix}-{model_slug}-01{IMAGE_EXT}"
    img02 = IMAGES_DIR / f"{date_prefix}-{model_slug}-02{IMAGE_EXT}"
    img03 = IMAGES_DIR / f"{date_prefix}-{model_slug}-03{IMAGE_EXT}"
    article_path = ARTICLES_DIR / f"{date_prefix}-{model_slug}.html"

    specs = random_specs(car_type)

    # Prompts
    p1 = prompt_front(car_type, model_name)
    p2 = prompt_rear(car_type, model_name)
    p3 = prompt_interior(car_type, model_name)

    print(f"[i] Génération images pour: {model_name} ({kind_fr})")
    # Image 01
    b64_1 = generate_image_b64(p1)
    save_b64_image(b64_1, img01)
    # Image 02
    b64_2 = generate_image_b64(p2)
    save_b64_image(b64_2, img02)
    # Image 03
    b64_3 = generate_image_b64(p3)
    save_b64_image(b64_3, img03)

    # Contexte HTML
    context = {
        "MODEL": model_name,
        "KIND_FR": kind_fr,
        "ZERO100": specs["zero100"],
        "VMAX": specs["vmax"],
        "POWER_HP": specs["power_hp"],
        "AUTONOMY": specs["autonomy"],
        "SEATS": specs["seats"],
        "DIM_LENGTH": specs["dimensions"]["length"],
        "DIM_WIDTH": specs["dimensions"]["width"],
        "DIM_HEIGHT": specs["dimensions"]["height"],
        "DIM_WB": specs["dimensions"]["wheelbase"],
        "IMG01": f"/images/{img01.name}",
        "IMG02": f"/images/{img02.name}",
        "IMG03": f"/images/{img03.name}",
    }

    html = render_template(context)
    article_path.write_text(html, encoding="utf-8")

    print(f"[✓] Article créé: {article_path.name}")
    print(f"[✓] Images: {img01.name}, {img02.name}, {img03.name}")

if __name__ == "__main__":
    # Petit contrôle: exige la clé API
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Erreur: OPENAI_API_KEY manquante. fais: export OPENAI_API_KEY='sk-...'")
    main()
