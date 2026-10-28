"""Builds BloodBridge_Pitch.pptx - a 6-slide hackathon deck.

All visuals are native PowerPoint shapes (flowcharts, chat mockup, architecture
diagram) plus a generated blood-drop logo, so the deck stays fully editable.
Run:  python make_ppt.py   ->  ../BloodBridge_Pitch.pptx
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

LIVE_URL = "https://bloodbridge-app.riteshnethi-art.workers.dev"

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.abspath(os.path.join(HERE, "..", "BloodBridge_Pitch.pptx"))
TOTAL_SLIDES = 7

# ---------------------------------------------------------------- brand
BRAND = RGBColor(0xC8, 0x1E, 0x1E)      # #C81E1E
BRAND_SOFT = RGBColor(0xFB, 0xE9, 0xE9)  # light red tint
DARK = RGBColor(0x1C, 0x19, 0x17)       # stone-900
GRAY = RGBColor(0x57, 0x53, 0x4E)       # stone-600
LIGHT = RGBColor(0xFA, 0xFA, 0xF9)      # stone-50
BORDER = RGBColor(0xE7, 0xE5, 0xE4)     # stone-200
GREEN = RGBColor(0x15, 0x80, 0x3D)
GREEN_SOFT = RGBColor(0xEC, 0xFC, 0xF3)
AMBER = RGBColor(0xB4, 0x53, 0x09)
AMBER_SOFT = RGBColor(0xFE, 0xF3, 0xC7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Calibri"

SLIDE_W, SLIDE_H = 13.333, 7.5


# ---------------------------------------------------------------- logo
def make_drop(path: str) -> None:
    """Draws a brand-red blood drop with a white cross, anti-aliased."""
    S = 4
    W = 256 * S
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy, r = W // 2, int(W * 0.62), int(W * 0.32)
    tip = (cx, int(W * 0.12))

    def on_circle(deg: float) -> tuple[float, float]:
        a = math.radians(deg)
        return (cx + r * math.cos(a), cy - r * math.sin(a))

    def quad(p0, p1, p2, steps=28):
        return [(round((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]),
                 round((1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]))
                for t in (i / steps for i in range(steps + 1))]

    left_sh, right_sh = on_circle(200), on_circle(340)
    pts = [tip]
    pts += quad(tip, (cx - 0.74 * r, cy - 0.74 * r), left_sh)[1:]
    pts += [on_circle(deg) for deg in range(200, 341, 5)]
    pts += quad(right_sh, (cx + 0.74 * r, cy - 0.74 * r), tip)[1:-1]
    d.polygon(pts, fill=(200, 30, 30, 255))
    # white medical cross inside the bulb
    arm, thick = int(0.19 * W), int(0.05 * W)
    d.rounded_rectangle((cx - thick, cy - arm, cx + thick, cy + arm),
                        radius=thick // 2, fill=(255, 255, 255, 235))
    d.rounded_rectangle((cx - arm, cy - thick, cx + arm, cy + thick),
                        radius=thick // 2, fill=(255, 255, 255, 235))
    # soft highlight
    d.ellipse((cx - 0.62 * r, cy - 0.60 * r, cx - 0.34 * r, cy - 0.32 * r),
              fill=(255, 255, 255, 70))
    img = img.resize((256, 256), Image.LANCZOS)
    img.save(path)


# ---------------------------------------------------------------- helpers
def blank(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill=None, line=None, line_w=1.0,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=None):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    sh.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = radius
        except Exception:
            pass
    return sh


def write(target, paras, anchor=MSO_ANCHOR.MIDDLE, m=(0.06, 0.06, 0.04, 0.04)):
    """paras: list of (runs, align, space_after) where runs = list of
    (text, size, bold, color) tuples."""
    tf = target.text_frame if hasattr(target, "text_frame") else target
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left, tf.margin_right = Inches(m[0]), Inches(m[1])
    tf.margin_top, tf.margin_bottom = Inches(m[2]), Inches(m[3])
    for i, (runs, align, space) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        for text, size, bold, color in runs:
            r = p.add_run()
            r.text = text
            r.font.name = FONT
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
    return tf


def textbox(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    return write(tb, paras, anchor=anchor, m=(0, 0, 0, 0))


def bullets(slide, x, y, w, h, items, size=12.5, gap=8, color=DARK, lead_color=None):
    """items: str or (lead, rest) tuples. Renders '•  lead: rest' paragraphs."""
    paras = []
    for it in items:
        lead, rest = it if isinstance(it, tuple) else ("", it)
        runs = [("\u2022  ", size, True, BRAND)]
        if lead:
            runs.append((lead + ": ", size, True, lead_color or DARK))
        runs.append((rest, size, False, color))
        paras.append((runs, PP_ALIGN.LEFT, gap))
    return textbox(slide, x, y, w, h, paras)


def arrow(slide, x1, y1, x2, y2, color=GRAY, w=1.75):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                      Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conn.line.color.rgb = color
    conn.line.width = Pt(w)
    conn.shadow.inherit = False
    ln = conn.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:tailEnd"),
                             {"type": "triangle", "w": "med", "len": "med"}))
    return conn


def header(slide, kicker, title):
    textbox(slide, 0.44, 0.32, 12.45, 0.35,
            [([(kicker.upper(), 12, True, BRAND)], PP_ALIGN.LEFT, 0)])
    textbox(slide, 0.44, 0.62, 12.45, 0.62,
            [([(title, 28, True, DARK)], PP_ALIGN.LEFT, 0)])
    rect(slide, 0.47, 1.32, 1.35, 0.045, fill=BRAND, shape=MSO_SHAPE.RECTANGLE)


def footer(slide, n):
    textbox(slide, 0.44, 7.08, 9.0, 0.3,
            [([("BloodBridge - AI-assisted blood donor discovery  \u00b7  LIVE: " + LIVE_URL, 9, False, GRAY)],
              PP_ALIGN.LEFT, 0)])
    textbox(slide, 12.0, 7.08, 0.9, 0.3,
            [([(f"{n} / {TOTAL_SLIDES}", 9, False, GRAY)], PP_ALIGN.RIGHT, 0)])


def node(slide, x, y, w, h, num, title, sub, fill=WHITE, line=BORDER,
         title_color=DARK, badge=BRAND):
    card = rect(slide, x, y, w, h, fill=fill, line=line, line_w=1.25, radius=0.10)
    card.text_frame.word_wrap = True
    badge_sh = rect(slide, x - 0.13, y - 0.13, 0.36, 0.36, fill=badge, shape=MSO_SHAPE.OVAL)
    write(badge_sh, [([(str(num), 13, True, WHITE)], PP_ALIGN.CENTER, 0)])
    write(card, [
        ([(title, 12.5, True, title_color)], PP_ALIGN.CENTER, 3),
        ([(sub, 9.5, False, GRAY)], PP_ALIGN.CENTER, 0),
    ], anchor=MSO_ANCHOR.MIDDLE, m=(0.08, 0.08, 0.02, 0.02))
    return card


def crop_top(src, dst, h_over_w):
    """Crop a screenshot from the top so its height/width ratio ≈ h_over_w."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    cut = int(min(h, w * h_over_w))
    img = img.crop((0, 0, w, cut))
    img.save(dst, quality=92)
    return dst


