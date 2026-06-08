"""
Generate blog article JSON fixtures for products without published articles.
Reads product data from /tmp/product_data.json and outputs JSON files
into blog_content/batches/033-product-spotlights-1/ through ...-4/.
"""
import json
import os
import random
from datetime import datetime

PRODUCT_DATA = "/tmp/product_data.json"
OUTPUT_DIR = "blog_content/batches"
BATCH_SIZE = 40  # articles per batch directory

random.seed(42)

# ── Product type labels ──────────────────────────────────────────
TYPE_LABELS = {
    "PH": "phone",
    "TB": "tablet",
    "LT": "laptop / computer",
    "AC": "accessory",
    "TW": "earphone / audio",
    "SW": "watch / wearable",
}

# ── Opening hooks (rotated) ──────────────────────────────────────
OPENING_HOOKS_PHONE = [
    "When it comes to finding the perfect smartphone at the best price in Kenya, the market is flooded with options. But the affordable {product_name} actually delivers. Whether you are upgrading from an older model or simply looking for the best {feature} in its class, this release from {brand} deserves your full attention.",
    "The affordable {product_name} is here, and it is making a strong case for being one of the most compelling {brand} releases this year. Packed with {feature} and wrapped in a refined design, it is built for anyone who refuses to settle — at a price that makes sense in Kenya.",
    "If you have been waiting for an affordable smartphone that balances performance, design, and value without cutting corners, the {product_name} might be exactly what you are looking for. {brand} has delivered a well-rounded package that punches above its weight in Kenya.",
    "The {product_name} enters the Kenyan market with a clear mission: deliver flagship-level features at an affordable price. With {feature} at its core and a battery built to last, it is a device that demands a closer look.",
    "{brand} has done it again. The {product_name} builds on everything that made its predecessors great while introducing meaningful upgrades like {feature}. It is a phone that knows exactly what it wants to be — affordable and reliable for Kenyan buyers.",
]

OPENING_HOOKS_OTHER = [
    "When it comes to finding the perfect {type_label} at the best price in Kenya, the choices can be overwhelming. But the affordable {product_name} actually delivers. Whether you need {feature} or simply want reliable performance from {brand}, this one stands out.",
    "The affordable {product_name} from {brand} is designed to make your daily life easier. With {feature} and a build that prioritises durability, it earns its place in your everyday carry — backed by warranty for peace of mind.",
    "If you are looking for an affordable {type_label} that combines quality, reliability, and thoughtful design, the {product_name} from {brand} is worth your attention. It delivers where it counts, and ships same day within Nairobi.",
    "{brand} has raised the bar with the {product_name}. Featuring {feature} and a design built for real-world use, it is a practical choice that does not compromise on quality or affordability — with warranty included in Kenya.",
    "The {product_name} proves that you do not need to spend a fortune to get a well-made {type_label}. {brand} has put together an affordable package that delivers solid performance and everyday dependability at the best price. Available in Kenya with same day shipping.",
]

# ── Design section templates ─────────────────────────────────────
DESIGN_INTROS = [
    "Out of the box, the first thing you will notice about the {product_name} is its thoughtful design. {brand} has opted for a clean, functional aesthetic that looks at home anywhere.",
    "The {product_name} makes a strong first impression with its refined look and solid build quality. It is clear that {brand} has paid attention to the details that matter.",
    "From the moment you unbox the {product_name}, the build quality is evident. {brand} has chosen materials and finishes that feel premium without being flashy.",
    "The {product_name} strikes a nice balance between form and function. It is designed to be practical for everyday use while still looking the part.",
]

# ── Feature section intros ───────────────────────────────────────
FEATURE_INTROS = [
    "Performance and battery life are where the {product_name} truly shines. It is equipped with the features that matter most for daily use in Kenya, making it incredibly capable for a wide range of tasks.",
    "Under the hood, the {product_name} brings together a solid set of specifications that handle everything from everyday tasks to more demanding workloads. The battery is built to keep up with your day.",
    "Where the {product_name} really impresses is in the feature set and battery life. {brand} has packed in everything you need for a smooth, reliable experience at an affordable price.",
]

# ── "Who is it for" section templates ────────────────────────────
AUDIENCE_TEMPLATES = [
    "The {product_name} is designed for anyone in Kenya who wants a dependable {type_label} at the best price without overpaying for features they will never use. If you value {feature} and appreciate {brand}'s attention to reliability, this is a strong contender. Order with same day shipping within Nairobi.",
    "Who is the {product_name} really for? It is for the user who needs a {type_label} that just works — at an affordable price. Whether you are a student, a professional, or someone who simply wants a dependable device, {brand} has built this with you in mind. Backed by warranty and available with fast delivery across Kenya.",
    "The {product_name} suits a wide range of users in Kenya. If you prioritise {feature} and want a {type_label} from a trusted brand like {brand} at a great price, this is an excellent choice that will serve you well. Enjoy same day shipping within Nairobi and warranty on every purchase.",
]

