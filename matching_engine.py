"""
TikTok KOL Matching Engine (Gemini Embedding API version)
============================================================
รับ brand_profile (จาก n8n brand profiler) + kol_dataset (จาก n8n TikTok scraper)
แล้วคำนวณ ranked list ของ KOL ที่เหมาะกับแบรนด์ที่สุด พร้อมเหตุผล match และลิงก์โปรไฟล์

ใช้ Gemini Embedding API แทน local model (sentence-transformers) เพื่อเลี่ยงปัญหา
Windows Application Control Policy บล็อก native DLL ของ torch/scipy/sklearn บนเครื่องที่มี
IT security policy จำกัดการรัน unsigned binary (พบได้บ่อยบนโน้ตบุ๊คบริษัท) — ไฟล์นี้ใช้แค่
`requests` (pure Python) ไม่มี compiled binary ที่เสี่ยงโดนบล็อก

วิธีใช้:
    pip install requests
    setx GEMINI_API_KEY "your-api-key-here"      (Windows, เปิด terminal ใหม่หลังตั้งค่า)
    หรือ: export GEMINI_API_KEY="your-api-key-here"   (Mac/Linux)

    python matching_engine.py --brand brand_profile.json --kols kol_dataset.json --top 15

ที่มา API (สำหรับ citation ในเอกสารส่ง):
    Google Gemini Embedding API — model: gemini-embedding-001
    https://ai.google.dev/gemini-api/docs/embeddings
    เลือกตัวนี้เพราะ multilingual (รองรับไทย+อังกฤษปนกัน), มี free tier สำหรับ prototype,
    และใช้ API key เดียวกับที่ใช้ทำ brand profiler ใน n8n flow อยู่แล้ว ไม่ต้องขอ credential เพิ่ม

CHANGELOG (v2):
    - แก้ปัญหา engagement_rate ของบัญชี follower น้อยผันผวนสูงจนได้ engagement_score
      เต็มหรือใกล้เต็มแบบไม่สมเหตุสมผล (เช่น account 467 followers ได้ 1.0 เต็ม) โดยเปลี่ยนจาก
      raw min-max normalize เป็น "shrinkage estimator" (Bayesian-style) ที่ดึงค่า engagement
      ของบัญชี follower น้อยเข้าใกล้ค่าเฉลี่ยของทั้ง dataset ก่อน แล้วค่อย normalize
      ดู docstring ของ compute_shrunk_engagement() สำหรับรายละเอียดสูตร

CHANGELOG (v3):
    - แก้ปัญหา embedding similarity จับ "beauty" แบบกว้างเกินไป ทำให้ KOL สาย makeup ล้วนๆ
      (ไม่มีคำที่เกี่ยวกับสิว/ผิวแพ้ง่าย/สกินแคร์เลยแม้แต่คำเดียว) ได้ content_fit สูงและขึ้น
      อันดับต้นๆ ทั้งที่เนื้อหาจริงไม่ตรง sub-niche ของแบรนด์ (พบกรณี @natkrittao ซึ่งเป็น
      makeup/eyeliner creator ล้วนๆ แต่ขึ้นอันดับ 1)
      วิธีแก้: เพิ่ม "keyword overlap check" แบบ exact substring match ระหว่างข้อความจริงของ
      KOL กับ keyword ของแบรนด์ (ไม่ใช่แค่ embedding similarity) ถ้าไม่มี keyword ไหนเลยที่
      ปรากฏจริงในข้อความของ KOL จะหัก content_fit ลงด้วย KEYWORD_OVERLAP_PENALTY_MULTIPLIER
      นอกจากนี้ matched_reasons จะเลือกคำที่ "พบจริง" ในข้อความ KOL ก่อนเสมอ แทนที่จะใช้แค่
      อันดับ similarity สูงสุดซึ่งบางครั้งไม่ตรงกับเนื้อหาจริงที่โพสต์
      ดู docstring ของ compute_keyword_overlap() และ select_matched_reasons() สำหรับรายละเอียด

CHANGELOG (v4):
    - เพิ่ม brand_tone (เช่น "น่าเชื่อถือเชิงวิชาการ เข้าถึงง่าย") เข้าไปใน lifestyle embedding
      เดิม field นี้มีอยู่ใน brand_profile.json แต่ไม่เคยถูกใช้คำนวณเลย ทำให้ระบบมองไม่ออกว่า
      KOL คนไหนมีโทนการรีวิวแบบผู้เชี่ยวชาญ/น่าเชื่อถือ vs. influencer ทั่วไปที่รับรีวิวจ่ายเงิน
      ทั้งที่สองแบบนี้อาจพูดถึง product keyword เดียวกันได้พอๆ กัน
    - เพิ่มการตรวจจับ "owned-brand account" — บัญชีที่จริงๆ แล้วเป็นของแบรนด์คู่แข่งเอง (โพสต์
      โปรโมทสินค้าตัวเองเป็นหลัก) ไม่ใช่ influencer อิสระ พบกรณี @kindness.thailand ซึ่ง bio/วิดีโอ
      เป็นบัญชีแบรนด์ "Kindness" เอง ไม่ควรถูกแนะนำให้ไปจ้างรีวิวให้แบรนด์อื่น
      สัญญาณที่ใช้ตรวจจับ: username ไปปรากฏซ้ำเป็นส่วนหนึ่งของ hashtag ที่ใช้บ่อย ซึ่งเป็น pattern
      ทั่วไปของบัญชีแบรนด์ (ใช้ branded-hashtag ของตัวเองซ้ำๆ) ต่างจาก KOL อิสระที่มักรีวิวหลาย
      แบรนด์สลับกันไป ดู docstring ของ is_likely_own_brand_account() สำหรับรายละเอียด
      บัญชีที่โดน flag จะถูกคัดออกจากผลลัพธ์ทั้งหมด (ไม่ใช่แค่หักคะแนน) เพราะ conflict of interest
"""

