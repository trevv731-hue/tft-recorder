# -*- coding: utf-8 -*-
"""
TFT Set 18 海克斯强化评级数据
来源: https://www.datatft.com/augment/tier
评级: S / A / B / C / D
阶段: 2-1 / 3-2 / 4-2 (部分海克斯仅在特定阶段出现)
"""

# 评级定义
TIER_COLORS = {
    "S": "#ff453a",  # 红
    "A": "#ff9f0a",  # 橙
    "B": "#ffd60a",  # 黄
    "C": "#30d158",  # 绿
    "D": "#8e8e93",  # 灰
}

TIER_DESC = {
    "S": "极强，大部分对局都适合拿",
    "A": "强，但需要特定阵容/装备配合",
    "B": "稳定选择，适合保命或过渡",
    "C": "仅特定场景有用",
    "D": "99%的局不要拿，除非硬赌",
}

# 2-1 阶段海克斯评级
AUGMENTS_2_1 = {
    # S
    "Expedition": "S", "Restart Mission": "S", "Dummify": "S", "Slightly Magic Roll": "S",
    # A
    "Latent Forge": "A", "Late Game Specialist": "A", "Caretaker's Ally": "A", "On a Roll": "A",
    "AFK": "A", "Group Hug I": "A", "Pandora's Items": "A", "Makeshift Armor I": "A",
    "Branching Out+": "A", "Band of Thieves": "A", "Silver Spoon": "A",
    # B
    "Charge Transfer I": "B", "Missed Connections": "B", "Twin Guardians": "B",
    "Size Matters": "B", "Augmented Power": "B", "Bonk!": "B", "Termeepnal Velocity": "B",
    "Stellar Combo": "B", "One Two Three": "B", "Kick Start": "B", "Small Grab Bag": "B",
    "Continuous Conjuration": "B", "Carve a Path": "B", "Exiles I": "B", "Feeling Lucky": "B",
    "Boxing Lessons": "B", "Glass Cannon I": "B", "Electrocharge I": "B", "Healing Orbs I": "B",
    "Patience is a Virtue": "B", "Branching Out": "B", "Partial Ascension": "B",
    "Forge a Friend": "B", "Item Grab Bag": "B", "One, Two, Five!": "B", "Team Building": "B",
    "Corrosion": "B", "Cognitive Tax": "B", "Cognitive Tax+": "B", "Iron Assets": "B",
    # C
    "Shieldmaiden": "C", "Find Your Center": "C", "Rolling For Days I": "C", "Risky Moves": "C",
    "Second Wind": "C", "Flowing Tears": "C", "Lineup": "C", "Good For Something I": "C",
    "Focused Fire": "C", "Teaming Up": "C", "Lunch Money": "C", "Tiny Titans": "C",
    "Backup Bows": "C", "Climb The Ladder I": "C", "Best Friends I": "C", "Stand United": "C",
    "Crafted Crafting": "C", "The Tower": "C", "Vampiric Vitality I": "C",
    # D
    "Slice of Life": "D", "Recombobulator": "D", "Survivor": "D",
}

