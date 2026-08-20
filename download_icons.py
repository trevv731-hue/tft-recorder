import os
import urllib.request
import time

ICON_DIR = r"D:\用户\trevv\桌面\tft_record\icons"
os.makedirs(ICON_DIR, exist_ok=True)

# S18 英雄列表
CHAMPS = [
    # 1费
    "Akali","Camille","Cinderling","Karma","Kobuko","Leona","Ornn","Pebbles","Rakan","RekSai","Varus","Veigar","Xayah","Yorick",
    # 2费
    "Alistar","Caitlyn","Elise","Gromp","Kayle","LeBlanc","Murkwolf","Scuttlecrab","Sejuani","Shen","Teemo","Warwick","Yunara",
    # 3费
    "Azir","Cassiopeia","Diana","Fiddlesticks","Hecarim","KhaZix","KogMaw","Krug","MasterYi","Rammus","Raptor","Rengar","Tristana","Vi",
    # 4费
    "Ahri","Amumu","AncientSentinel","Aphelios","Brambleback","Ezreal","Lillia","Malphite","Morgana","Nidalee","Sett","Sivir","Soraka","Zyra",
    # 5费
    "Alune","Ashe","Draven","ElderDragon","Gnar","Ivern","Kennen","Lux","Maokai","Taric",
]

# TFT英雄ID到LOL英雄ID的映射（TFT专属英雄没有对应LOL英雄）
TFT_TO_LOL = {
    "Cinderling": None, "Kobuko": None, "Pebbles": None,
    "Gromp": None, "Murkwolf": None, "Scuttlecrab": None, "Yunara": None,
    "Krug": None, "Raptor": None,
    "AncientSentinel": None, "Brambleback": None,
    "ElderDragon": None,
}

def download_champ(champ):
    path = os.path.join(ICON_DIR, f"{champ}.png")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return True
    
    lol_id = TFT_TO_LOL.get(champ, champ)
    
    urls = []
    if lol_id:
        # Data Dragon LOL英雄头像
        urls.append(f"https://ddragon.leagueoflegends.com/cdn/14.20.1/img/champion/{lol_id}.png")
        urls.append(f"https://ddragon.leagueoflegends.com/cdn/14.19.1/img/champion/{lol_id}.png")
    
    # Community Dragon TFT头像
    urls.append(f"https://raw.communitydragon.org/latest/game/assets/characters/{champ.lower()}/hud/{champ.lower()}_square.png")
    urls.append(f"https://raw.communitydragon.org/latest/game/assets/characters/{champ.lower()}/hud/icons/{champ.lower()}.png")
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                if len(data) > 1000:
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"✓ {champ} ({len(data)} bytes)")
                    return True
        except Exception as e:
            continue
    
    print(f"✗ {champ} 下载失败")
    return False

success = 0
fail = 0
for champ in CHAMPS:
    if download_champ(champ):
        success += 1
    else:
        fail += 1
    time.sleep(0.15)

print(f"\n完成: 成功{success}个, 失败{fail}个")