import argparse
import json
import math
import os
import re
import time
from typing import Any

import requests



EXCLUDED_TERMS = ["thailand"]

def is_excluded_account(kol: dict) -> bool:
    """Exclude likely official Thailand accounts."""
    username = str(kol.get("username","")).lower()
    nickname = str(kol.get("nickname", kol.get("display_name",""))).lower()
    return any(term in username or term in nickname for term in EXCLUDED_TERMS)

def filter_excluded_accounts(kols: list[dict]) -> list[dict]:
    return [k for k in kols if not is_excluded_account(k)]

def filter_results_to_dataset(results: list[dict], kols: list[dict]) -> list[dict]:
    """กรองผลลัพธ์ให้เหลือเฉพาะ KOL ที่อยู่ในชุดข้อมูลปัจจุบันจริง ๆ"""
    valid_usernames = {kol.get("username") for kol in kols if kol.get("username")}
    return [result for result in results if result.get("username") in valid_usernames]

EMBED_MODEL = "gemini-embedding-001"
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"
RATE_LIMIT_DELAY_SECS = 1.0  # หน่วงระหว่าง API call กัน rate limit

# ---------- Weight config (ปรับได้ตามที่ agency ต้องการ) ----------
WEIGHT_LIFESTYLE_SIM = 0.6      # ภายใน content_fit
WEIGHT_PRODUCT_SIM = 0.4        # ภายใน content_fit

# Final score ใช้แบบ "content_fit เป็นตัวคูณหลัก แล้ว engagement/tier เป็นตัวปรับ (modifier)"
# แทนการบวกกันตรงๆ (additive) — เหตุผล: ถ้าบวกกันตรงๆ candidate ที่ content ไม่เกี่ยวกับ
# แบรนด์เลยแต่ engagement/follower tier สูง จะสามารถ "ชดเชย" แซงหน้าคนที่ content ตรงกว่าได้
# ซึ่งขัดกับเป้าหมายธุรกิจ (ห้าม recommend KOL ที่ audience ไม่ตรงกลุ่มเป้าหมาย ต่อให้ metric ตัวอื่นดี)
# สูตร: final_score = content_fit * (BASE + w_engagement*engagement_score + w_tier*tier_score)
# ช่วงตัวคูณ modifier = [BASE, BASE + w_engagement + w_tier] = [0.85, 1.0]
# แปลว่า engagement/tier ปรับ score ได้สูงสุด ~15% เท่านั้น ไม่มีทางพลิกอันดับข้าม content_fit ที่ต่างกันมาก
CONTENT_FIT_MODIFIER_BASE = 0.85
WEIGHT_ENGAGEMENT_MODIFIER = 0.10
WEIGHT_TIER_MODIFIER = 0.05

