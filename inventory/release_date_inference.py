"""Infer product release dates from catalog names and a curated family lookup."""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

_FAMILY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Apple iPhone (specific variants before generic)
    (re.compile(r"iphone\s+17e"), "iphone-17e"),
    (re.compile(r"iphone\s+17\s+pro\s+max"), "iphone-17-pro-max"),
    (re.compile(r"iphone\s+17\s+pro"), "iphone-17-pro"),
    (re.compile(r"iphone\s+17\s+air"), "iphone-17-air"),
    (re.compile(r"iphone\s+17"), "iphone-17"),
    (re.compile(r"iphone\s+16e"), "iphone-16e"),
    (re.compile(r"iphone\s+16\s+pro\s+max"), "iphone-16-pro-max"),
    (re.compile(r"iphone\s+16\s+pro"), "iphone-16-pro"),
    (re.compile(r"iphone\s+16\s+plus"), "iphone-16-plus"),
    (re.compile(r"iphone\s+16"), "iphone-16"),
    (re.compile(r"iphone\s+15\s+pro\s+max"), "iphone-15-pro-max"),
    (re.compile(r"iphone\s+15\s+pro"), "iphone-15-pro"),
    (re.compile(r"iphone\s+15\s+plus"), "iphone-15-plus"),
    (re.compile(r"iphone\s+15"), "iphone-15"),
    (re.compile(r"iphone\s+14\s+pro\s+max"), "iphone-14-pro-max"),
    (re.compile(r"iphone\s+14\s+pro"), "iphone-14-pro"),
    (re.compile(r"iphone\s+14\s+plus"), "iphone-14-plus"),
    (re.compile(r"iphone\s+14"), "iphone-14"),
    (re.compile(r"iphone\s+13\s+pro\s+max"), "iphone-13-pro-max"),
    (re.compile(r"iphone\s+13\s+pro"), "iphone-13-pro"),
    (re.compile(r"iphone\s+13\s+mini"), "iphone-13-mini"),
    (re.compile(r"iphone\s+13"), "iphone-13"),
    (re.compile(r"iphone\s+12\s+pro\s+max"), "iphone-12-pro-max"),
    (re.compile(r"iphone\s+12\s+pro"), "iphone-12-pro"),
    (re.compile(r"iphone\s+12\s+mini"), "iphone-12-mini"),
    (re.compile(r"iphone\s+12"), "iphone-12"),
    (re.compile(r"iphone\s+11\s+pro\s+max"), "iphone-11-pro-max"),
    (re.compile(r"iphone\s+11\s+pro"), "iphone-11-pro"),
    (re.compile(r"iphone\s+11\b"), "iphone-11"),
    (re.compile(r"iphone\s+xs\s+max"), "iphone-xs-max"),
    (re.compile(r"iphone\s+xs\b"), "iphone-xs"),
    (re.compile(r"iphone\s+xr\b"), "iphone-xr"),
    (re.compile(r"iphone\s+x\b"), "iphone-x"),
    (re.compile(r"iphone\s+8\s+plus"), "iphone-8-plus"),
    (re.compile(r"iphone\s+8\b"), "iphone-8"),
    (re.compile(r"iphone\s+7\s+plus"), "iphone-7-plus"),
    (re.compile(r"iphone\s+7\b"), "iphone-7"),
    (re.compile(r"iphone\s+se\s*(?:\(\s*3|3rd|\b3\b)"), "iphone-se-3"),
    (re.compile(r"iphone\s+se\b"), "iphone-se-3"),
    (re.compile(r"iphone\s+air\b"), "iphone-17-air"),
    # Samsung Galaxy S / Z / Note
    (re.compile(r"galaxy\s+s26\s+ultra"), "galaxy-s26-ultra"),
    (re.compile(r"galaxy\s+s26\+"), "galaxy-s26-plus"),
    (re.compile(r"galaxy\s+s26\b"), "galaxy-s26"),
    (re.compile(r"galaxy\s+s25\s+ultra"), "galaxy-s25-ultra"),
    (re.compile(r"galaxy\s+s25\s+edge"), "galaxy-s25-edge"),
    (re.compile(r"galaxy\s+s25\s+fe"), "galaxy-s25-fe"),
    (re.compile(r"galaxy\s+s25\+"), "galaxy-s25-plus"),
    (re.compile(r"galaxy\s+s25\b"), "galaxy-s25"),
    (re.compile(r"galaxy\s+s24\s+ultra"), "galaxy-s24-ultra"),
    (re.compile(r"galaxy\s+s24\+"), "galaxy-s24-plus"),
    (re.compile(r"galaxy\s+s24\b"), "galaxy-s24"),
    (re.compile(r"galaxy\s+s23\s+ultra"), "galaxy-s23-ultra"),
    (re.compile(r"galaxy\s+s23\s*fe"), "galaxy-s23-fe"),
    (re.compile(r"galaxy\s+s23\+"), "galaxy-s23-plus"),
    (re.compile(r"galaxy\s+s23\b"), "galaxy-s23"),
    (re.compile(r"galaxy\s+s22\s+ultra"), "galaxy-s22-ultra"),
    (re.compile(r"galaxy\s+s22\+"), "galaxy-s22-plus"),
    (re.compile(r"galaxy\s+s22\b"), "galaxy-s22"),
    (re.compile(r"galaxy\s+s21\s+ultra"), "galaxy-s21-ultra"),
    (re.compile(r"galaxy\s+s21\s*fe"), "galaxy-s21-fe"),
    (re.compile(r"galaxy\s+s21\+"), "galaxy-s21-plus"),
    (re.compile(r"galaxy\s+s21\b"), "galaxy-s21"),
    (re.compile(r"galaxy\s+s20\s+ultra"), "galaxy-s20-ultra"),
    (re.compile(r"galaxy\s+s20\s+fe"), "galaxy-s20-fe"),
    (re.compile(r"galaxy\s+s20\+"), "galaxy-s20-plus"),
    (re.compile(r"galaxy\s+s20\b"), "galaxy-s20"),
    (re.compile(r"galaxy\s+s10\s+lite"), "galaxy-s10-lite"),
    (re.compile(r"galaxy\s+s10\+"), "galaxy-s10-plus"),
    (re.compile(r"galaxy\s+s10e"), "galaxy-s10e"),
    (re.compile(r"galaxy\s+s10\b"), "galaxy-s10"),
    (re.compile(r"galaxy\s+fold\s*5"), "galaxy-z-fold-5"),
    (re.compile(r"galaxy\s+z\s*fold\s*7"), "galaxy-z-fold-7"),
    (re.compile(r"galaxy\s+z\s*fold\s*6"), "galaxy-z-fold-6"),
    (re.compile(r"galaxy\s+z\s*fold\s*5"), "galaxy-z-fold-5"),
    (re.compile(r"galaxy\s+z\s*fold\s*4"), "galaxy-z-fold-4"),
    (re.compile(r"galaxy\s+z\s*fold\s*3"), "galaxy-z-fold-3"),
    (re.compile(r"galaxy\s+z\s*flip\s*7"), "galaxy-z-flip-7"),
    (re.compile(r"galaxy\s+z\s*flip\s*6"), "galaxy-z-flip-6"),
    (re.compile(r"galaxy\s+z\s*flip\s*5"), "galaxy-z-flip-5"),
    (re.compile(r"galaxy\s+z\s*flip\s*4"), "galaxy-z-flip-4"),
    (re.compile(r"galaxy\s+z\s*flip\s*3"), "galaxy-z-flip-3"),
    (re.compile(r"galaxy\s+note\s*20\s+ultra"), "galaxy-note-20-ultra"),
    (re.compile(r"galaxy\s+note\s*20\b"), "galaxy-note-20"),
    (re.compile(r"galaxy\s+note\s*10\+"), "galaxy-note-10-plus"),
    (re.compile(r"galaxy\s+note\s*10\b"), "galaxy-note-10"),
    # Samsung A / M series (two-digit to avoid matching storage)
    (re.compile(r"galaxy\s+a57\b"), "galaxy-a57"),
    (re.compile(r"galaxy\s+a56\b"), "galaxy-a56"),
    (re.compile(r"galaxy\s+a55\b"), "galaxy-a55"),
    (re.compile(r"galaxy\s+a54\b"), "galaxy-a54"),
    (re.compile(r"galaxy\s+a53\b"), "galaxy-a53"),
    (re.compile(r"galaxy\s+a52\b"), "galaxy-a52"),
    (re.compile(r"galaxy\s+a51\b"), "galaxy-a51"),
    (re.compile(r"galaxy\s+a50\b"), "galaxy-a50"),
    (re.compile(r"galaxy\s+a42\b"), "galaxy-a42"),
    (re.compile(r"galaxy\s+a41\b"), "galaxy-a41"),
    (re.compile(r"galaxy\s+a40\b"), "galaxy-a40"),
    (re.compile(r"galaxy\s+a37\b"), "galaxy-a37"),
    (re.compile(r"galaxy\s+a36\b"), "galaxy-a36"),
    (re.compile(r"galaxy\s+a35\b"), "galaxy-a35"),
    (re.compile(r"galaxy\s+a34\b"), "galaxy-a34"),
    (re.compile(r"galaxy\s+a33\b"), "galaxy-a33"),
    (re.compile(r"galaxy\s+a32\b"), "galaxy-a32"),
    (re.compile(r"galaxy\s+a31\b"), "galaxy-a31"),
    (re.compile(r"galaxy\s+a30\b"), "galaxy-a30"),
    (re.compile(r"galaxy\s+a26\b"), "galaxy-a26"),
    (re.compile(r"galaxy\s+a25\b"), "galaxy-a25"),
    (re.compile(r"galaxy\s+a24\b"), "galaxy-a24"),
    (re.compile(r"galaxy\s+a23\b"), "galaxy-a23"),
    (re.compile(r"galaxy\s+a22\b"), "galaxy-a22"),
    (re.compile(r"galaxy\s+a21\b"), "galaxy-a21"),
    (re.compile(r"galaxy\s+a20\b"), "galaxy-a20"),
    (re.compile(r"galaxy\s+a17\b"), "galaxy-a17"),
    (re.compile(r"galaxy\s+a16\b"), "galaxy-a16"),
    (re.compile(r"galaxy\s+a15\b"), "galaxy-a15"),
    (re.compile(r"galaxy\s+a14\b"), "galaxy-a14"),
    (re.compile(r"galaxy\s+a13\b"), "galaxy-a13"),
    (re.compile(r"galaxy\s+a12\b"), "galaxy-a12"),
    (re.compile(r"galaxy\s+a10\b"), "galaxy-a10"),
    (re.compile(r"galaxy\s+a07\b"), "galaxy-a07"),
    (re.compile(r"galaxy\s+a06\b"), "galaxy-a06"),
    (re.compile(r"galaxy\s+buds\s+core"), "galaxy-buds-core"),
    (re.compile(r"galaxy\s+buds\s+3\b"), "galaxy-buds-3"),
    (re.compile(r"galaxy\s+tab\s+s10\s+fe"), "galaxy-tab-s10-fe"),
    (re.compile(r"pixel\s+10a\b"), "pixel-10a"),
    (re.compile(r"pixel\s+9a\b"), "pixel-9a"),
    (re.compile(r"mac\s+mini\s+m4"), "mac-mini-m4"),
    (re.compile(r"macbook\s+13.*neo"), "macbook-13-neo"),
    (re.compile(r"macbook\s+air\b"), "macbook-air-m5"),
    (re.compile(r"apple\s+pencil\s+2\s+pro"), "apple-pencil-2-pro"),
    (re.compile(r"apple\s+pencil\s+2"), "apple-pencil-2"),
    (re.compile(r"honor\s+x5c\s+plus"), "honor-x5c-plus"),
    (re.compile(r"honor\s+x5c\b"), "honor-x5c"),
    (re.compile(r"honor\s+x5b\b"), "honor-x5b"),
    (re.compile(r"honor\s+x7d\b"), "honor-x7d"),
    (re.compile(r"honor\s+x7c\b"), "honor-x7c"),
    (re.compile(r"honor\s+7d\b"), "honor-7d"),
    (re.compile(r"honor\s+play\s*10"), "honor-play10"),
    (re.compile(r"oppo\s+reno\s+15\s+pro"), "oppo-reno-15-pro-5g"),
    (re.compile(r"oppo\s+reno\s+15f"), "oppo-reno-15f-5g"),
    (re.compile(r"oppo\s+reno\s+15"), "oppo-reno-15-5g"),
    (re.compile(r"oppo\s+a6\s+pro"), "oppo-a6-pro-4g"),
    (re.compile(r"oppo\s+a6x\b"), "oppo-a6x"),
    (re.compile(r"oppo\s+a6\b"), "oppo-a6-4g"),
    (re.compile(r"oppo\s+a5\b"), "oppo-a5"),
    (re.compile(r"oppo\s+a3x\b"), "oppo-a3x"),
    (re.compile(r"oppo\s+a3\b"), "oppo-a3"),
    (re.compile(r"redmi\s+note\s+15\s+pro"), "redmi-note-15-pro"),
    (re.compile(r"redmi\s+note\s+15\b"), "redmi-note-15"),
    (re.compile(r"redmi\s+15c\b"), "redmi-15c"),
    (re.compile(r"redmi\s+15\b"), "redmi-15"),
    (re.compile(r"redmi\s+a7\s+pro"), "redmi-a7-pro"),
    (re.compile(r"redmi\s+a7\b"), "redmi-a7"),
    (re.compile(r"infinix\s+hot\s+60\s+pro\+"), "infinix-hot-60-pro+"),
    (re.compile(r"infinix\s+hot\s+60\s+pro"), "infinix-hot-60-pro"),
    (re.compile(r"infinix\s+hot\s+60i\b"), "infinix-hot-60i"),
    (re.compile(r"infinix\s+note\s+60\s+pro"), "infinix-note-60-pro"),
    (re.compile(r"infinix\s+note\s+edge"), "infinix-note-edge"),
    (re.compile(r"infinix\s+smart\s+20\b"), "infinix-smart-20"),
    (re.compile(r"infinix\s+smart\s+10\b"), "infinix-smart-10"),
    (re.compile(r"tecno\s+camon\s+50\s+ultra"), "tecno-camon-50-ultra"),
    (re.compile(r"tecno\s+camon\s+50\s+pro"), "tecno-camon-50-pro"),
    (re.compile(r"tecno\s+camon\s+50\b"), "tecno-camon-50"),
    (re.compile(r"tecno\s+spark\s+50\b"), "tecno-spark-50"),
    (re.compile(r"tecno\s+spark\s+40\s+pro"), "tecno-spark-40-pro"),
    (re.compile(r"tecno\s+pop\s+20\b"), "tecno-pop-20"),
    (re.compile(r"tecno\s+pop\s+10\b"), "tecno-pop-10"),
    (re.compile(r"vivo\s+v70\s+fe"), "vivo-v70-fe"),
    (re.compile(r"vivo\s+v70\b"), "vivo-v70"),
    (re.compile(r"vivo\s+v60\s+lite\s+5g"), "vivo-v60-lite-5g"),
    (re.compile(r"vivo\s+v60\s+lite\s+4g"), "vivo-v60-lite-4g"),
    (re.compile(r"vivo\s+y31d\b"), "vivo-y31d"),
    (re.compile(r"vivo\s+y21d\b"), "vivo-y21d"),
    (re.compile(r"vivo\s+y05\b"), "vivo-y05"),
    (re.compile(r"vivo\s+y04e\b"), "vivo-y04e"),
    (re.compile(r"vivo\s+y04\b"), "vivo-y04"),
    (re.compile(r"vivo\s+y28\b"), "vivo-y28"),
    (re.compile(r"realme\s+note\s+70\b"), "realme-note-70"),
    (re.compile(r"realme\s+note\s+60x\b"), "realme-note-60x"),
    (re.compile(r"realme\s+note\s+50\b"), "realme-note-50"),
    (re.compile(r"realme\s+c85\s+pro"), "realme-c85-pro"),
    (re.compile(r"realme\s+c100i\b"), "realme-c100i"),
    (re.compile(r"realme\s+c75\b"), "realme-c75"),
    (re.compile(r"realme\s+12\+"), "realme-12+"),
    (re.compile(r"itel\s+s26\s+ultra"), "itel-s26-ultra"),
    (re.compile(r"itel\s+city\s+200"), "itel-city-200"),
    (re.compile(r"itel\s+a100c\b"), "itel-a100c"),
    (re.compile(r"itel\s+a200\b"), "itel-a200"),
    (re.compile(r"itel\s+p70\b"), "itel-p70"),
    (re.compile(r"itel\s+a04\b"), "itel-a04"),
    (re.compile(r"galaxy\s+a05\b"), "galaxy-a05"),
    (re.compile(r"galaxy\s+a04\b"), "galaxy-a04"),
    (re.compile(r"galaxy\s+a03\b"), "galaxy-a03"),
    (re.compile(r"galaxy\s+a02\b"), "galaxy-a02"),
    (re.compile(r"galaxy\s+a01\b"), "galaxy-a01"),
    (re.compile(r"galaxy\s+a70\b"), "galaxy-a70"),
    (re.compile(r"galaxy\s+a71\b"), "galaxy-a71"),
    (re.compile(r"galaxy\s+m54\b"), "galaxy-m54"),
    (re.compile(r"galaxy\s+m53\b"), "galaxy-m53"),
    (re.compile(r"galaxy\s+m52\b"), "galaxy-m52"),
    (re.compile(r"galaxy\s+m51\b"), "galaxy-m51"),
    (re.compile(r"galaxy\s+m40\b"), "galaxy-m40"),
    (re.compile(r"galaxy\s+m33\s*5g"), "galaxy-m33"),
    (re.compile(r"galaxy\s+m32\b"), "galaxy-m32"),
    (re.compile(r"galaxy\s+m31\b"), "galaxy-m31"),
    (re.compile(r"galaxy\s+m30s\b"), "galaxy-m30s"),
    (re.compile(r"galaxy\s+m23\b"), "galaxy-m23"),
    (re.compile(r"galaxy\s+m22\b"), "galaxy-m22"),
    (re.compile(r"galaxy\s+m21\b"), "galaxy-m21"),
    (re.compile(r"galaxy\s+m20\b"), "galaxy-m20"),
    (re.compile(r"galaxy\s+m14\b"), "galaxy-m14"),
    (re.compile(r"galaxy\s+m13\b"), "galaxy-m13"),
    (re.compile(r"galaxy\s+m12\b"), "galaxy-m12"),
    (re.compile(r"galaxy\s+m10\b"), "galaxy-m10"),
    # Google Pixel
    (re.compile(r"pixel\s+10\s+pro\s+xl"), "pixel-10-pro-xl"),
    (re.compile(r"pixel\s+10\s+pro"), "pixel-10-pro"),
    (re.compile(r"pixel\s+10\b"), "pixel-10"),
    (re.compile(r"pixel\s+9\s+pro\s+xl"), "pixel-9-pro-xl"),
    (re.compile(r"pixel\s+9\s+pro"), "pixel-9-pro"),
    (re.compile(r"pixel\s+9\b"), "pixel-9"),
    (re.compile(r"pixel\s+8\b"), "pixel-8"),
    (re.compile(r"pixel\s+7a\b"), "pixel-7a"),
    # OnePlus / Nothing / Xiaomi / Honor / Sony
    (re.compile(r"oneplus\s+15\b"), "oneplus-15"),
    (re.compile(r"oneplus\s+13s\b"), "oneplus-13s"),
    (re.compile(r"oneplus\s+13\b"), "oneplus-13"),
    (re.compile(r"oneplus\s+9\b"), "oneplus-9"),
    (re.compile(r"oneplus\s+nord\s+ce\s+5"), "oneplus-nord-ce-5"),
    (re.compile(r"nothing\s+phone\s+3a\s+pro"), "nothing-phone-3a-pro"),
    (re.compile(r"nothing\s+phone\s+3a\b"), "nothing-phone-3a"),
    (re.compile(r"nothing\s+phone\s+3\b"), "nothing-phone-3"),
    (re.compile(r"xiaomi\s+17\s+pro\s+max"), "xiaomi-17-pro-max"),
    (re.compile(r"honor\s+h400\s+pro"), "honor-h400-pro"),
    (re.compile(r"honor\s+h400\b"), "honor-h400"),
    (re.compile(r"honor\s+x9d\b"), "honor-x9d"),
    (re.compile(r"honor\s+x6c\b"), "honor-x6c"),
    (re.compile(r"xperia\s+10\s+v"), "sony-xperia-10-v"),
    (re.compile(r"xperia\s+5\s+iv"), "sony-xperia-5-iv"),
    # iPad / Mac
    (re.compile(r"ipad\s+pro\s+m5.*13"), "ipad-pro-m5-13"),
    (re.compile(r"ipad\s+pro\s+m5.*11"), "ipad-pro-m5-11"),
    (re.compile(r"ipad\s+pro\s+m4.*13"), "ipad-pro-m4-13"),
    (re.compile(r"ipad\s+pro\s+m4.*11"), "ipad-pro-m4-11"),
    (re.compile(r"ipad\s+air\s+m3"), "ipad-air-m3"),
    (re.compile(r"ipad\s+mini\s+7"), "ipad-mini-7"),
    (re.compile(r"ipad\s+11(?:th)?(?:\s+gen)?"), "ipad-11"),
    (re.compile(r"ipad\s+10\b"), "ipad-10"),
    (re.compile(r"ipad\s+6\b"), "ipad-6"),
    (re.compile(r"macbook\s+air\s+m5"), "macbook-air-m5"),
    (re.compile(r"macbook\s+air\s+m4"), "macbook-air-m4"),
    (re.compile(r"macbook\s+air\s+m3"), "macbook-air-m3"),
    (re.compile(r"macbook\s+air\s+m2"), "macbook-air-m2"),
    (re.compile(r"macbook\s+air\s+m1"), "macbook-air-m1"),
    (re.compile(r"macbook\s+pro\s+m5"), "macbook-pro-m5"),
    (re.compile(r"macbook\s+pro\s+m4"), "macbook-pro-m4"),
    (re.compile(r"imac\s+m1"), "imac-m1"),
    # Wearables / buds
    (re.compile(r"watch\s+ultra\s+3"), "apple-watch-ultra-3"),
    (re.compile(r"watch\s+series\s+11"), "apple-watch-series-11"),
    (re.compile(r"watch\s+series\s+10"), "apple-watch-series-10"),
    (re.compile(r"watch\s+se\s+3"), "apple-watch-se-3"),
    (re.compile(r"watch\s+se\s+2"), "apple-watch-se-2"),
    (re.compile(r"airpods\s+pro\s+3|airpod\s+pro\s+3"), "airpods-pro-3"),
    (re.compile(r"airpods\s+pro\s+2"), "airpods-pro-2"),
    (re.compile(r"airpods\s+4\b"), "airpods-4"),
    (re.compile(r"airpods\s+max"), "airpods-max"),
    (re.compile(r"tab\s+s11\s+ultra"), "galaxy-tab-s11-ultra"),
    (re.compile(r"tab\s+s10\s+ultra"), "galaxy-tab-s10-ultra"),
    (re.compile(r"tab\s+s10\s+lite"), "galaxy-tab-s10-lite"),
    (re.compile(r"tab\s+s9\b"), "galaxy-tab-s9"),
    (re.compile(r"tab\s+a11\s+plus"), "galaxy-tab-a11-plus"),
    (re.compile(r"tab\s+a11\b"), "galaxy-tab-a11"),
    (re.compile(r"watch\s+8\b"), "galaxy-watch-8"),
    (re.compile(r"watch\s+7\b"), "galaxy-watch-7"),
    (re.compile(r"watch\s+6\s+classic"), "galaxy-watch-6-classic"),
    (re.compile(r"buds\s+4\s+pro"), "galaxy-buds-4-pro"),
    (re.compile(r"buds\s+4\b"), "galaxy-buds-4"),
    (re.compile(r"buds\s+3\s+pro"), "galaxy-buds-3-pro"),
    (re.compile(r"buds\s+3\s+fe"), "galaxy-buds-3-fe"),
)