# 3-2 阶段海克斯评级
AUGMENTS_3_2 = {
    # S
    "Early Learnings": "S", "Treasure Hunt": "S", "Tactician's Kitchen": "S",
    "The Trait Tree": "S", "The Trait Tree+": "S",
    # A
    "NO SCOUT NO PIVOT": "A", "Portable Forge": "A", "Reach for the Stars": "A",
    "Booster Pack++": "A", "Birthday Reunion": "A", "Spreading Roots+": "A",
    "The Big Bang": "A", "Self Destruct": "A", "Epic Rolldown": "A",
    "Forward Thinking": "A", "Swordsmith": "A", "Duo Queue": "A", "Big Grab Bag": "A",
    "Little Buddies": "A", "Calculated Loss": "A", "Cosmic Restart": "A",
    "Staffsmith": "A", "Urf's Gambit": "A", "Explosive Growth": "A", "Explosive Growth+": "A",
    "Warlord's Honor": "A", "Patient Study": "A", "Money Hungry": "A", "Woven Magic": "A",
    # B
    "Savings Account": "B", "Two Tanky": "B", "Booster Pack": "B", "Booster Pack+": "B",
    "Spreading Roots": "B", "Misfits": "B", "Heat Death": "B", "Concentration": "B",
    "Trade Sector": "B", "Legion of Threes": "B", "Exclusive Customization": "B",
    "Care Package": "B", "Bodyguard Training": "B", "Frontline Foundation": "B",
    "Solo Plate": "B", "Arcane Viktor-y": "B", "Replication": "B", "Late Game Scaling": "B",
    "Plot Armor": "B", "Heart of Steel": "B", "Warpath": "B", "Epoch": "B",
    "Group Hug II": "B", "Epoch+": "B", "Sunfire Board": "B", "Healing Orbs II": "B",
    "Cry Me A River": "B", "Clear Mind": "B", "Slammin'": "B", "Slammin'+": "B",
    "Exiles II": "B", "Glass Cannon II": "B", "Heavy Is the Crown": "B",
    "Crash Test Dummies": "B", "Apotheotic Forge": "B", "Cluttered Mind": "B",
    "Kahunahuna": "B", "Gain 21 Gold": "B", "Gilded Steel": "B",
    "Advanced Loan": "B", "Advanced Loan+": "B", "A Magic Roll": "B", "Contract Killer": "B",
    "U.R.F": "B", "ReinFOURcement": "B", "Indiscriminate Killer": "B",
    "Seraphim's Staff": "B", "Heroic Grab Bag+": "B", "Heroic Grab Bag++": "B",
    "Prizefighter": "B", "Climb The Ladder II": "B",
    # C
    "Tour of the Galaxy": "C", "Timestream": "C", "Infinity Protection": "C",
    "Charge Transfer II": "C", "Backline Blueprint": "C", "Clockwork Accelerator": "C",
    "Malicious Monetization": "C", "Salvage Bin": "C", "Salvage Bin+": "C",
    "Spirit of Redemption": "C", "Anima Commander": "C", "May the Fours Be With You": "C",
    "Speedy Double Kill": "C", "Loot Singularity": "C", "Side Effects": "C",
    "Second Wind II": "C", "Makeshift Armor II": "C", "Tons of Stats!": "C",
    "Best Friends II": "C", "Mace's Will": "C", "Cybernetic Uplink": "C",
    "Cybernetic Implants": "C", "Pandora's Items II": "C", "Feed the Flames": "C",
    "Electrocharge II": "C", "Heroic Grab Bag": "C", "Cognitive Overload": "C",
    "Ascension": "C", "Aura Farming": "C", "Pilfer": "C", "Jeweled Lotus I": "C",
    "Bronze For Life I": "C",
    # D
    "Divine Amendment": "D", "High Voltage": "D", "Trifecta I": "D",
    "Worth the Wait": "D", "You Have My Bow": "D", "Solo Leveling": "D",
    "Hustler": "D", "Blood Offering": "D",
}

# 4-2 阶段海克斯评级
AUGMENTS_4_2 = {
    # S
    "Tactician's Kitchen": "S", "The Trait Tree": "S", "The Trait Tree+": "S",
    # A
    "Wise Spending": "A", "Forged in Strength": "A", "Flexible": "A",
    "Hold the Line": "A", "An Exalted Adventure": "A", "Money Monsoon": "A",
    "Call to Chaos": "A", "Deadlier Caps": "A", "Commerce Core": "A",
    # B
    "Living Forge": "B", "Baron's Lair": "B", "One Buff, Two Buff": "B",
    "Upward Mobility": "B", "Hedge Fund+": "B", "Hedge Fund": "B",
    "Wand Overflow": "B", "Heart of the Swarm": "B", "Radiant Rascal": "B",
    "Sword Overflow": "B", "Luxury Subscription": "B", "Lucky Gloves+": "B",
    "Expected Unexpectedness": "B", "Invested+": "B", "Invested++": "B",
    "Prismatic Ticket": "B", "Pandora's Items III": "B", "Buried Treasures": "B",
    "Band of Thieves II": "B", "Band of Thieves II+": "B", "Band of Thieves II++": "B",
    "Comeback Story": "B", "Belt Overflow": "B", "Shimmerscale Essence": "B",
    "Golden Gamble": "B", "Golden Gamble+": "B", "Golden Gamble++": "B",
    "Urf's Grab Bag": "B", "Deadlier Blades": "B", "Exclusive Customization II": "B",
    "Min-Max": "B", "Worth the Wait II": "B", "Tiniest Titan": "B", "Cursed Crown": "B",
    # C
    "Level Up!": "C", "Giant and Mighty": "C", "New Recruit": "C",
    "We Stick Together": "C", "Birthday Present": "C", "Hard Commit": "C",
    "Tiny, but Deadly": "C", "Construct a Companion": "C", "Build a Bud": "C",
    "Retribution": "C", "Soul Awakening": "C", "Sweet Treats": "C",
    "Going Long": "C", "At What Cost": "C", "Bronze For Life II": "C",
    # D
    "Lucky Gloves": "D", "Win Out": "D", "Component Heist": "D",
    "The Golden Egg": "D", "Trifecta II": "D", "Jeweled Lotus II": "D",
    "Subscription Service": "D",
}