# ── Verdict / closing templates ──────────────────────────────────
VERDICT_TEMPLATES = [
    "Ultimately, the {product_name} is a solid {type_label} that delivers where it counts. It hits the sweet spot between performance, design, and value. If you are looking for the best price on a reliable device from {brand} in Kenya, this one earns a strong recommendation. Backed by warranty and available with same day shipping.",
    "The {product_name} proves that {brand} knows how to deliver a well-rounded {type_label} at an affordable price. It is not trying to be the flashiest option on the shelf, but it delivers consistent performance and battery life where it matters. Highly recommended for everyday use in Kenya.",
    "For the best price in Kenya, the {product_name} offers excellent value. It covers all the essentials, performs reliably, and comes from a brand you can trust with warranty coverage. If you need a {type_label} that gets the job done, look no further. Same day shipping available within Nairobi.",
]

CTA_TEMPLATES = [
    "Ready to upgrade at the best price? Check out the {product_name} and explore our full range of specs, colors, and options in the shop today. Same day shipping within Nairobi and warranty included.",
    "See the {product_name} for yourself in the shop. Browse the full specs and make it yours today with affordable pricing, warranty, and fast delivery across Kenya.",
    "Visit the shop to view the {product_name} at the best price in Kenya. Take advantage of our competitive pricing, warranty coverage, and same day shipping within Nairobi.",
]


def pick(choices, seed, key=None):
    """Deterministically pick from a list based on seed and optional key."""
    r = random.Random(str(seed) + str(key))
    return r.choice(choices)


def get_product_type_label(pt):
    return TYPE_LABELS.get(pt, "device")


def get_feature(product):
    """Extract a notable feature from product data."""
    desc = (product.get('long_description') or product.get('product_description') or '')
    brand = product.get('brand', '')
    name = product.get('product_name', '')
    pt = product.get('product_type', '')
    
    if pt == 'PH':
        features = [
            f"its impressive camera system",
            f"its long-lasting battery",
            f"its vibrant display",
            f"its powerful performance",
            f"its sleek design and capable cameras",
            f"its all-day battery life",
            f"its smooth performance and display quality",
        ]
    elif pt == 'TB':
        features = [
            f"its large, immersive display",
            f"its portability and battery life",
            f"its versatility for work and entertainment",
            f"its powerful chip and long battery life",
        ]
    elif pt == 'LT':
        features = [
            f"its powerful processor and ample storage",
            f"its combination of performance and portability",
            f"its excellent build quality and performance",
        ]
    elif pt in ('AC', 'TW'):
        features = [
            f"its reliable performance",
            f"its thoughtful design and durability",
            f"its excellent build quality",
            f"its compatibility and ease of use",
        ]
    else:
        features = [
            f"its stand out features",
            f"its quality build and design",
            f"its reliable performance",
        ]
    
    r = random.Random(name + brand)
    return r.choice(features)


def generate_headline(product, seed):
    name = product['product_name']
    brand = product.get('brand', '')
    pt = product.get('product_type', '')
    tl = get_product_type_label(pt)
    
    templates_phone = [
        f"{name} Review: Affordable {brand} Phone in Kenya",
        f"{name}: Best Price on {brand}'s Latest Phone in Kenya",
        f"{name} Review: Performance, Battery, and Value in Kenya",
        f"Is the {name} the Right Affordable Phone for You in Kenya?",
        f"{name} Review: Affordable Price, Solid Performance in Kenya",
    ]
    templates_other = [
        f"{name} Review: Affordable {brand} {tl.title()} in Kenya",
        f"{name}: Best Price on This {brand} {tl.title()} in Kenya",
        f"{name} Review: Performance, Battery, and Value in Kenya",
        f"Is the {name} the Right Affordable {tl.title()} for You in Kenya?",
        f"{name} Review: Affordable Price, Great Value in Kenya",
    ]
    
    templates = templates_phone if pt == 'PH' else templates_other
    return pick(templates, seed, 'headline').format(name=name, brand=brand, tl=tl)


def generate_seo_title(product, seed):
    name = product['product_name']
    brand = product.get('brand', '')
    pt = product.get('product_type', '')
    
    templates = [
        f"{name} Review: Best Price in Kenya | Affordable Gadgets KE",
        f"{name} in Kenya: Affordable Review & Specs | Affordable Gadgets KE",
        f"{name} Review & Best Price | Affordable Gadgets KE",
        f"Buy {name} in Kenya at Best Price | Affordable Gadgets KE",
        f"{name}: Affordable Review & Buying Guide Kenya | Affordable Gadgets KE",
    ]
    return pick(templates, seed, 'seo_title').format(name=name, brand=brand)[:60]