def normalize_product_name(product_name: str) -> str:
    """Strip storage, RAM, and region tags for family matching."""
    name = (product_name or "").lower()
    # Remove storage/RAM clusters as a unit so model numbers (e.g. Z Fold 7) are kept.
    name = re.sub(
        r"\b\d+\s*gb(?:\s+\d+\s*gb)?(?:\s*ram)?\b",
        " ",
        name,
        flags=re.I,
    )
    name = re.sub(r"\b\d+\s*tb\b", " ", name, flags=re.I)
    name = re.sub(r"\b\d+\s*mb\b", " ", name, flags=re.I)
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(
        r"\b(e-?sim|sim|official|dubai|black|desert|silver|orange|blue|white|gold)\b",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(r"\b(\d+)(?:st|nd|rd|th)\s+gen\b", r"\1", name, flags=re.I)
    name = re.sub(r"[^a-z0-9+ ]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def slugify_product_name(product_name: str) -> str:
    normalized = normalize_product_name(product_name)
    return re.sub(r"[^a-z0-9+]+", "-", normalized).strip("-")


def match_family_key(product_name: str) -> str | None:
    normalized = normalize_product_name(product_name)
    for pattern, family_key in _FAMILY_PATTERNS:
        if pattern.search(normalized):
            return family_key
    slug = slugify_product_name(product_name)
    if slug and slug in load_release_date_lookup():
        return slug
    return None


@lru_cache(maxsize=1)
def load_release_date_lookup() -> dict[str, date]:
    """Return family_key -> release date (1st of month). DB first, JSON fallback."""
    try:
        from inventory.models import ProductReleaseDate

        rows = list(ProductReleaseDate.objects.all())
        if rows:
            return {row.family_key: row.to_date() for row in rows}
    except Exception:
        # Table may not exist before migrations run.
        pass

    data_dir = Path(__file__).resolve().parent.parent / "data"
    path = data_dir / "product-release-dates.json"
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    exact_path = data_dir / "product-release-dates-exact.json"
    if exact_path.exists():
        with exact_path.open(encoding="utf-8") as handle:
            raw.update(json.load(handle))
    return {
        key: date.fromisoformat(value).replace(day=1)
        for key, value in raw.items()
    }


def clear_release_date_lookup_cache() -> None:
    load_release_date_lookup.cache_clear()


def infer_release_date(product_name: str) -> date | None:
    """Return a release date for a product name, or None if unknown."""
    lookup = load_release_date_lookup()
    family_key = match_family_key(product_name)
    if family_key:
        return lookup.get(family_key)
    slug = slugify_product_name(product_name)
    return lookup.get(slug) if slug else None