# ---------- Shrinkage config สำหรับ engagement rate ----------
# ปัญหา: engagement_rate = engagements / follower_count เป็นสัดส่วนที่ยิ่ง follower_count
# น้อย ยิ่งมี "sample size" น้อย ทำให้ผันผวนสูงมาก (นักสถิติเรียกว่า small-sample noise)
# บัญชี 467 followers ที่ได้ engagement เพิ่มมาไม่กี่สิบครั้งก็ทำให้ % พุ่งเป็น 20%+ ได้ง่ายๆ
# ในขณะที่บัญชี 500,000 followers ต้องมี engagement เพิ่มขึ้นเป็นหมื่นถึงจะขยับ % เท่ากัน
# ถ้า normalize ตรงๆ บัญชีเล็กจะชนะ engagement_score เกือบทุกครั้งทั้งที่ไม่ได้ "เก่งจริง"
#
# วิธีแก้: ใช้ shrinkage / Bayesian-style estimator ดึงค่า engagement ของบัญชีที่ follower
# น้อยเข้าใกล้ค่าเฉลี่ยของทั้งกลุ่ม (population mean) ตามน้ำหนักของ follower_count เทียบกับ
# ค่าคงที่ K (สมมติว่า K = "follower เทียบเท่าที่ทำให้เราเริ่มเชื่อถือค่า engagement ของบัญชีนั้น")
# สูตร: shrunk_rate = (engagement_rate * follower_count + prior_mean * K) / (follower_count + K)
# - ถ้า follower_count >> K   -> shrunk_rate ≈ engagement_rate เดิม (เชื่อค่าจริงเกือบเต็มที่)
# - ถ้า follower_count << K   -> shrunk_rate ≈ prior_mean (ดึงเข้าค่ากลาง ลด noise)
ENGAGEMENT_SHRINKAGE_K = 20_000  # ปรับได้: ยิ่งสูง ยิ่ง "ไม่เชื่อ" บัญชีเล็กง่ายๆ

# ---------- Keyword overlap config (กัน embedding จับ category กว้างเกินไป) ----------
# ปัญหา: embedding similarity มองคำว่า "beauty" กว้างมาก ทำให้ makeup, skincare, haircare,
# spa ทั้งหมดอยู่ใกล้กันในเชิง semantic ทั้งที่ธุรกิจจริงต้องการเจาะจงแค่ sub-niche เดียว
# (เช่น สกินแคร์รักษาสิวสำหรับผิวแพ้ง่าย ไม่ใช่ makeup tutorial ทั่วไป)
#
# วิธีแก้: เสริม embedding ด้วยการเช็ค "keyword overlap" แบบ exact substring — ดูว่า keyword
# ของแบรนด์ (จาก keywords/product_keywords/lifestyle_keywords/sub_niche) ปรากฏอยู่จริงใน
# bio/hashtag/caption ของ KOL คนนั้นหรือไม่ ถ้าไม่มีเลยแม้แต่คำเดียว แสดงว่า content ที่
# ดูคล้ายกันในเชิง embedding อาจเป็นแค่ภาพลวงจาก category กว้างๆ ไม่ใช่ content ที่ตรงจริง
# จึงหัก content_fit ลงด้วย multiplier นี้ (ไม่ใช่ hard filter ตัดทิ้งเลย เพราะบาง KOL อาจ
# ใช้คำพ้องความหมายที่ไม่ตรงกับ keyword list เป๊ะๆ แต่เนื้อหาก็ยังตรงอยู่ได้)
KEYWORD_OVERLAP_PENALTY_MULTIPLIER = 0.75  # ปรับได้: ยิ่งต่ำ ยิ่งลงโทษแรงเมื่อไม่พบ keyword ตรงเป๊ะเลย

TIER_BOUNDS = [
    ("nano", 0, 10_000),
    ("micro", 10_000, 100_000),
    ("mid", 100_000, 500_000),
    ("macro", 500_000, float("inf")),
]

PRICE_TO_PREFERRED_TIERS = {
    "budget": ["nano", "micro"],
    "mid-range": ["micro", "mid"],
    "premium": ["mid", "macro"],
}


# ---------- Embedding via Gemini API ----------

def get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit(
            "ไม่พบ GEMINI_API_KEY ในตัวแปรสภาพแวดล้อม\n"
            "ตั้งค่าก่อนรัน เช่น:\n"
            "  Windows (PowerShell): $env:GEMINI_API_KEY=\"your-key\"\n"
            "  Mac/Linux:            export GEMINI_API_KEY=\"your-key\""
        )
    return key