# 中文海克斯名称 → 英文名称 映射 (国服/中文界面用)
CN_TO_EN = {
    # S tier
    "远征": "Expedition", "重新开始任务": "Restart Mission", "重启任务": "Restart Mission",
    "傻瓜化": "Dummify", "傀儡化": "Dummify", "轻量魔法投掷": "Slightly Magic Roll",
    "轻微魔法掷骰": "Slightly Magic Roll", "早期学习": "Early Learnings", "寻宝": "Treasure Hunt",
    "战术家的厨房": "Tactician's Kitchen", "羁绊之树": "The Trait Tree", "羁绊之树+": "The Trait Tree+",
    # A tier
    "潜在锻造": "Latent Forge", "后期专家": "Late Game Specialist", "守护者盟友": "Caretaker's Ally",
    "顺风顺水": "On a Roll", "连战连胜": "On a Roll", "挂机": "AFK", "集体拥抱 I": "Group Hug I",
    "潘多拉的装备": "Pandora's Items", "临时护甲 I": "Makeshift Armor I", "节外生枝+": "Branching Out+",
    "盗贼团伙": "Band of Thieves", "银勺": "Silver Spoon", "不侦察不转型": "NO SCOUT NO PIVOT",
    "便携式锻造台": "Portable Forge", "摘星": "Reach for the Stars", "大爆炸": "The Big Bang",
    "自毁": "Self Destruct", "史诗级刷新": "Epic Rolldown", "前瞻性思维": "Forward Thinking",
    "铸剑师": "Swordsmith", "双排": "Duo Queue", "大礼包": "Big Grab Bag", "小伙伴": "Little Buddies",
    "算计失败": "Calculated Loss", "宇宙重启": "Cosmic Restart", "法杖锻造师": "Staffsmith",
    "海牛的赌注": "Urf's Gambit", "爆发性成长": "Explosive Growth", "爆发性成长+": "Explosive Growth+",
    "军阀的荣誉": "Warlord's Honor", "耐心研究": "Patient Study", "贪财": "Money Hungry",
    "编织魔法": "Woven Magic", "明智消费": "Wise Spending", "力量锻造": "Forged in Strength",
    "灵活": "Flexible", "坚守阵线": "Hold the Line", "崇高冒险": "An Exalted Adventure",
    "金币季风": "Money Monsoon", "混乱召唤": "Call to Chaos", "致命帽子": "Deadlier Caps",
    "商业核心": "Commerce Core",
    # B tier (常见)
    "认知税": "Cognitive Tax", "认知税+": "Cognitive Tax+", "腐蚀": "Corrosion",
    "充能转移 I": "Charge Transfer I", "错失连接": "Missed Connections", "双重守护者": "Twin Guardians",
    "尺寸问题": "Size Matters", "增强力量": "Augmented Power", "重击": "Bonk!",
    "恒星组合": "Stellar Combo", "一二三": "One Two Three", "快速启动": "Kick Start",
    "小礼包": "Small Grab Bag", "持续召唤": "Continuous Conjuration", "开辟道路": "Carve a Path",
    "流放者 I": "Exiles I", "感觉幸运": "Feeling Lucky", "拳击课": "Boxing Lessons",
    "玻璃大炮 I": "Glass Cannon I", "电光 I": "Electrocharge I", "治疗宝珠 I": "Healing Orbs I",
    "耐心是美德": "Patience is a Virtue", "节外生枝": "Branching Out", "部分飞升": "Partial Ascension",
    "锻造朋友": "Forge a Friend", "装备自助餐": "Item Grab Bag", "一二五": "One, Two, Five!",
    "团队建设": "Team Building", "基础装备自助餐": "Item Grab Bag",
    "储蓄账户": "Savings Account", "两个坦克": "Two Tanky", "强化包": "Booster Pack",
    "强化包+": "Booster Pack+", "传播根系": "Spreading Roots", "不合群": "Misfits",
    "热寂": "Heat Death", "专注": "Concentration", "贸易区": "Trade Sector",
    "三人军团": "Legion of Threes", "独家定制": "Exclusive Customization", "护理包": "Care Package",
    "保镖训练": "Bodyguard Training", "前线基础": "Frontline Foundation", "单独板块": "Solo Plate",
    "奥术维克托": "Arcane Viktor-y", "复制": "Replication", "后期缩放": "Late Game Scaling",
    "剧情护甲": "Plot Armor", "钢铁之心": "Heart of Steel", "征途": "Warpath",
    "纪元": "Epoch", "纪元+": "Epoch+", "集体拥抱 II": "Group Hug II", "日炎板": "Sunfire Board",
    "治疗宝珠 II": "Healing Orbs II", "哭泣之河": "Cry Me A River", "清晰头脑": "Clear Mind",
    "猛击": "Slammin'", "猛击+": "Slammin'+", "流放者 II": "Exiles II",
    "玻璃大炮 II": "Glass Cannon II", "王冠之重": "Heavy Is the Crown", "碰撞测试假人": "Crash Test Dummies",
    "神化锻造": "Apotheotic Forge", "混乱头脑": "Cluttered Mind", "卡胡纳": "Kahunahuna",
    "获得21金币": "Gain 21 Gold", "镀金钢铁": "Gilded Steel", "高级贷款": "Advanced Loan",
    "高级贷款+": "Advanced Loan+", "魔法掷骰": "A Magic Roll", "契约杀手": "Contract Killer",
    "无限火力": "U.R.F", "四人强化": "ReinFOURcement", "无差别杀手": "Indiscriminate Killer",
    "炽天使之杖": "Seraphim's Staff", "英雄礼包+": "Heroic Grab Bag+", "英雄礼包++": "Heroic Grab Bag++",
    "职业拳手": "Prizefighter", "爬梯 II": "Climb The Ladder II", "活体锻造": "Living Forge",
    "男爵巢穴": "Baron's Lair", "一buff二buff": "One Buff, Two Buff", "向上流动": "Upward Mobility",
    "对冲基金+": "Hedge Fund+", "对冲基金": "Hedge Fund", "法杖溢出": "Wand Overflow",
    "虫群之心": "Heart of the Swarm", "光辉恶棍": "Radiant Rascal", "剑溢出": "Sword Overflow",
    "奢侈订阅": "Luxury Subscription", "幸运手套+": "Lucky Gloves+", "意料之外的预期": "Expected Unexpectedness",
    "投资+": "Invested+", "投资++": "Invested++", "棱彩门票": "Prismatic Ticket",
    "潘多拉的装备 III": "Pandora's Items III", "埋藏宝藏": "Buried Treasures",
    "盗贼团伙 II": "Band of Thieves II", "盗贼团伙 II+": "Band of Thieves II+",
    "盗贼团伙 II++": "Band of Thieves II++", "回归故事": "Comeback Story", "腰带溢出": "Belt Overflow",
    "珠光精华": "Shimmerscale Essence", "黄金赌博": "Golden Gamble", "黄金赌博+": "Golden Gamble+",
    "黄金赌博++": "Golden Gamble++", "海牛的礼包": "Urf's Grab Bag", "致命之刃": "Deadlier Blades",
    "独家定制 II": "Exclusive Customization II", "最小最大化": "Min-Max", "值得等待 II": "Worth the Wait II",
    "最小泰坦": "Tiniest Titan", "诅咒王冠": "Cursed Crown",
    # C/D tier (常见)
    "升级": "Level Up!", "巨大而强大": "Giant and Mighty", "新兵": "New Recruit",
    "我们团结一心": "We Stick Together", "生日礼物": "Birthday Present", "坚定承诺": "Hard Commit",
    "小而致命": "Tiny, but Deadly", "构造伙伴": "Construct a Companion", "建造伙伴": "Build a Bud",
    "报复": "Retribution", "灵魂觉醒": "Soul Awakening", "甜蜜款待": "Sweet Treats",
    "打长期战": "Going Long", "代价为何": "At What Cost", "青铜人生 II": "Bronze For Life II",
    "幸运手套": "Lucky Gloves", "赢到底": "Win Out", "组件盗窃": "Component Heist",
    "金蛋": "The Golden Egg", "三连击 II": "Trifecta II", "珠宝莲花 II": "Jeweled Lotus II",
    "订阅服务": "Subscription Service",
    # 其他
    "弈子配送": "Unit Delivery", "弈子配送+": "Unit Delivery+", "弈子配送++": "Unit Delivery++",
    "进攻宣告": "Offensive Declaration", "资本利得 I": "Capital Gains I",
    "值得等待": "Worth the Wait", "你有我的弓": "You Have My Bow", "单人练级": "Solo Leveling",
    "骗子": "Hustler", "血祭": "Blood Offering", "高压电": "High Voltage",
    "神圣修正": "Divine Amendment", "三连击 I": "Trifecta I",
}