# ---------------------------------------------------------------- build
def build():
    os.makedirs(ASSETS, exist_ok=True)
    drop_png = os.path.join(ASSETS, "drop.png")
    if not os.path.exists(drop_png):
        make_drop(drop_png)

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)

    # live-site assets (screen captures + QR), cropped for consistent cards
    shots = {}
    for name, ratio in (("shot_landing", 0.95), ("shot_assistant_gate", 0.70),
                        ("shot_matches", 1.05)):
        src = os.path.join(ASSETS, name + ".jpg")
        if os.path.exists(src):
            dst = os.path.join(ASSETS, name + "_card.jpg")
            crop_top(src, dst, ratio)
            shots[name] = dst
    qr_png = os.path.join(ASSETS, "live_qr.png")

    # ================================================== SLIDE 1 - title
    s = blank(prs)
    rect(s, 0, 0, SLIDE_W, SLIDE_H, fill=LIGHT, shape=MSO_SHAPE.RECTANGLE)
    rect(s, 0, 0, SLIDE_W, 0.16, fill=BRAND, shape=MSO_SHAPE.RECTANGLE)
    s.shapes.add_picture(drop_png, Inches(5.97), Inches(1.67), width=Inches(1.4))
    textbox(s, 1.0, 3.13, 11.33, 1.0,
            [([("BloodBridge", 52, True, DARK)], PP_ALIGN.CENTER, 0)])
    textbox(s, 1.0, 4.13, 11.33, 0.5,
            [([("AI-assisted blood donor discovery, matching and community engagement",
                19, False, GRAY)], PP_ALIGN.CENTER, 0)])
    textbox(s, 1.0, 4.73, 11.33, 0.5,
            [([("\u201cFinding a donor should never be the emergency.\u201d",
                16, True, BRAND)], PP_ALIGN.CENTER, 0)])
    live_badge = rect(s, 4.47, 5.42, 4.4, 0.44, fill=GREEN_SOFT, line=GREEN, line_w=1.25)
    write(live_badge, [([("\u25cf  LIVE NOW  -  it works in production", 12, True, GREEN)],
                        PP_ALIGN.CENTER, 0)])
    band = rect(s, 0, 6.72, SLIDE_W, 0.78, fill=BRAND, shape=MSO_SHAPE.RECTANGLE)
    write(band, [([("Supports preliminary donor discovery only - never medical advice, "
                    "never a guarantee of donors or blood availability.", 12.5, True, WHITE)],
                  PP_ALIGN.CENTER, 0)])

    # ================================================== SLIDE 2 - problem / solution
    s = blank(prs)
    header(s, "Why BloodBridge exists", "The problem - and what we built")
    footer(s, 2)
    cy, chh = 1.72, 5.1
    # problem card
    c1 = rect(s, 0.44, cy, 6.0, chh, fill=WHITE, line=BORDER, line_w=1.25, radius=0.06)
    h1 = rect(s, 0.44, cy, 6.0, 0.6, fill=DARK, radius=0.06)
    write(h1, [([("THE PROBLEM TODAY", 14, True, WHITE)], PP_ALIGN.LEFT, 0)],
          m=(0.25, 0.1, 0, 0))
    bullets(s, 0.75, cy + 0.85, 5.45, chh - 1.0, [
        "Emergencies are manual: phone trees, WhatsApp groups and social-media "
        "scrambles to find a compatible donor in time",
        "Requests lose structure - group, city, hospital, units and deadline "
        "live in one messy thread",
        "Nobody tracks who was asked, who accepted, or what happened next",
        "Donor phone numbers and addresses get forwarded around and leaked",
        "Existing tools are ad-heavy, city-limited, or stop at a directory list",
    ], size=12.5, gap=10)
    # solution card
    c2 = rect(s, 6.89, cy, 6.0, chh, fill=WHITE, line=BRAND, line_w=1.5, radius=0.06)
    h2 = rect(s, 6.89, cy, 6.0, 0.6, fill=BRAND, radius=0.06)
    write(h2, [([("WHAT BLOODBRIDGE DOES", 14, True, WHITE)], PP_ALIGN.LEFT, 0)],
          m=(0.25, 0.1, 0, 0))
    bullets(s, 7.2, cy + 0.85, 5.45, chh - 1.0, [
        ("Conversational intake", "the Bridge Assistant turns a free-text plea into a "
         "structured, confirmed request in minutes"),
        ("Compatibility engine", "all 8 blood groups, who-can-give-whom, tested "
         "server-side"),
        ("Location matching", "ranks nearby available donors by real haversine "
         "distance - never invented numbers"),
        ("Consent-gated contact", "donor phones are never public; contact opens only "
         "after a donor accepts"),
        ("Community engine", "rewards and referrals keep donors engaged - without "
         "cash or donation-tied incentives"),
    ], size=12.5, gap=10)

    # ================================================== SLIDE 3 - workflow
    s = blank(prs)
    header(s, "How it works", "From \u201cwe need O- now\u201d to a ranked donor list")
    footer(s, 3)
    steps = [
        ("Request created", "Assistant intake: slots filled, summary confirmed"),
        ("Compatibility filter", "All 8 groups - who can give to whom"),
        ("Location ranking", "Haversine distance + availability + recency"),
        ("Consent-gated contact", "Donor accepts, then contact is shared"),
        ("Donation at hospital", "Fulfillment happens offline, between humans"),
    ]
    nx, nw, ngap, ny, nh = 0.44, 2.29, 0.25, 2.35, 1.62
    for i, (t, sub) in enumerate(steps):
        x = nx + i * (nw + ngap)
        fill = BRAND_SOFT if i in (0, 4) else WHITE
        node(s, x, ny, nw, nh, i + 1, t, sub, fill=fill,
             title_color=BRAND if i in (0, 4) else DARK)
        if i < len(steps) - 1:
            arrow(s, x + nw + 0.02, ny + nh / 2, x + nw + ngap - 0.02, ny + nh / 2)
    banner = rect(s, 0.44, 4.42, 12.45, 0.72, fill=BRAND_SOFT, line=BRAND, line_w=1.25)
    write(banner, [([("Safety gate: ", 12.5, True, BRAND),
                     ("BloodBridge supports discovery only - it never guarantees donors, "
                      "never gives medical advice, and never claims a request was fulfilled.",
                      12.5, False, DARK)], PP_ALIGN.CENTER, 0)])
    proofs = [("8", "blood groups covered", "full who-can-give-whom compatibility matrix"),
              ("<1 min", "from plea to ranked list", "one free-text message in, ranked donors out"),
              ("0", "donor numbers exposed", "contact opens only after a donor accepts")]
    pw, pgap = 3.95, 0.3
    for i, (big, lead, sub) in enumerate(proofs):
        x = 0.44 + i * (pw + pgap)
        card = rect(s, x, 5.42, pw, 1.28, fill=WHITE, line=BORDER, line_w=1.25)
        write(card, [
            ([(big, 24, True, GREEN), ("   " + lead, 11.5, True, DARK)],
             PP_ALIGN.LEFT, 2),
            ([(sub, 10, False, GRAY)],
             PP_ALIGN.LEFT, 0),
        ], m=(0.18, 0.12, 0.06, 0.06))

    # ================================================== SLIDE 4 - assistant
    s = blank(prs)
    header(s, "Product spotlight", "Bridge Assistant - intake that actually completes")
    footer(s, 4)
    # phone-style chat card
    cx0, cy0, cw0, ch0 = 0.55, 1.66, 5.35, 5.22
    rect(s, cx0, cy0, cw0, ch0, fill=WHITE, line=BORDER, line_w=1.5, radius=0.05)
    hdr = rect(s, cx0, cy0, cw0, 0.46, fill=BRAND, radius=0.05)
    write(hdr, [([("Bridge Assistant", 12, True, WHITE),
                 ("      demo mode (deterministic)", 10, False, WHITE)],
                PP_ALIGN.LEFT, 0)], m=(0.2, 0.1, 0, 0))
    body_top = cy0 + 0.58
    yy = body_top + 0.08

    def bubble(y, side, text, w, h, fill, line, bold=False, size=9.5):
        if side == "L":
            x = cx0 + 0.18
        else:
            x = cx0 + cw0 - 0.18 - w
        b = rect(s, x, y, w, h, fill=fill, line=line, line_w=1.0, radius=0.28)
        write(b, [([(text, size, bold, DARK)], PP_ALIGN.LEFT, 0)],
              m=(0.1, 0.1, 0.02, 0.02))
        return y + h + 0.07

    yy = bubble(yy, "L", "Hello! I'm Bridge Assistant. Which blood group is needed?",
                3.45, 0.46, LIGHT, BORDER)
    yy = bubble(yy, "R", "I need O negative blood in Pune urgently",
                3.3, 0.46, BRAND_SOFT, BRAND)
    yy = bubble(yy, "L", "Great - blood group, city, urgency noted. Which hospital "
                 "is it for?", 3.9, 0.58, LIGHT, BORDER)
    div = textbox(s, cx0 + 0.2, yy + 0.0, cw0 - 0.4, 0.24,
                  [([("\u2026 guided steps: hospital \u00b7 units \u00b7 deadline \u00b7 "
                      "name \u00b7 contact \u2026", 9, False, GRAY)], PP_ALIGN.CENTER, 0)])
    yy += 0.30
    yy = bubble(yy, "L", "Here's your request summary:\nO- \u00b7 Pune \u00b7 Demo Hospital "
                "\u00b7 2 units \u00b7 urgent \u00b7 tomorrow 9am\nShall I submit?",
                4.35, 0.86, LIGHT, BORDER)
    yy = bubble(yy, "R", "confirm", 1.25, 0.32, GREEN_SOFT, GREEN)
    yy = bubble(yy, "L", "Done! Request BB-6D4006E5 submitted - finding compatible "
                "donors near Pune.", 4.35, 0.56, GREEN_SOFT, GREEN)
    gate = rect(s, cx0 + 0.18, cy0 + ch0 - 0.52, cw0 - 0.36, 0.4,
                fill=AMBER_SOFT, line=AMBER, line_w=1.0)
    write(gate, [([("Nothing submits without explicit user confirmation", 9.5, True, AMBER)],
                  PP_ALIGN.CENTER, 0)])
    # right column
    bullets(s, 6.35, 1.9, 6.5, 4.9, [
        ("Slot-filling state machine", "10 fields with optional skips - it asks one "
         "clear question at a time and never loses progress to FAQ detours"),
        ("Understands rich messages", "\u201cO negative in Pune urgently\u201d fills "
         "blood group, city and urgency in one turn"),
        ("Explicit confirmation gate", "a full summary with per-field edit commands; "
         "submission only on approval"),
        ("Two modes", "deterministic demo parser always works; optional Gemini "
         "extraction is re-validated server-side and falls back silently"),
        ("Channel-ready", "the same engine answers over WhatsApp Business Cloud API "
         "when configured - until then it is clearly labeled Demo Mode"),
    ], size=12.5, gap=11)

    # ================================================== slide 5 - live product walkthrough
    s = blank(prs)
    header(s, "Live now - not on localhost", "The real product, running in production today")
    footer(s, 5)
    cols = [
        ("shot_landing", "Landing & onboarding",
         "Compatibility table, safety notice and a 4-step tour - a stranger can act in 60 seconds"),
        ("shot_assistant_gate", "Assistant confirmation gate",
         "Full structured summary with per-field edit commands - nothing submits without explicit approval"),
        ("shot_matches", "Ranked matches, explained",
         "Score, distance, availability and a per-donor explanation - contact stays consent-gated"),
    ]
    cw, cgap, cy2, ch2 = 3.95, 0.3, 1.66, 4.72
    img_w = cw - 0.12
    cap_h = 0.92
    ratios = {"shot_landing": 0.95, "shot_assistant_gate": 0.70, "shot_matches": 1.05}
    for i, (key, cap_title, cap_sub) in enumerate(cols):
        x = 0.44 + i * (cw + cgap)
        card = rect(s, x, cy2, cw, ch2, fill=WHITE, line=BORDER, line_w=1.25, radius=0.05)
        path = shots.get(key)
        if path:
            s.shapes.add_picture(path, Inches(x + 0.06), Inches(cy2 + 0.06), width=Inches(img_w))
            actual_h = img_w * ratios[key] if key in shots else 0
            used = min(actual_h, ch2 - cap_h - 0.18)
            cap_y = cy2 + 0.06 + used + 0.08
            textbox(s, x + 0.14, cap_y, cw - 0.28, cap_h, [
                ([(cap_title, 11.5, True, DARK)], PP_ALIGN.LEFT, 3),
                ([(cap_sub, 9, False, GRAY)], PP_ALIGN.LEFT, 0),
            ])
    band = rect(s, 0.44, 6.55, 12.45, 0.46, fill=GREEN_SOFT, line=GREEN, line_w=1.0)
    write(band, [([("Deployed on free tiers - ", 11, True, DARK),
                   ("Cloudflare Pages (frontend) + Render + SQLite (backend). "
                    "Live now, scan the QR on the last slide", 11, False, DARK)],
                  PP_ALIGN.CENTER, 0)]);

    # ================================================== slide 6 - rewards & referrals
    s = blank(prs)
    header(s, "Community engine", "Rewards and referrals that keep donors engaged")
    footer(s, 6)
    cy, chh = 1.72, 4.72
    # rewards card
    rect(s, 0.44, cy, 6.0, chh, fill=WHITE, line=BORDER, line_w=1.25, radius=0.06)
    h1 = rect(s, 0.44, cy, 6.0, 0.55, fill=GREEN, radius=0.06)
    write(h1, [([("COMMUNITY REWARDS", 13.5, True, WHITE)], PP_ALIGN.LEFT, 0)],
          m=(0.25, 0.1, 0, 0))
    bullets(s, 0.75, cy + 0.75, 5.45, chh - 0.9, [
        ("Earn recognition", "badges and certificates for completing your profile, "
         "inviting friends and learning donation facts"),
        ("Redeem", "for partner offers from verified local partners - always labeled "
         "\u201cDemo Partner\u201d in the demo"),
        ("Transactional claims", "reserve \u2192 verify \u2192 redeem; every step is "
         "audited and race-safe"),
        ("Never cash", "no money, no gift cards, and nothing is ever tied to "
         "donating blood - recognition only"),
    ], size=12, gap=9)
    # referral card with funnel
    rect(s, 6.89, cy, 6.0, chh, fill=WHITE, line=BORDER, line_w=1.25, radius=0.06)
    h2 = rect(s, 6.89, cy, 6.0, 0.55, fill=BRAND, radius=0.06)
    write(h2, [([("REFERRAL PROGRAM - TRACKED FUNNEL", 13.5, True, WHITE)],
                PP_ALIGN.LEFT, 0)], m=(0.25, 0.1, 0, 0))
    funnel = ["Share link  BLOODBRIDGE-XXXXX", "Friend opens & registers",
              "Profile completed", "First request or donor response",
              "Reward eligibility \u2192 admin-reviewed claim"]
    fy = cy + 0.68
    fw, fh = 3.6, 0.46
    fx = 6.89 + 0.25
    for i, step in enumerate(funnel):
        col = GREEN_SOFT if i == len(funnel) - 1 else LIGHT
        ln = GREEN if i == len(funnel) - 1 else BORDER
        b = rect(s, fx, fy, fw, fh, fill=col, line=ln, line_w=1.0, radius=0.22)
        write(b, [([(step, 10.5, i == len(funnel) - 1, DARK)], PP_ALIGN.LEFT, 0)],
              m=(0.14, 0.06, 0, 0))
        badge = rect(s, fx - 0.24, fy + 0.06, 0.34, 0.34, fill=BRAND, shape=MSO_SHAPE.OVAL)
        write(badge, [([(str(i + 1), 11, True, WHITE)], PP_ALIGN.CENTER, 0)])
        if i < len(funnel) - 1:
            arrow(s, fx + fw / 2, fy + fh + 0.01, fx + fw / 2, fy + fh + 0.15,
                  color=BRAND, w=1.5)
        fy += fh + 0.17
    note = textbox(s, 7.2, fy + 0.08, 5.4, 0.8,
                   [([("Protections: ", 10.5, True, BRAND),
                      ("8 tracked stages per referral \u00b7 unique per-user codes \u00b7 "
                       "self-referral & duplicate-device fraud checks \u00b7 campaigns need "
                       "admin approval notes", 10.5, False, GRAY)], PP_ALIGN.LEFT, 0)])
    warn = rect(s, 0.44, 6.6, 12.45, 0.5, fill=AMBER_SOFT, line=AMBER, line_w=1.0)
    write(warn, [([("Ethics by design: ", 11.5, True, AMBER),
                   ("no cash equivalents, nothing tied to the act of donating, and "
                    "every incentive is disclosed in the UI.", 11.5, False, DARK)],
                  PP_ALIGN.CENTER, 0)])

    # ================================================== slide 7 - tech & demo
    s = blank(prs)
    header(s, "Under the hood", "Architecture, quality and how to try it live")
    footer(s, 7)
    tiers = [
        ("Frontend", "React 18 \u00b7 TypeScript \u00b7 Vite \u00b7 Tailwind\n12 pages, "
         "protected routes, notification bell"),
        ("API", "FastAPI \u00b7 Pydantic schemas\n9 routers, role-based auth "
         "(PBKDF2 + HMAC tokens)"),
        ("Data", "SQLAlchemy ORM \u00b7 15 models\nSQLite now, PostgreSQL-ready by config"),
    ]
    tw, tgap, ty, th = 3.6, 0.62, 1.78, 1.62
    x0 = (SLIDE_W - (3 * tw + 2 * tgap)) / 2
    for i, (t, sub) in enumerate(tiers):
        x = x0 + i * (tw + tgap)
        node(s, x, ty, tw, th, i + 1, t, sub)
        if i < 2:
            arrow(s, x + tw + 0.06, ty + th / 2, x + tw + tgap - 0.06, ty + th / 2)
    # quality card
    qy = 4.35
    rect(s, 0.44, qy, 7.3, 2.3, fill=WHITE, line=BORDER, line_w=1.25, radius=0.06)
    textbox(s, 0.7, qy + 0.12, 6.8, 0.35,
            [([("QUALITY & SAFETY", 12.5, True, DARK)], PP_ALIGN.LEFT, 0)])
    bullets(s, 0.7, qy + 0.52, 6.9, 1.7, [
        "73 automated tests, all green, plus a live end-to-end browser run",
        "Donor phone/address never exposed publicly; contact is consent-gated",
        "Compliance disclaimers on every page and every assistant reply",
        "Audit log for admin actions; demo data clearly seeded & labeled",
    ], size=11, gap=6)
    # live-demo card with QR
    rect(s, 8.0, qy, 4.89, 2.3, fill=BRAND_SOFT, line=BRAND, line_w=1.5, radius=0.06)
    textbox(s, 8.25, qy + 0.12, 3.6, 0.35,
            [([("SCAN - IT IS LIVE NOW", 12.5, True, BRAND)], PP_ALIGN.LEFT, 0)])
    textbox(s, 8.25, qy + 0.52, 3.35, 1.65, [
        ([("bloodbridge-app.", 12.5, True, DARK)], PP_ALIGN.LEFT, 2),
        ([("riteshnethi-art.workers.dev", 12.5, True, DARK)], PP_ALIGN.LEFT, 8),
        ([("Free tier: Cloudflare Pages + Render", 10, False, DARK)], PP_ALIGN.LEFT, 6),
        ([("No login needed - demo data, clearly labeled", 9.5, False, GRAY)],
         PP_ALIGN.LEFT, 0),
    ])
    qr_frame = rect(s, 11.05, qy + 0.18, 1.65, 1.65, fill=WHITE, line=BORDER, line_w=1.25, radius=0.06)
    if os.path.exists(qr_png):
        s.shapes.add_picture(qr_png, Inches(11.13), Inches(qy + 0.26), width=Inches(1.49))

    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print("saved:", path)