def embed_text(text: str, api_key: str, task_type: str = "SEMANTIC_SIMILARITY") -> list[float]:
    """เรียก Gemini Embedding API สำหรับข้อความเดียว คืน dense vector
    task_type=SEMANTIC_SIMILARITY บอกโมเดลว่าจะเอา embedding นี้ไปเทียบความคล้ายกับข้อความอื่น
    โดยตรง (ไม่ใช่ retrieval/search) ทำให้ vector แยกความแตกต่างระหว่างเนื้อหาที่เกี่ยว/ไม่เกี่ยวได้ดีกว่า
    ถ้าไม่ระบุ task_type ค่า default ของโมเดลจะให้ similarity สูงเกินจริงระหว่างข้อความที่ไม่เกี่ยวกันเลย"""
    if not text or not text.strip():
        text = "ไม่มีข้อมูล"  # กัน error กรณี text ว่างเปล่า
    resp = requests.post(
        EMBED_URL,
        params={"key": api_key},
        json={
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
        },
        timeout=30,
    )
    resp.raise_for_status()
    time.sleep(RATE_LIMIT_DELAY_SECS)
    return resp.json()["embedding"]["values"]


# ---------- Pure-python vector math (ไม่พึ่ง numpy/scipy) ----------

def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def min_max_normalize(values: list) -> list[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return [0.0 for _ in values]
    lo, hi = min(clean), max(clean)
    if hi == lo:
        return [0.5 for _ in values]
    return [0.0 if v is None else (v - lo) / (hi - lo) for v in values]


def compute_shrunk_engagement(kols: list[dict]) -> list[float]:
    """คำนวณ engagement rate แบบ shrinkage เพื่อลด noise จากบัญชี follower น้อย

    ขั้นตอน:
    1. หา prior_mean = ค่าเฉลี่ย engagement_rate ถ่วงน้ำหนักด้วย follower_count
       (ใช้ weighted mean แทน simple mean เพราะไม่อยากให้บัญชีเล็กจำนวนมาก
       ดึงค่ากลางเพี้ยนไปจากพฤติกรรมจริงของ dataset)
    2. สำหรับแต่ละ KOL: shrunk = (rate*followers + prior_mean*K) / (followers + K)
    3. คืนค่า list ของ shrunk rate ตามลำดับเดิมของ kols (ไว้ normalize ต่อ)
    """
    valid = [
        (k.get("engagement_rate"), k.get("follower_count"))
        for k in kols
        if k.get("engagement_rate") is not None and k.get("follower_count")
    ]
    if not valid:
        return [0.0 for _ in kols]

    total_weighted = sum(rate * followers for rate, followers in valid)
    total_followers = sum(followers for _, followers in valid)
    prior_mean = total_weighted / total_followers if total_followers else 0.0

    shrunk = []
    for kol in kols:
        rate = kol.get("engagement_rate")
        followers = kol.get("follower_count")
        if rate is None or not followers:
            shrunk.append(prior_mean)
            continue
        shrunk_rate = (rate * followers + prior_mean * ENGAGEMENT_SHRINKAGE_K) / (
            followers + ENGAGEMENT_SHRINKAGE_K
        )
        shrunk.append(shrunk_rate)
    return shrunk


def get_follower_tier(follower_count) -> str:
    if not follower_count:
        return "unknown"
    for tier_name, low, high in TIER_BOUNDS:
        if low <= follower_count < high:
            return tier_name
    return "unknown"


def tier_fit_score(price_positioning: str, tier: str) -> float:
    preferred = PRICE_TO_PREFERRED_TIERS.get(price_positioning, [])
    if tier in preferred:
        return 1.0
    if tier == "unknown":
        return 0.3
    return 0.4


def build_brand_texts(brand: dict) -> tuple:
    # brand_tone (เช่น "น่าเชื่อถือเชิงวิชาการ") ใส่ไว้ในชุด lifestyle เพราะมันคือมิติ
    # "นำเสนอยังไง" เหมือน content_style_fit ไม่ใช่มิติ "ขายอะไร" แบบ product_keywords
    lifestyle_parts = (
        brand.get("lifestyle_keywords", [])
        + brand.get("content_style_fit", [])
        + [brand.get("brand_tone", "")]
    )
    product_parts = brand.get("product_keywords", []) + [
        brand.get("industry", ""), brand.get("sub_niche", "")
    ]
    lifestyle_text = " ".join(p for p in lifestyle_parts if p)
    product_text = " ".join(p for p in product_parts if p)
    return lifestyle_text, product_text


def build_kol_text(kol: dict) -> str:
    parts = [
        kol.get("bio", "") or "",
        " ".join(kol.get("top_hashtags_used", []) or []),
        " ".join((kol.get("recent_video_captions", []) or [])[:5]),
    ]
    return " ".join(p for p in parts if p)


def build_overlap_terms(brand: dict) -> list[str]:
    """รวบรวม keyword ทั้งหมดของแบรนด์ที่จะใช้เช็ค exact substring overlap กับข้อความ KOL
    (คนละชุดกับ all_brand_keywords ที่ใช้ทำ matched_reasons ผ่าน embedding — อันนี้เอาให้
    ครอบคลุมกว้างสุดเพื่อเช็คว่า KOL แตะประเด็นของแบรนด์บ้างหรือไม่ แม้แต่นิดเดียว)"""
    terms = []
    for key in ("keywords", "product_keywords", "lifestyle_keywords", "content_style_fit"):
        terms.extend(brand.get(key, []) or [])
    sub_niche = brand.get("sub_niche", "")
    if sub_niche:
        terms.append(sub_niche)
    return [t for t in terms if t]


def compute_keyword_overlap(kol_text: str, overlap_terms: list[str]) -> list[str]:
    """คืน list ของ term ที่ปรากฏจริง (exact substring, case-insensitive) ในข้อความ KOL
    ใช้ตัดสินว่าควรหัก content_fit ลงหรือไม่ (ดู KEYWORD_OVERLAP_PENALTY_MULTIPLIER ด้านบน)"""
    if not kol_text:
        return []
    text_lower = kol_text.lower()
    return [term for term in overlap_terms if term.lower() in text_lower]


def select_matched_reasons(kol_text: str, kw_sims: list[tuple], top_n: int = 3) -> list[str]:
    """เลือกเหตุผล match โดยให้ความสำคัญกับคำที่ 'พบจริง' ในข้อความ KOL ก่อนเสมอ
    (exact substring match) แล้วค่อยเติมด้วยอันดับ embedding similarity สูงสุดที่เหลือ
    เหตุผล: การใช้แค่ top-similarity ล้วนๆ เคยทำให้ reason ที่ให้มาไม่ตรงกับสิ่งที่ KOL
    โพสต์จริง (เช่น ขึ้น "เซรั่มลดสิว" ทั้งที่ KOL คนนั้นไม่เคยพูดถึงสิวเลยสักครั้ง)
    kw_sims ต้อง sort จาก similarity สูงสุดไปต่ำสุดมาก่อนแล้ว"""
    text_lower = (kol_text or "").lower()
    grounded = [kw for kw, _ in kw_sims if kw.lower() in text_lower]
    ungrounded = [kw for kw, _ in kw_sims if kw.lower() not in text_lower]
    return (grounded + ungrounded)[:top_n]


# ---------- Owned-brand account detection ----------
# ปัญหา: บางบัญชีใน dataset ไม่ใช่ influencer อิสระ แต่เป็นบัญชีของแบรนด์ (มักเป็นคู่แข่ง)
# ที่โพสต์โปรโมทสินค้าตัวเองเป็นหลัก เช่น @kindness.thailand ซึ่งเป็นบัญชีแบรนด์สกินแคร์
# "Kindness" เอง ไม่ใช่คนที่รับจ้างรีวิวสินค้าแบรนด์อื่น ถ้าเอามาแนะนำให้ลูกค้าจ้างรีวิว
# จะกลายเป็นแนะนำให้จ้างคู่แข่งพูดถึงแบรนด์ตัวเอง ซึ่งผิดวัตถุประสงค์เครื่องมือนี้โดยสิ้นเชิง
#
# สัญญาณเบื้องต้น: username ไปปรากฏซ้ำเป็นส่วนหนึ่งของ hashtag ที่ใช้บ่อย (เช่น username
# "kindness.thailand" ใช้ hashtag "kindnessskin" ซ้ำแทบทุกโพสต์) — แต่สัญญาณนี้เพียงอย่างเดียว
# "false positive สูงเกินไป" เพราะ creator อิสระจำนวนมาก (โดยเฉพาะ TikTok ไทย) ก็ใช้ชื่อ/แฮนเดิล
# ตัวเองเป็น signature hashtag เหมือนกัน (เช่น @aertha33 ใช้ #aertha, @aurora_myat ที่จริงคือ
# "Freelance Makeup Artist" ตัวจริง ใช้ #auroramyat เป็นแค่ลายเซ็นส่วนตัว)
#
# จึงต้องมี "สัญญาณยืนยันที่สอง" (corroborating signal) ควบคู่กันถึงจะ auto-exclude:
#   - username มีคำว่า "official" (เช่น cosmedi_official)
#   - bio มีคำว่า "บริษัท" หรือ "official" ที่สื่อว่าเป็นช่องทางการของแบรนด์
#   - bio มีอีเมลติดต่องานแบบ sales@<ชื่อแบรนด์> ที่ตรงกับ username/hashtag (เช่น shobbeauty_th)
# ถ้าเจอแค่ username↔hashtag ตรงกันอย่างเดียว (ไม่มีสัญญาณที่สอง) จะ "flag ไว้เฉยๆ" ไม่ตัดออก
# เพราะ text อย่างเดียวฟันธงไม่ได้เสมอไป (กรณี kindness.thailand เองก็ต้องดูวิดีโอจริงถึงจะชัวร์)
OWN_BRAND_MIN_STEM_LENGTH = 4  # กันคำสั้นเกินไป (เช่น "aa") ที่จะ false positive ง่าย
# หมายเหตุ: ไม่เช็คคำว่า "official" ใน bio เพราะบางคนใส่ contact handle ของคนอื่นที่มีคำว่า
# official ปน (เช่น "For Work Line @Aertha.official") ซึ่งไม่ได้แปลว่าเจ้าของบัญชีเป็นบริษัทเอง
# เช็คแค่ username ตัวเองเท่านั้นว่ามี "official" ต่อท้ายหรือไม่ (เช่น cosmedi_official)
OWN_BRAND_BIO_SIGNALS = ["บริษัท", "sales@"]


def _extract_username_stem(username: str) -> str:
    """ตัด username เอาเฉพาะส่วนแรกก่อนตัวคั่นทั่วไป (., _, ตัวเลข) เพื่อใช้เทียบกับ hashtag
    เช่น 'kindness.thailand' -> 'kindness', 'natkrittao' -> 'natkrittao'"""
    if not username:
        return ""
    stem = re.split(r"[.\d_]", username, maxsplit=1)[0]
    return stem.lower()


def is_likely_own_brand_account(kol: dict) -> tuple[bool, bool, str]:
    """เช็คว่า KOL คนนี้น่าจะเป็นบัญชีแบรนด์เอง (ไม่ใช่ influencer อิสระ) หรือไม่
    คืนค่า (should_exclude, should_flag_for_review, matched_hashtag)
    - should_exclude=True: เจอสัญญาณ 2 ชั้น (hashtag ตรง + bio ยืนยันชัดเจน) มั่นใจพอจะคัดออกอัตโนมัติ
    - should_flag_for_review=True: เจอแค่ hashtag↔username ตรงกันอย่างเดียว ไม่มั่นใจพอจะคัดออกเอง
      แต่ควรให้คนตรวจสอบก่อนส่งให้ลูกค้า"""
    stem = _extract_username_stem(kol.get("username", ""))
    username_lower = (kol.get("username", "") or "").lower()
    bio_lower = (kol.get("bio", "") or "").lower()

    if len(stem) < OWN_BRAND_MIN_STEM_LENGTH:
        return False, False, ""

    hashtags = kol.get("top_hashtags_used", []) or []
    matched_tag = ""
    for tag in hashtags:
        if stem in tag.lower():
            matched_tag = tag
            break

    if not matched_tag:
        return False, False, ""

    has_bio_signal = "official" in username_lower or any(
        signal in bio_lower for signal in OWN_BRAND_BIO_SIGNALS
    )
    if has_bio_signal:
        return True, False, matched_tag
    return False, True, matched_tag


def run_matching(brand: dict, kols: list, api_key: str, top_n: int = 15):
    # คัดบัญชีที่มั่นใจว่าเป็น owned-brand account ออกก่อนเรียก embedding API เลย
    # (ประหยัด API call) ส่วนที่ไม่มั่นใจพอ (สัญญาณเดียว) จะปล่อยผ่านแต่ติด flag ไว้ในผลลัพธ์
    filtered_kols = []
    excluded = []
    flagged_ids = {}
    for kol in kols:
        should_exclude, should_flag, matched_tag = is_likely_own_brand_account(kol)
        if should_exclude:
            excluded.append((kol.get("username"), matched_tag))
            continue
        if should_flag:
            flagged_ids[kol.get("username")] = matched_tag
        filtered_kols.append(kol)

    if excluded:
        print(f"ตัดบัญชีที่มั่นใจว่าเป็น owned-brand account ออก {len(excluded)} บัญชี "
              f"(มี username↔hashtag ตรงกัน + สัญญาณยืนยันใน bio):")
        for username, tag in excluded:
            print(f"  - @{username} (hashtag '#{tag}')")
        print()
    if flagged_ids:
        print(f"พบ {len(flagged_ids)} บัญชีที่ username↔hashtag ตรงกัน แต่ไม่มีสัญญาณยืนยันชัดพอ "
              f"จะคัดออกอัตโนมัติ — ยังอยู่ใน ranking แต่ติด flag 'possible_own_brand' ไว้ให้ตรวจสอบเอง:")
        for username, tag in flagged_ids.items():
            print(f"  - @{username} (hashtag '#{tag}')")
        print()

    kols = filtered_kols

    lifestyle_text, product_text = build_brand_texts(brand)
    print("กำลัง embed ข้อมูลแบรนด์...")
    lifestyle_emb = embed_text(lifestyle_text, api_key)
    product_emb = embed_text(product_text, api_key)

    # precompute embedding ของ keyword แต่ละคำไว้ล่วงหน้า (ใช้ทำ 'เหตุผล match' โดยไม่ต้อง
    # เรียก API ซ้ำต่อ KOL แต่ละคน — ประหยัด call และเวลา)
    all_brand_keywords = brand.get("lifestyle_keywords", []) + brand.get("product_keywords", [])
    print(f"กำลัง embed brand keywords ({len(all_brand_keywords)} คำ)...")
    keyword_embs = {kw: embed_text(kw, api_key) for kw in all_brand_keywords}

    print(f"กำลัง embed ข้อมูล KOL ({len(kols)} คน)...")
    kol_embs = []
    kol_texts = []
    for i, kol in enumerate(kols, 1):
        text = build_kol_text(kol)
        kol_texts.append(text)
        kol_embs.append(embed_text(text, api_key))
        print(f"  [{i}/{len(kols)}] @{kol.get('username')} embedded")

    # engagement: shrink ก่อน แล้วค่อย min-max normalize (แทนการ normalize ค่า raw ตรงๆ)
    shrunk_rates = compute_shrunk_engagement(kols)
    engagement_norm = min_max_normalize(shrunk_rates)

    overlap_terms = build_overlap_terms(brand)
    price_positioning = brand.get("price_positioning", "")

    results = []
    for kol, kol_emb, kol_text, eng_score, shrunk_rate in zip(
        kols, kol_embs, kol_texts, engagement_norm, shrunk_rates
    ):
        sim_lifestyle = cosine_sim(kol_emb, lifestyle_emb)
        sim_product = cosine_sim(kol_emb, product_emb)
        content_fit = WEIGHT_LIFESTYLE_SIM * sim_lifestyle + WEIGHT_PRODUCT_SIM * sim_product

        # keyword overlap check: ถ้าไม่มี keyword ของแบรนด์ปรากฏจริงในข้อความ KOL เลย
        # แม้แต่คำเดียว ให้หัก content_fit ลง กัน embedding หลอกจาก category กว้างๆ
        overlap_matches = compute_keyword_overlap(kol_text, overlap_terms)
        overlap_multiplier = 1.0 if overlap_matches else KEYWORD_OVERLAP_PENALTY_MULTIPLIER
        content_fit_adjusted = content_fit * overlap_multiplier

        tier = get_follower_tier(kol.get("follower_count"))
        tier_score = tier_fit_score(price_positioning, tier)

        engagement_modifier = WEIGHT_ENGAGEMENT_MODIFIER * eng_score
        tier_modifier = WEIGHT_TIER_MODIFIER * tier_score
        final_score = content_fit_adjusted * (CONTENT_FIT_MODIFIER_BASE + engagement_modifier + tier_modifier)

        kw_sims = [(kw, cosine_sim(kol_emb, emb)) for kw, emb in keyword_embs.items()]
        kw_sims.sort(key=lambda x: x[1], reverse=True)
        reasons = select_matched_reasons(kol_text, kw_sims, top_n=3)

        results.append({
            "username": kol.get("username"),
            "profile_url": kol.get("profile_url") or f"https://www.tiktok.com/@{kol.get('username')}",
            "follower_count": kol.get("follower_count"),
            "follower_tier": tier,
            "engagement_rate": kol.get("engagement_rate"),
            "final_score": round(final_score, 4),
            "possible_own_brand_account": kol.get("username") in flagged_ids,
            "score_breakdown": {
                "content_fit": round(content_fit, 4),
                "content_fit_adjusted": round(content_fit_adjusted, 4),
                "keyword_overlap_matches": overlap_matches,
                "keyword_overlap_multiplier": overlap_multiplier,
                "sim_lifestyle": round(sim_lifestyle, 4),
                "sim_product": round(sim_product, 4),
                "engagement_rate_shrunk": round(shrunk_rate, 5),
                "engagement_score": round(eng_score, 4),
                "tier_fit_score": round(tier_score, 4),
                "modifier_multiplier": round(CONTENT_FIT_MODIFIER_BASE + engagement_modifier + tier_modifier, 4),
            },
            "matched_reasons": reasons,
        })

    results.sort(key=lambda r: r["final_score"], reverse=True)
    excluded_own_brand_accounts = [
        {"username": username, "matched_hashtag": tag} for username, tag in excluded
    ]
    return results[:top_n], excluded_own_brand_accounts


def load_json_file(path: str, label: str):
    """อ่านไฟล์ JSON แบบทนทาน: กัน BOM (encoding utf-8-sig), เช็คไฟล์ว่าง,
    และแจ้ง error ชัดเจนถ้า parse ไม่ผ่าน แทนที่จะโยน traceback ยาวๆ ใส่ user"""
    if not os.path.exists(path):
        raise SystemExit(f"ไม่พบไฟล์ {label}: {path}")

    with open(path, encoding="utf-8-sig") as f:
        raw = f.read()

    if not raw.strip():
        raise SystemExit(f"ไฟล์ {label} ({path}) ว่างเปล่า — ตรวจสอบว่า save ข้อมูลลงไปจริงหรือยัง")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"ไฟล์ {label} ({path}) ไม่ใช่ JSON ที่ถูกต้อง: {e}\n"
            f"บรรทัดแรกของไฟล์คือ: {raw.splitlines()[0][:100] if raw.splitlines() else '(ว่าง)'}"
        )


