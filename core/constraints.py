"""
约束管理模块 — 按稳定性分级

三级体系（冲突时高档优先）：
  TIER_1_FOUNDATION   基础性：绝对不可偏离（角色名、世界观硬规则、行文底线）
  TIER_2_EVOLVABLE    可演变：随行文自然变化（称呼、关系、情绪、伏笔状态）
  TIER_3_FLEXIBLE     可偏离：根据行文情况调整（细纲、场景设计、节奏）

存储结构：
  constraints/
    tier1_foundation.json   ← 基础约束（极少变动）
    tier2_evolvable.json    ← 可演变约束（随章节自动更新）
    tier3_flexible.json     ← 可偏离约束（每章覆盖）
    archive/                ← 归档的细纲（每章一个文件）
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from enum import IntEnum
from dataclasses import dataclass, field, asdict


class Tier(IntEnum):
    """约束等级（数字越小优先级越高）"""
    FOUNDATION = 1   # 基础性：绝对不可偏离
    EVOLVABLE = 2    # 可演变：随行文自然变化
    FLEXIBLE = 3     # 可偏离：根据行文情况调整


# ═══════════════════════════════════════════════════════════════
#  预置基础约束（Tier1）— 系统初始化时写入
# ═══════════════════════════════════════════════════════════════

PRESET_TIER1 = [
    # ── 角色基础 ──
    ("character", "角色名不可更改：林远、系统、所有已登场角色的名字一旦写定不可修改"),
    ("character", "角色核心性格不可逆转：林远嘴碎但善良、懒但关键时刻靠谱，这些底层性格不随剧情改变"),

    # ── 世界观硬规则 ──
    ("world", "境界体系不可修改：滴水境→溪流境→江河境→湖泽境→沧海境→归墟境"),
    ("world", "能力获取方式不可修改：打捞天赋、建造天赋等获取规则一旦写定不可更改"),
    ("world", "地理设定不可修改：乐园区域划分（造浪池、漂流河、彩虹滑道等）"),

    # ── 行文底线（绝对禁止）──
    ("style", "禁止使用原作人名与商标词"),
    ("style", "禁止写'命运的齿轮开始转动'"),
    ("style", "禁止写'这一刻，他终于明白了'"),
    ("style", "禁止写'首先、其次、最后'"),
    ("style", "禁止写'值得注意的是''综上所述''需要说明的是'等零回指评论"),
    ("style", "禁止在小说正文里用列表格式，禁止用冒号引出一串并列内容"),
    ("style", "禁止对话分割不自然：一轮对话中间最多插入1次描写，且必须在语义完整处"),
    ("style", "禁止所有角色说话风格雷同：每个角色有3-5个常用词/口头禅，说话风格必须区分"),
    ("style", "禁止叙述者替读者总结主题：不要在结尾写'他终于明白了''这个故事告诉我们'"),
    ("style", "禁止角色借对话讲大道理：对话围绕具体事情，不用行动之外的方式说教"),
    ("style", "禁止破折号过密：一个段落内最多出现1次破折号"),
    ("style", "禁止冒号用于对话标注：对话用引号，不用冒号"),
    ("style", "禁止句式过于工整对称：连续3句以上长度相同的句子必须打破"),
    ("style", "禁止对举结构滥用：不要频繁使用'不是……而是……'"),
    ("style", "禁止段首零回指评论：新段落开头必须有明确主语"),
    ("style", "禁止感官描写过载：一场戏调动2-3种感官就够了"),
    ("style", "禁止环境描写八股化：不用'夕阳的余晖洒在大地上'等套话"),
    ("style", "禁止过度身体反应描写：不用'冷汗、心跳加速、拳头握紧'标准套餐"),
    ("style", "禁止心理活动直给：少用形容词定义情绪，多用动作外化"),
    ("style", "网文只许从角色嘴里长出来，作者不下场玩梗"),

    # ── 平台硬性要求 ──
    ("platform", "每章1000-2500字（番茄小说平台要求）"),
    ("platform", "每章至少1个爽点+1个章尾钩子"),
    ("platform", "前3章必须亮出金手指或核心悬念"),
    ("platform", "切忌长篇大论铺垫世界观，世界观通过人物冲突和场景细节透出"),
    ("platform", "爽点间隔不超过3章"),
    ("platform", "每3章一个小高潮，每10章一个大高潮"),

    # ── 格式 ──
    ("format", "直接输出正文，不要有标题，不要使用Markdown格式"),
    ("format", "对话用引号包裹，说话人用动作锚定，不要用'XX说'"),
    ("format", "感叹号一章内不超过5个，问号可以频繁使用制造口语感"),
]

PRESET_TIER2_OUTLINE = [
    # 这些会在大纲导入时自动填充
    ("plot", "大纲是行文的第二优先级指引，正文偏离大纲时需在后续章节修正"),
    ("foreshadowing", "伏笔的埋设和回收必须符合大纲约定，不可随意废弃"),
]

PRESET_TIER3_EMPTY = [
    # 细纲由系统每章自动生成
]


@dataclass
class Constraint:
    """单条约束"""
    id: str
    tier: int
    category: str          # character/world/style/platform/format/plot/foreshadowing/scene/relationship
    content: str
    source: str = ""       # 来源：preset/fmanual/ch001/大纲第3卷 等
    created_at: str = ""
    locked: bool = False   # True = 手动锁定，不会被自动清除
    evolved_from: str = "" # 如果是演变来的，记录原内容

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class ConstraintManager:
    """约束管理器"""

    TIER_FILES = {
        Tier.FOUNDATION: 'tier1_foundation.json',
        Tier.EVOLVABLE:  'tier2_evolvable.json',
        Tier.FLEXIBLE:   'tier3_flexible.json',
    }

    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
        self.constraints_dir = self.base_path / 'constraints'
        self.archive_dir = self.constraints_dir / 'archive'
        self.project_name = project_name

    # ── 加载/保存 ─────────────────────────────────────────

    def _tier_path(self, tier: Tier) -> Path:
        return self.constraints_dir / self.TIER_FILES[tier]

    def _load_tier(self, tier: Tier) -> List[Constraint]:
        path = self._tier_path(tier)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding='utf-8'))
        return [Constraint(**item) for item in data]

    def _save_tier(self, tier: Tier, constraints: List[Constraint]):
        self.constraints_dir.mkdir(parents=True, exist_ok=True)
        path = self._tier_path(tier)
        data = [asdict(c) for c in constraints]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    # ── 初始化：写入预置约束 ─────────────────────────────

    def init_preset_constraints(self):
        """初始化预置约束（仅首次）"""
        # Tier1 基础约束
        if not self._tier_path(Tier.FOUNDATION).exists():
            for cat, content in PRESET_TIER1:
                self.add(Tier.FOUNDATION, cat, content, source="preset", locked=True)

        # Tier2 可演变约束（大纲类）
        if not self._tier_path(Tier.EVOLVABLE).exists():
            for cat, content in PRESET_TIER2_OUTLINE:
                self.add(Tier.EVOLVABLE, cat, content, source="preset")

        # Tier3 可偏离约束
        if not self._tier_path(Tier.FLEXIBLE).exists():
            self._save_tier(Tier.FLEXIBLE, [])

    # ── CRUD ─────────────────────────────────────────────

    def add(self, tier: Tier, category: str, content: str,
            source: str = "", locked: bool = False) -> Constraint:
        """添加一条约束（自动去重）"""
        constraints = self._load_tier(tier)
        prefix = content[:20]
        for existing in constraints:
            if existing.category == category and existing.content[:20] == prefix:
                return existing
        c = Constraint(
            id=f"t{tier.value}_{category[:3]}_{len(constraints)+1:04d}",
            tier=tier.value,
            category=category,
            content=content,
            source=source,
            locked=locked
        )
        constraints.append(c)
        self._save_tier(tier, constraints)
        return c

    def update(self, tier: Tier, constraint_id: str, new_content: str,
               evolved_from: str = "") -> bool:
        """更新一条约束（用于可演变约束的自然变化）"""
        constraints = self._load_tier(tier)
        for c in constraints:
            if c.id == constraint_id:
                c.evolved_from = c.content if not evolved_from else evolved_from
                c.content = new_content
                c.updated_at = datetime.now().isoformat()
                self._save_tier(tier, constraints)
                return True
        return False

    def remove(self, tier: Tier, constraint_id: str) -> bool:
        constraints = self._load_tier(tier)
        before = len(constraints)
        constraints = [c for c in constraints if c.id != constraint_id]
        if len(constraints) < before:
            self._save_tier(tier, constraints)
            return True
        return False

    def get_all(self) -> Dict[int, List[Constraint]]:
        return {
            Tier.FOUNDATION: self._load_tier(Tier.FOUNDATION),
            Tier.EVOLVABLE:  self._load_tier(Tier.EVOLVABLE),
            Tier.FLEXIBLE:   self._load_tier(Tier.FLEXIBLE),
        }

    def get_tier(self, tier: Tier) -> List[Constraint]:
        return self._load_tier(tier)

    # ── Tier2 可演变约束：从已写内容自动同步 ───────────

    def sync_from_outline(self, outline_text: str, source: str = "大纲"):
        """从大纲文本提取关键情节约束到 Tier2"""
        paragraphs = [p.strip() for p in outline_text.split('\n') if p.strip()]
        for para in paragraphs:
            if len(para) < 5:
                continue
            cat = self._guess_category(para)
            self.add(Tier.EVOLVABLE, cat, para[:200], source=source)

    def _guess_category(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ['角色', '人物', '性格', '称呼', '关系']):
            return 'character'
        if any(k in t for k in ['伏笔', '悬念', '回收', '呼应']):
            return 'foreshadowing'
        if any(k in t for k in ['世界', '设定', '规则', '体系']):
            return 'world'
        if any(k in t for k in ['风格', '调性', '节奏', '爽点']):
            return 'style'
        return 'plot'

    def sync_evolvable_from_chapters(self, storage):
        """从已写章节同步 Tier2 可演变约束（称呼、关系、情绪等会变的内容）"""
        chapters = storage.list_chapters()
        if not chapters:
            return

        for ch_info in chapters:
            ch_num = ch_info.get('chapter', 0)
            ch_dir = storage._chapter_dir(ch_num)
            mem_file = ch_dir / 'memory.json'
            if not mem_file.exists():
                continue
            ch_memory = json.loads(mem_file.read_text(encoding='utf-8'))
            source = f"ch{ch_num:04d}"

            # 关系变化 → Tier2
            for rel in ch_memory.get('relationship_changes', []):
                fr = rel.get('from', '')
                to = rel.get('to', '')
                rel_type = rel.get('relation', '')
                detail = rel.get('detail', '')
                if fr and to:
                    content = f"{fr}→{to}：{rel_type}"
                    if detail:
                        content += f"（{detail}）"
                    self.add(Tier.EVOLVABLE, 'relationship', content, source=source)

            # 角色状态变化 → Tier2（情绪、位置等会变的）
            for cc in ch_memory.get('character_changes', []):
                name = cc.get('name', '')
                if not name:
                    continue
                if cc.get('emotion'):
                    self.add(Tier.EVOLVABLE, 'emotion',
                             f"{name}当前情绪：{cc['emotion']}", source=source)
                if cc.get('state'):
                    self.add(Tier.EVOLVABLE, 'state',
                             f"{name}状态：{cc['state']}", source=source)

    # ── Tier3 可偏离约束：每章细纲 ────────────────────

    def set_chapter_flex(self, chapter: int, outline_text: str):
        """写入当章细纲（覆盖式）"""
        self.constraints_dir.mkdir(parents=True, exist_ok=True)
        c = Constraint(
            id=f"ch{chapter:04d}_flex",
            tier=Tier.FLEXIBLE.value,
            category='chapter_outline',
            content=outline_text,
            source=f"ch{chapter:04d}"
        )
        self._save_tier(Tier.FLEXIBLE, [c])

    def archive_chapter_flex(self, chapter: int):
        """归档当章细纲"""
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        tier3 = self._load_tier(Tier.FLEXIBLE)
        if tier3:
            archive_path = self.archive_dir / f"ch{chapter:04d}.json"
            archive_path.write_text(
                json.dumps([asdict(c) for c in tier3], ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        self._save_tier(Tier.FLEXIBLE, [])

    def load_archive(self, chapter: int) -> List[Constraint]:
        path = self.archive_dir / f"ch{chapter:04d}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding='utf-8'))
        return [Constraint(**item) for item in data]

    # ── 冲突检测 ────────────────────────────────────────

    def check_conflict(self, new_constraint: Constraint) -> Optional[Constraint]:
        """检查新约束是否与更高或同级约束冲突"""
        for tier in [Tier.FOUNDATION, Tier.EVOLVABLE, Tier.FLEXIBLE]:
            if tier.value > new_constraint.tier:
                continue
            existing = self._load_tier(tier)
            for c in existing:
                if c.id == new_constraint.id:
                    continue
                if c.category == new_constraint.category:
                    overlap = self._text_overlap(c.content, new_constraint.content)
                    if overlap > 0.6:
                        return c
        return None

    def _text_overlap(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        set_a, set_b = set(a), set(b)
        return len(set_a & set_b) / max(len(set_a), len(set_b))

    # ── 格式化输出（注入提示词）────────────────────────

    def format_for_prompt(self, max_tokens_per_tier: Dict[int, int] = None) -> str:
        """将全部约束格式化为提示词文本"""
        if max_tokens_per_tier is None:
            max_tokens_per_tier = {
                Tier.FOUNDATION: 2500,
                Tier.EVOLVABLE:  1200,
                Tier.FLEXIBLE:   600,
            }

        parts = []
        tier_labels = {
            Tier.FOUNDATION: "【第一档·基础性·绝对不可偏离】",
            Tier.EVOLVABLE:  "【第二档·可演变·随行文自然变化】",
            Tier.FLEXIBLE:   "【第三档·可偏离·根据行文情况调整】",
        }

        cat_labels = {
            'character': '角色', 'world': '世界观', 'style': '风格',
            'platform': '平台', 'format': '格式', 'plot': '情节',
            'foreshadowing': '伏笔', 'relationship': '关系',
            'emotion': '情绪', 'state': '状态', 'chapter_outline': '细纲',
            'scene': '场景', 'event': '事件',
        }

        for tier in [Tier.FOUNDATION, Tier.EVOLVABLE, Tier.FLEXIBLE]:
            constraints = self._load_tier(tier)
            if not constraints:
                continue

            by_cat: Dict[str, List[Constraint]] = {}
            for c in constraints:
                by_cat.setdefault(c.category, []).append(c)

            lines = [tier_labels[tier]]
            max_tokens = max_tokens_per_tier.get(tier, 1000)
            used_tokens = 0

            for cat, cat_list in by_cat.items():
                cat_label = cat_labels.get(cat, cat)
                for c in cat_list:
                    tokens = len(c.content) // 2
                    if used_tokens + tokens > max_tokens:
                        break
                    lines.append(f"  [{cat_label}] {c.content}")
                    used_tokens += tokens

            if len(lines) > 1:
                parts.append("\n".join(lines))

        return "\n\n".join(parts)

    # ── 统计 ────────────────────────────────────────────

    def get_stats(self) -> Dict:
        stats = {}
        for tier in [Tier.FOUNDATION, Tier.EVOLVABLE, Tier.FLEXIBLE]:
            constraints = self._load_tier(tier)
            stats[f'tier{tier.value}'] = len(constraints)
        stats['archive'] = len(list(self.archive_dir.glob('ch*.json'))) if self.archive_dir.exists() else 0
        return stats
