# TikTok KOL Matching

โปรเจกต์นี้ใช้ Gemini Embedding API เพื่อจับคู่แบรนด์กับ KOL ที่เหมาะสมตามความสอดคล้องของเนื้อหาและพฤติกรรมผู้ติดตาม

## ข้อกำหนดระบบ
- Python 3.9+
- Internet connection สำหรับเรียก Gemini API

## ติดตั้ง dependency
```bash
pip install -r requirements.txt
```

## ตั้งค่า Gemini API Key
อย่าลืมตั้งค่า API key ก่อนรันทุกครั้ง เพราะโปรแกรมต้องเรียก Gemini Embedding API

### Windows (PowerShell)
```powershell
$env:GEMINI_API_KEY="your-api-key"
```

### macOS / Linux
```bash
export GEMINI_API_KEY="your-api-key"
```

> ถ้าต้องการให้คีย์มีผลใน session เดียวกันเท่านั้น ให้ใช้คำสั่งด้านบน หากต้องการให้คีย์อยู่ตลอดไปใน Windows ให้ใช้คำสั่งแบบถาวรใน PowerShell:
```powershell
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your-api-key", "User")
```

## วิธีใช้
### 1) เตรียมไฟล์จาก n8n
จาก n8n ให้เอาไฟล์ JSON ที่ได้จาก node ต่าง ๆ ไปวางในโฟลเดอร์นี้:

- `brand_profile.json` : เอา output จาก node ที่สร้าง/ประมวลผล brand profile มาใส่
- `kol_dataset.json` : เอา output จาก node ที่ scrape / build KOL dataset มาใส่

### 2) ตรวจสอบข้อมูลในไฟล์ brand profile
ไฟล์ `brand_profile.json` ควรมีข้อมูลต่อไปนี้อย่างน้อย:
- `page_name`
- `industry`
- `sub_niche`
- `product_keywords`
- `lifestyle_keywords`
- `content_style_fit`
- `price_positioning`
- `website_url` หรือ `facebook_url`

ถ้าต้องการให้โปรแกรมใช้ข้อมูลเว็บไซต์หรือ Facebook page ของแบรนด์ ให้แน่ใจว่าในไฟล์มี field เช่น:
- `website_url`
- `facebook_url`

### 3) รันแบบพื้นฐาน
```bash
python matching_engine.py --brand brand_profile.json --kols kol_dataset.json --top 15
```

### 4) ถ้าต้องการรันต่อจาก n8n ให้ใช้คำสั่งนี้
```bash
python matching_engine.py --brand brand_profile.json --kols kol_dataset.json --top 15 --out ranked_kols.json
```

### 5) ตัวเลือกเพิ่มเติม
```bash
python matching_engine.py --brand brand_profile.json --kols kol_dataset.json --top 15 --out ranked_kols.json
```

- `--brand` : ไฟล์โปรไฟล์แบรนด์
- `--kols` : ไฟล์ข้อมูล KOL
- `--top` : จำนวน KOL ที่จะแสดงในผลลัพธ์
- `--out` : ไฟล์ JSON ที่ใช้เก็บผลลัพธ์

### 5) Workflow จาก n8n แบบสั้น
1. จาก node build profile parse ให้เอา output มาใส่ที่ `brand_profile.json`
2. จาก node ที่โหลด KOL dataset ให้เอา output มาใส่ที่ `kol_dataset.json`
3. ก่อนรัน matching ให้ลบ KOL ที่ซ้ำออกด้วยคำสั่ง:
```bash
python dedupe_kol.py kol_dataset.json
```
4. รอให้ไฟล์ถูกโหลดครบแล้วค่อยรันคำสั่งด้านบน
5. ผลลัพธ์จะถูกสร้างเป็น `ranked_kols.json`

## ปรับ parameter
คุณสามารถปรับพฤติกรรมของตัวจัดอันดับได้โดยแก้ค่าตัวแปรด้านบนในไฟล์ `matching_engine.py`:

```python
WEIGHT_LIFESTYLE_SIM = 0.6
WEIGHT_PRODUCT_SIM = 0.4
CONTENT_FIT_MODIFIER_BASE = 0.85
WEIGHT_ENGAGEMENT_MODIFIER = 0.10
WEIGHT_TIER_MODIFIER = 0.05
```

### คำอธิบายสั้น
- `WEIGHT_LIFESTYLE_SIM` : น้ำหนักความเหมาะสมของ lifestyle
- `WEIGHT_PRODUCT_SIM` : น้ำหนักความเหมาะสมของ product
- `CONTENT_FIT_MODIFIER_BASE` : ค่าพื้นฐานของคะแนนก่อนปรับด้วย engagement/tier
- `WEIGHT_ENGAGEMENT_MODIFIER` : น้ำหนักของ engagement rate
- `WEIGHT_TIER_MODIFIER` : น้ำหนักของ follower tier

### ตัวอย่างการปรับให้เน้น engagement มากขึ้น
```python
WEIGHT_ENGAGEMENT_MODIFIER = 0.20
WEIGHT_TIER_MODIFIER = 0.10
```

### ตัวอย่างการปรับให้เน้นความตรงกับแบรนด์มากขึ้น
```python
WEIGHT_LIFESTYLE_SIM = 0.7
WEIGHT_PRODUCT_SIM = 0.3
```

## ผลลัพธ์ที่ได้
โปรแกรมจะสร้างไฟล์ JSON ที่มีรายการ KOL ที่ถูกจัดอันดับจากความเหมาะสมสูงสุด พร้อมคะแนนและเหตุผลที่แมตช์

## โครงสร้างไฟล์หลัก
- `matching_engine.py` : ตัวจัดอันดับ KOL
- `brand_profile.json` : โปรไฟล์แบรนด์
- `kol_dataset.json` : ข้อมูล KOL
- `ranked_kols.json` : ผลลัพธ์ที่ถูกสร้างขึ้น