# 英文→中文 反向映射 (用于显示)
EN_TO_CN = {v: k for k, v in CN_TO_EN.items()}

import difflib

def _fuzzy_match_cn(name, candidates, cutoff=0.6):
    """模糊匹配中文名称"""
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None

# 合并所有阶段的数据（用于模糊查找）
ALL_AUGMENTS = {}
for d in [AUGMENTS_2_1, AUGMENTS_3_2, AUGMENTS_4_2]:
    for k, v in d.items():
        if k not in ALL_AUGMENTS:
            ALL_AUGMENTS[k] = v

# ========== 性能优化: 预计算索引 + LRU缓存 ==========
def _normalize(s):
    return ''.join(c.lower() for c in s if c.isalnum())

# 中文名称直接→评级映射 (优先使用, 不需要中英文转换)
CN_TO_TIER = {
    # === S级 ===
    "远征": "S", "重新开始任务": "S", "重启任务": "S", "傻瓜化": "S", "傀儡化": "S",
    "轻量魔法投掷": "S", "轻微魔法掷骰": "S", "早期学习": "S", "寻宝": "S",
    "战术家的厨房": "S", "羁绊之树": "S", "羁绊之树+": "S",
    # === A级 ===
    "潜在锻造": "A", "后期专家": "A", "守护者盟友": "A", "顺风顺水": "A", "连战连胜": "A",
    "挂机": "A", "集体拥抱 I": "A", "潘多拉的装备": "A", "临时护甲 I": "A", "节外生枝+": "A",
    "盗贼团伙": "A", "银勺": "A", "不侦察不转型": "A", "便携式锻造台": "A", "摘星": "A",
    "大爆炸": "A", "自毁": "A", "史诗级刷新": "A", "前瞻性思维": "A", "铸剑师": "A",
    "双排": "A", "大礼包": "A", "小伙伴": "A", "算计失败": "A", "宇宙重启": "A",
    "法杖锻造师": "A", "海牛的赌注": "A", "爆发性成长": "A", "爆发性成长+": "A",
    "军阀的荣誉": "A", "耐心研究": "A", "贪财": "A", "编织魔法": "A", "明智消费": "A",
    "力量锻造": "A", "灵活": "A", "坚守阵线": "A", "崇高冒险": "A", "金币季风": "A",
    "混乱召唤": "A", "致命帽子": "A", "商业核心": "A", "生日重聚": "A", "蔓延根系+": "A",
    "强化包++": "A",
    # === B级 ===
    "金鳞精萃": "B", "珍藏财宝": "B", "珍藏财宝 II": "B", "珍藏财宝 III": "B",
    "绝境反击": "B", " comeback story": "B", "认知税": "B", "认知税+": "B", "腐蚀": "B",
    "充能转移 I": "B", "错失连接": "B", "双重守护者": "B", "尺寸问题": "B", "增强力量": "B",
    "重击": "B", "恒星组合": "B", "一二三": "B", "快速启动": "B", "小礼包": "B",
    "持续召唤": "B", "开辟道路": "B", "流放者 I": "B", "感觉幸运": "B", "拳击课": "B",
    "玻璃大炮 I": "B", "电光 I": "B", "治疗宝珠 I": "B", "耐心是美德": "B", "节外生枝": "B",
    "部分飞升": "B", "锻造朋友": "B", "装备自助餐": "B", "一二五": "B", "团队建设": "B",
    "基础装备自助餐": "B", "钢铁资产": "B", "储蓄账户": "B", "两个坦克": "B", "强化包": "B",
    "强化包+": "B", "蔓延根系": "B", "不合群": "B", "热寂": "B", "专注": "B", "贸易区": "B",
    "三人军团": "B", "独家定制": "B", "护理包": "B", "保镖训练": "B", "前线基础": "B",
    "单独板块": "B", "奥术维克托": "B", "复制": "B", "后期缩放": "B", "剧情护甲": "B",
    "钢铁之心": "B", "征途": "B", "纪元": "B", "纪元+": "B", "集体拥抱 II": "B",
    "日炎板": "B", "治疗宝珠 II": "B", "哭泣之河": "B", "清晰头脑": "B", "猛击": "B",
    "猛击+": "B", "流放者 II": "B", "玻璃大炮 II": "B", "王冠之重": "B", "碰撞测试假人": "B",
    "神化锻造": "B", "混乱头脑": "B", "卡胡纳": "B", "获得21金币": "B", "镀金钢铁": "B",
    "高级贷款": "B", "高级贷款+": "B", "魔法掷骰": "B", "契约杀手": "B", "无限火力": "B",
    "四人强化": "B", "无差别杀手": "B", "炽天使之杖": "B", "英雄礼包+": "B", "英雄礼包++": "B",
    "职业拳手": "B", "爬梯 II": "B", "活体锻造": "B", "男爵巢穴": "B", "一buff二buff": "B",
    "向上流动": "B", "对冲基金+": "B", "对冲基金": "B", "法杖溢出": "B", "虫群之心": "B",
    "光辉恶棍": "B", "剑溢出": "B", "奢侈订阅": "B", "幸运手套+": "B", "意料之外的预期": "B",
    "投资+": "B", "投资++": "B", "棱彩门票": "B", "潘多拉的装备 III": "B", "埋藏宝藏": "B",
    "盗贼团伙 II": "B", "盗贼团伙 II+": "B", "盗贼团伙 II++": "B", "回归故事": "B",
    "腰带溢出": "B", "黄金赌博": "B", "黄金赌博+": "B", "黄金赌博++": "B", "海牛的礼包": "B",
    "致命之刃": "B", "独家定制 II": "B", "最小最大化": "B", "值得等待 II": "B", "最小泰坦": "B",
    "诅咒王冠": "B", "终极极速": "B",
    # === C级 ===
    "升级": "C", "巨大而强大": "C", "新兵": "C", "我们团结一心": "C", "生日礼物": "C",
    "坚定承诺": "C", "小而致命": "C", "构造伙伴": "C", "建造伙伴": "C", "报复": "C",
    "灵魂觉醒": "C", "甜蜜款待": "C", "打长期战": "C", "代价为何": "C", "青铜人生 II": "C",
    "幸运手套": "C", "赢到底": "C", "组件盗窃": "C", "金蛋": "C", "三连击 II": "C",
    "珠宝莲花 II": "C", "订阅服务": "C", "盾牌女仆": "C", "找到你的中心": "C",
    "滚动天数 I": "C", "冒险举动": "C", "第二次呼吸": "C", "流动之泪": "C", "阵容": "C",
    "有用的东西 I": "C", "聚焦火力": "C", "组队": "C", "午餐钱": "C", "小泰坦": "C",
    "备用弓": "C", "爬梯 I": "C", "最好的朋友 I": "C", "团结一致": "C", "精心制作": "C",
    "塔楼": "C", "吸血活力 I": "C", "银河之旅": "C", "时间流": "C", "无限保护": "C",
    "充能转移 II": "C", "后排蓝图": "C", "发条加速器": "C", "恶意货币化": "C", "回收箱": "C",
    "回收箱+": "C", "救赎之灵": "C", "灵魂指挥官": "C", "愿四与你同在": "C", "快速双杀": "C",
    "战利品奇点": "C", "副作用": "C", "第二次呼吸 II": "C", "临时护甲 II": "C", "大量属性": "C",
    "最好的朋友 II": "C", "锤石的意志": "C", "赛博上行链路": "C", "赛博植入": "C",
    "潘多拉的装备 II": "C", "喂火": "C", "电光 II": "C", "英雄礼包": "C", "认知过载": "C",
    "飞升": "C", "光环耕种": "C", "偷窃": "C", "珠宝莲花 I": "C", "青铜人生 I": "C",
    # === D级 ===
    "生活片段": "D", "重组器": "D", "幸存者": "D", "神圣修正": "D", "高压电": "D",
    "三连击 I": "D", "值得等待": "D", "你有我的弓": "D", "单人练级": "D", "骗子": "D",
    "血祭": "D",
}