def generate_seo_description(product, seed):
    name = product['product_name']
    brand = product.get('brand', '')
    price = product.get('min_price') or product.get('max_price') or ''
    price_str = f" from Ksh {price:,.0f}" if price else ""
    
    templates = [
        f"Looking for the {name} at the best price in Kenya? Read our review covering design, battery, and value{price_str}. Available with warranty and same day shipping at Affordable Gadgets KE in Nairobi.",
        f"Thinking about buying the {name} in Kenya? We break down everything you need to know{price_str} — from features and battery life to real-world performance. Affordable price with warranty at Affordable Gadgets KE.",
        f"Read our full review of the affordable {name} by {brand}{price_str}. Discover key features, battery life, and best price in Kenya. Warranty and same day shipping at Affordable Gadgets KE Nairobi.",
    ]
    return pick(templates, seed, 'seo_desc').format(name=name, brand=brand, price_str=price_str)[:160]


def generate_body(product, seed):
    name = product['product_name']
    brand = product.get('brand', '')
    pt = product.get('product_type', '')
    tl = get_product_type_label(pt)
    desc = (product.get('long_description') or product.get('product_description') or '')
    feature = get_feature(product)

    # Dedicated description if available
    desc_paragraph = ""
    if desc and len(desc) > 30:
        desc_paragraph = f"\n\n{desc}"

    # Opening
    hooks = OPENING_HOOKS_PHONE if pt == 'PH' else OPENING_HOOKS_OTHER
    opening = pick(hooks, seed, 'opening').format(
        product_name=name, brand=brand, feature=feature, type_label=tl
    )

    # Design section
    design_intro = pick(DESIGN_INTROS, seed, 'design').format(
        product_name=name, brand=brand
    )
    design_body = f"It is designed to fit seamlessly into your daily routine, whether you are at home, in the office, or on the move. Every purchase comes with warranty coverage for added peace of mind."
    if pt == 'PH':
        design_body = f"The phone feels solid in the hand with a finish that resists fingerprints and everyday wear. It is comfortable to hold and easy to use one-handed when needed. Plus, it comes with warranty coverage for your peace of mind."

    # Feature section
    feat_intro = pick(FEATURE_INTROS, seed, 'feature').format(
        product_name=name, brand=brand
    )
    price_str = ""
    p_min = product.get('min_price')
    p_max = product.get('max_price')
    if p_min and p_max and p_min != p_max:
        price_str = f"Priced between Ksh {p_min:,.0f} and Ksh {p_max:,.0f}, it offers flexibility depending on your budget and storage needs."
    elif p_min:
        price_str = f"Priced from Ksh {p_min:,.0f}, it offers excellent value in its category."

    # Audience section
    audience = pick(AUDIENCE_TEMPLATES, seed, 'audience').format(
        product_name=name, brand=brand, feature=feature, type_label=tl
    )

    # Verdict
    verdict = pick(VERDICT_TEMPLATES, seed, 'verdict').format(
        product_name=name, brand=brand, type_label=tl
    )

    # CTA
    cta = pick(CTA_TEMPLATES, seed, 'cta').format(
        product_name=name, brand=brand
    )

    # Build full body
    body = f"""{opening}

## Design and Build: Thoughtful and Practical

{design_intro} {design_body}{desc_paragraph}

## Key Features Under the Hood

{feat_intro}

Here is a quick look at the standout details:

- **Brand:** {brand}
- **Model:** {name}
- **Category:** {tl.title()}
{price_str}

{audience}

## The Verdict

{verdict}

{cta}"""

    return body.strip()


def main():
    with open(PRODUCT_DATA) as f:
        products = json.load(f)

    print(f"Generating articles for {len(products)} products...")

    # Sort by brand then name for consistency
    products.sort(key=lambda p: (p.get('brand', ''), p.get('product_name', '')))

    # Create batch directories
    batch_num = 33
    batch_count = 0
    batch_total = 1
    os.makedirs(f"{OUTPUT_DIR}/033-product-spotlights-1", exist_ok=True)
    batch_dir = f"{OUTPUT_DIR}/033-product-spotlights-1"

    generated = 0
    for idx, product in enumerate(products):
        slug = product['slug']
        name = product['product_name']

        # Rotate batch directories every BATCH_SIZE articles
        if batch_count >= BATCH_SIZE:
            batch_count = 0
            batch_total += 1
            batch_num += 1
            batch_dir = f"{OUTPUT_DIR}/{batch_num:03d}-product-spotlights-{batch_total}"
            os.makedirs(batch_dir, exist_ok=True)

        headline = generate_headline(product, idx)
        seo_title = generate_seo_title(product, idx)
        seo_description = generate_seo_description(product, idx)
        body = generate_body(product, idx)

        article = {
            "product_slug": slug,
            "product_name": name,
            "category": "buying_guide",
            "headline": headline,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "is_published": True,
            "body_markdown": body,
        }

        filename = f"{batch_dir}/{idx+1:03d}-{slug}.json"
        with open(filename, 'w') as f:
            json.dump(article, f, indent=2)

        batch_count += 1
        generated += 1
        if generated % 20 == 0:
            print(f"  Generated {generated}/{len(products)}...", flush=True)

    print(f"\nDone! Generated {generated} articles in {batch_total} batches.")
    print(f"Directories: 033-product-spotlights-1 through {batch_num:03d}-product-spotlights-{batch_total}")


if __name__ == '__main__':
    main()
