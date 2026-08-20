import os
from PIL import Image, ImageDraw, ImageFont

ICON_DIR = r"D:\用户\trevv\桌面\tft_record\icons"

# 失败的英雄及其费用
FAILED_CHAMPS = {
    "Cinderling": 1, "Kobuko": 1, "Pebbles": 1,
    "Gromp": 2, "LeBlanc": 2, "Murkwolf": 2, "Scuttlecrab": 2, "Yunara": 2,
    "Krug": 3, "Raptor": 3,
    "AncientSentinel": 4, "Brambleback": 4,
    "Alune": 5, "ElderDragon": 5,
}

COST_COLORS = {
    1: (156, 163, 175),  # 灰
    2: (34, 197, 94),    # 绿
    3: (59, 130, 246),   # 蓝
    4: (168, 85, 247),   # 紫
    5: (245, 158, 11),   # 金
}

for champ, cost in FAILED_CHAMPS.items():
    path = os.path.join(ICON_DIR, f"{champ}.png")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        continue
    
    color = COST_COLORS[cost]
    img = Image.new("RGBA", (64, 64), color + (255,))
    draw = ImageDraw.Draw(img)
    
    # 画费用数字
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        font = ImageFont.load_default()
    
    text = str(cost)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((64-tw)//2, (64-th)//2 - 4), text, fill=(255,255,255,255), font=font)
    
    # 画英雄名缩写
    short = champ[:3]
    try:
        font2 = ImageFont.truetype("arial.ttf", 10)
    except:
        font2 = ImageFont.load_default()
    bbox2 = draw.textbbox((0, 0), short, font=font2)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((64-tw2)//2, 48), short, fill=(255,255,255,200), font=font2)
    
    img.save(path)
    print(f"✓ 创建占位符: {champ} ({cost}费)")

print("\n完成!")