# 中文 normalize 索引 (用于快速中文模糊匹配)
_CN_NORM_INDEX = {_normalize(k): k for k in CN_TO_TIER.keys()}

_tier_cache = {}
_CACHE_MAX = 2000

def _cache_result(key, value):
    if len(_tier_cache) >= _CACHE_MAX:
        for k in list(_tier_cache.keys())[:_CACHE_MAX//2]:
            del _tier_cache[k]
    _tier_cache[key] = value

def get_augment_tier(name, stage=None):
    """获取海克斯评级 — 优先中文直接查找, 带缓存+索引"""
    if not name:
        return None
    name = name.strip()
    cache_key = (name, stage)
    if cache_key in _tier_cache:
        return _tier_cache[cache_key]

    # 1. 中文直接精确查找 (优先, 不需要中英文转换)
    if name in CN_TO_TIER:
        tier = CN_TO_TIER[name]
        result = (tier, TIER_COLORS[tier], TIER_DESC[tier], name)
        _cache_result(cache_key, result)
        return result

    # 2. 中文 normalize 快速匹配
    nname = _normalize(name)
    if nname in _CN_NORM_INDEX:
        cn_name = _CN_NORM_INDEX[nname]
        tier = CN_TO_TIER[cn_name]
        result = (tier, TIER_COLORS[tier], TIER_DESC[tier], cn_name)
        _cache_result(cache_key, result)
        return result

    # 3. 中文模糊匹配 (difflib)
    cn_match = _fuzzy_match_cn(name, list(CN_TO_TIER.keys()), cutoff=0.5)
    if cn_match:
        tier = CN_TO_TIER[cn_match]
        result = (tier, TIER_COLORS[tier], TIER_DESC[tier], cn_match)
        _cache_result(cache_key, result)
        return result

    # 4. 回退: 中文→英文→英文评级表 (兼容旧数据)
    en_name = CN_TO_EN.get(name)
    lookup_name = en_name or name
    data_map = None
    if stage == 2: data_map = AUGMENTS_2_1
    elif stage == 3: data_map = AUGMENTS_3_2
    elif stage == 4: data_map = AUGMENTS_4_2

    if data_map and lookup_name in data_map:
        tier = data_map[lookup_name]
        result = (tier, TIER_COLORS[tier], TIER_DESC[tier], lookup_name)
        _cache_result(cache_key, result)
        return result

    search_map = data_map if data_map else ALL_AUGMENTS
    for k, v in search_map.items():
        if _normalize(k) == nname or nname in _normalize(k) or _normalize(k) in nname:
            result = (v, TIER_COLORS[v], TIER_DESC[v], k)
            _cache_result(cache_key, result)
            return result

    en_match = difflib.get_close_matches(lookup_name, list(search_map.keys()), n=1, cutoff=0.5)
    if en_match:
        tier = search_map[en_match[0]]
        result = (tier, TIER_COLORS[tier], TIER_DESC[tier], en_match[0])
        _cache_result(cache_key, result)
        return result

    _cache_result(cache_key, None)
    return None


def get_all_augment_names():
    """返回所有海克斯名称列表"""
    return list(ALL_AUGMENTS.keys())
