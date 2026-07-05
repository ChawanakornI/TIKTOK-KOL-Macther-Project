"""ลบ KOL ที่ username ซ้ำออกจากไฟล์ kol_dataset.json (เก็บ record แรกที่เจอไว้)"""
import json
import sys

def dedupe(path, out_path=None):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    seen = set()
    deduped = []
    for record in data:
        username = record.get('username')
        if username in seen:
            continue
        seen.add(username)
        deduped.append(record)

    out_path = out_path or path
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    print(f"เดิม {len(data)} รายการ -> เหลือ {len(deduped)} รายการ (ลบซ้ำ {len(data) - len(deduped)} รายการ)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("วิธีใช้: python dedupe_kol.py kol_dataset.json")
        sys.exit(1)
    dedupe(sys.argv[1])