def main():
    parser = argparse.ArgumentParser(description="TikTok KOL Matching Engine (Gemini Embedding API)")
    parser.add_argument("--brand", required=True, help="path to brand_profile.json")
    parser.add_argument("--kols", required=True, help="path to kol_dataset.json (array of KOL records)")
    parser.add_argument("--top", type=int, default=15, help="how many results to output")
    parser.add_argument("--out", default="ranked_kols.json", help="output file path")
    args = parser.parse_args()

    api_key = get_api_key()

    brand = load_json_file(args.brand, "brand profile")
    kols = load_json_file(args.kols, "KOL dataset")

    # n8n export ข้อมูลออกมาเป็น array ของ item เสมอ แม้จะมีแค่ brand เดียว
    # เช่น [{...}] แทนที่จะเป็น {...} ตรงๆ — unwrap ให้อัตโนมัติกันต้องแก้ไฟล์เอง
    if isinstance(brand, list):
        if len(brand) == 0:
            raise SystemExit("ไฟล์ brand profile เป็น array ว่างเปล่า")
        if len(brand) > 1:
            print(f"หมายเหตุ: ไฟล์ brand profile มี {len(brand)} record จะใช้ record แรก (index 0)")
        brand = brand[0]

    if not isinstance(brand, dict):
        raise SystemExit("ไฟล์ brand profile ต้องเป็น object หรือ array ที่มี object อยู่ข้างใน")
    if not isinstance(kols, list):
        raise SystemExit("ไฟล์ KOL dataset ต้องเป็น array ของ KOL records")

    ranked, excluded_own_brand = run_matching(brand, kols, api_key, top_n=args.top)
    ranked = filter_results_to_dataset(ranked, kols)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(ranked, f, ensure_ascii=False, indent=2)

    # เขียน excluded_own_brand ลงไฟล์แยกด้วย (ไม่ใช่แค่ print ออก console) เพราะเวลารันผ่าน
    # n8n/automation จะไม่มีใครเห็น stdout — ต้องมีไฟล์ให้ตรวจสอบย้อนหลังได้ว่าตัดใครออกไปบ้างทำไม
    excluded_path = args.out.rsplit(".", 1)[0] + ".excluded_own_brand.json"
    if excluded_own_brand:
        with open(excluded_path, "w", encoding="utf-8") as f:
            json.dump(excluded_own_brand, f, ensure_ascii=False, indent=2)

    print(f"\n=== Top {len(ranked)} KOL matches for '{brand.get('page_name', '?')}' ===\n")
    for i, r in enumerate(ranked, 1):
        flag_note = "  ⚠️ possible_own_brand_account — ตรวจสอบก่อนแนะนำ" if r.get("possible_own_brand_account") else ""
        print(f"{i}. @{r['username']}  (score={r['final_score']})  {r['profile_url']}{flag_note}")
        print(f"   followers={r['follower_count']} ({r['follower_tier']})  "
              f"engagement_rate={r['engagement_rate']}")
        print(f"   เหตุผลที่แมตช์: {', '.join(r['matched_reasons'])}")
        print()

    print(f"บันทึกผลลัพธ์เต็มที่: {args.out}")
    if excluded_own_brand:
        print(f"บันทึกรายชื่อที่ถูกคัดออกเพราะน่าจะเป็น owned-brand account: {excluded_path}")


if __name__ == "__main__":
    main()