"""
约束管理模块

三级约束体系（冲突时高档覆盖低档）：
  TIER_1_IMMUTABLE  — 已写定内容（角色设定、称呼、关系、已发生事件）
  TIER_2_OUTLINE    — 大纲（卷纲、关键转折、伏笔约定）
  TIER_3_CHAPTER    — 细纲/当章提示词（可适度偏离，但不违反上位约束）

存储结构：
  constraints/
    tier1_immutable.json   ← 已写定事实（程序自动维护 + 手动补充）
    tier2_outline.json     ← 大纲约束（从大纲提取 + 手动补充）
    tier3_chapter.json     ← 细纲约束（每章生成前写入，生成后归档）
    archive/               ← 已归档的细纲（每章一个文件）
      ch001.json
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from enum import IntEnum
from dataclasses import dataclass, field, asdict


class Tier(IntEnum):
    """约束等级（数字越小优先级越高）"""
    IMMUTABLE = 1    # 已写定，绝对不可违背
    OUTLINE = 2      # 大纲，原则上不可违背
    CHAPTER = 3      # 细纲，可适度偏离


@dataclass
class Constraint:
    """单条约束"""
    id: str
    tier: int              # Tier 枚举值
    category: str          # 分类：character/plot/world/foreshadowing/style/tone
    content: str           # 约束描述
    source: str = ""       # 来源（如：ch001、大纲第3卷）
    created_at: str = ""
    locked: bool = False   # True = 手动锁定，不会被自动归档清除

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class ConstraintManager:
    """约束管理器"""

    TIER_FILES = {
        Tier.IMMUTABLE: 'tier1_immutable.json',
        Tier.OUTLINE:   'tier2_outline.json',
        Tier.CHAPTER:   'tier3_chapter.json',
    }

    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
        self.constraints_dir = self.base_path / 'constraints'
        self.archive_dir = self.constraints_dir / 'archive'

    # ── 加载/保存 ─────────────────────────────────────────

    def _tier_path(self, tier: Tier) -> Path:
        return self.constraints_dir / self.TIER_FILES[tier]

    def _load_tier(self, tier: Tier) -> List[Constraint]:
        """加载某一级约束"""
        path = self._tier_path(tier)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding='utf-8'))
        return [Constraint(**item) for item in data]

    def _save_tier(self, tier: Tier, constraints: List[Constraint]):
        """保存某一级约束"""
        self.constraints_dir.mkdir(parents=True, exist_ok=True)
        path = self._tier_path(tier)
        data = [asdict(c) for c in constraints]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    # ── CRUD ─────────────────────────────────────────────

    def add(self, tier: Tier, category: str, content: str,
            source: str = "", locked: bool = False) -> Constraint:
        """添加一条约束"""
        constraints = self._load_tier(tier)
        # 去重：同tier+同category+相同内容前20字
        prefix = content[:20]
        for existing in constraints:
            if existing.category == category and existing.content[:20] == prefix:
                return existing  # 已存在，返回现有
        c = Constraint(
            id=f"{tier.name.lower()}_{len(constraints)+1:04d}",
            tier=tier.value,
            category=category,
            content=content,
            source=source,
            locked=locked
        )
        constraints.append(c)
        self._save_tier(tier, constraints)
        return c

    def remove(self, tier: Tier, constraint_id: str) -> bool:
        """删除一条约束"""
        constraints = self._load_tier(tier)
        before = len(constraints)
        constraints = [c for c in constraints if c.id != constraint_id]
        if len(constraints) < before:
            self._save_tier(tier, constraints)
            return True
        return False

    def get_all(self) -> Dict[int, List[Constraint]]:
        """获取全部约束，按tier分组"""
        return {
            Tier.IMMUTABLE: self._load_tier(Tier.IMMUTABLE),
            Tier.OUTLINE:   self._load_tier(Tier.OUTLINE),
            Tier.CHAPTER:   self._load_tier(Tier.CHAPTER),
        }

    def get_tier(self, tier: Tier) -> List[Constraint]:
        return self._load_tier(tier)

    # ── 从已有内容自动提取 Tier1 约束 ──────────────────

    def sync_from_written_chapters(self, storage):
        """从已保存的章节中自动提取 Tier1 约束（角色名、称呼、已发生事件）"""
        chapters = storage.list_chapters()
        if not chapters:
            return

        for ch_info in chapters:
            ch_num = ch_info.get('chapter', 0)
            mem = storage.load_chapter_meta(ch_num)
            # 读取本章记忆
            ch_dir = storage._chapter_dir(ch_num)
            mem_file = ch_dir / 'memory.json'
            if not mem_file.exists():
                continue
            ch_memory = json.loads(mem_file.read_text(encoding='utf-8'))

            source = f"ch{ch_num:04d}"

            # 角色状态变化 → Tier1
            for cc in ch_memory.get('character_changes', []):
                name = cc.get('name', '')
                if not name:
                    continue
                if cc.get('emotion'):
                    self.add(Tier.IMMUTABLE, 'character',
                             f"{name}当前情绪：{cc['emotion']}", source=source)
                if cc.get('state'):
                    self.add(Tier.IMMUTABLE, 'character',
                             f"{name}状态：{cc['state']}", source=source)
                if cc.get('new_info'):
                    self.add(Tier.IMMUTABLE, 'character',
                             f"{name}已知信息：{cc['new_info']}", source=source)

            # 关系变化 → Tier1
            for rel in ch_memory.get('relationship_changes', []):
                self.add(Tier.IMMUTABLE, 'relationship',
                         f"{rel.get('from','')}→{rel.get('to','')}：{rel.get('relation','')}（{rel.get('detail','')}）",
                         source=source)

            # 已发生的事件 → Tier1
            for ev in ch_memory.get('events', []):
                self.add(Tier.IMMUTABLE, 'event',
                         f"第{ch_num}章：{ev.get('description','')[:80]}",
                         source=source)

            # 已埋/已解伏笔 → Tier1
            for fh in ch_memory.get('foreshadowing', []):
                hint = fh.get('hint', '')
                if not hint:
                    continue
                if fh.get('status') == 'new':
                    self.add(Tier.IMMUTABLE, 'foreshadowing',
                             f"已埋伏笔：{hint}", source=source)
                elif fh.get('status') == 'resolved':
                    self.add(Tier.IMMUTABLE, 'foreshadowing',
                             f"已解伏笔：{hint}", source=source)

    # ── 从大纲提取 Tier2 约束 ─────────────────────────

    def sync_from_outline(self, outline_text: str, source: str = "大纲"):
        """从大纲文本中提取关键约束（角色、转折、结局等）"""
        # 按段落拆分，每段作为一个约束
        paragraphs = [p.strip() for p in outline_text.split('\n') if p.strip()]
        for i, para in enumerate(paragraphs):
            # 跳过纯标题行
            if len(para) < 5:
                continue
            category = self._guess_category(para)
            self.add(Tier.OUTLINE, category, para[:200], source=source)

    def _guess_category(self, text: str) -> str:
        """根据关键词猜测分类"""
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

    # ── 细纲管理（Tier3）──────────────────────────────

    def set_chapter_constraints(self, chapter: int, constraints_text: str):
        """写入当章细纲约束（覆盖式）"""
        self.constraints_dir.mkdir(parents=True, exist_ok=True)
        c = Constraint(
            id=f"ch{chapter:04d}",
            tier=Tier.CHAPTER.value,
            category='chapter_outline',
            content=constraints_text,
            source=f"ch{chapter:04d}"
        )
        self._save_tier(Tier.CHAPTER, [c])

    def archive_chapter_constraints(self, chapter: int):
        """归档当章细纲（写完后存入 archive/）"""
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        tier3 = self._load_tier(Tier.CHAPTER)
        if tier3:
            archive_path = self.archive_dir / f"ch{chapter:04d}.json"
            archive_path.write_text(
                json.dumps([asdict(c) for c in tier3], ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        # 清空当章细纲
        self._save_tier(Tier.CHAPTER, [])

    def load_archive(self, chapter: int) -> List[Constraint]:
        """读取归档的细纲"""
        path = self.archive_dir / f"ch{chapter:04d}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding='utf-8'))
        return [Constraint(**item) for item in data]

    # ── 冲突检测 ────────────────────────────────────────

    def check_conflict(self, new_constraint: Constraint) -> Optional[Constraint]:
        """检查新约束是否与更高或同级约束冲突"""
        for tier in [Tier.IMMUTABLE, Tier.OUTLINE, Tier.CHAPTER]:
            if tier.value > new_constraint.tier:
                continue  # 只检查同级和高级
            existing = self._load_tier(tier)
            for c in existing:
                if c.id == new_constraint.id:
                    continue
                # 同category下内容高度重叠视为冲突
                if c.category == new_constraint.category:
                    overlap = self._text_overlap(c.content, new_constraint.content)
                    if overlap > 0.6:
                        return c
        return None

    def _text_overlap(self, a: str, b: str) -> float:
        """简单字符重叠率"""
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = set_a & set_b
        return len(intersection) / max(len(set_a), len(set_b))

    # ── 格式化输出（注入提示词）────────────────────────

    def format_for_prompt(self, max_tokens_per_tier: Dict[int, int] = None) -> str:
        """将全部约束格式化为提示词文本"""
        if max_tokens_per_tier is None:
            max_tokens_per_tier = {
                Tier.IMMUTABLE: 2000,
                Tier.OUTLINE:   1500,
                Tier.CHAPTER:   800,
            }

        parts = []
        tier_labels = {
            Tier.IMMUTABLE: "【第一档·已写定·绝对不可违背】",
            Tier.OUTLINE:   "【第二档·大纲·原则上不可违背】",
            Tier.CHAPTER:   "【第三档·细纲·可适度偏离】",
        }

        for tier in [Tier.IMMUTABLE, Tier.OUTLINE, Tier.CHAPTER]:
            constraints = self._load_tier(tier)
            if not constraints:
                continue

            # 按category分组
            by_cat: Dict[str, List[Constraint]] = {}
            for c in constraints:
                by_cat.setdefault(c.category, []).append(c)

            cat_labels = {
                'character':     '角色',
                'relationship':  '关系',
                'event':         '事件',
                'plot':          '情节',
                'foreshadowing': '伏笔',
                'world':         '世界观',
                'style':         '风格',
                'chapter_outline': '细纲',
            }

            lines = [tier_labels[tier]]
            max_tokens = max_tokens_per_tier.get(tier, 1000)
            used_tokens = 0

            for cat, cat_constraints in by_cat.items():
                cat_label = cat_labels.get(cat, cat)
                for c in cat_constraints:
                    # 粗略token估算
                    tokens = len(c.content) // 2
                    if used_tokens + tokens > max_tokens:
                        break
                    lines.append(f"  [{cat_label}] {c.content}")
                    used_tokens += tokens

            if len(lines) > 1:
                parts.append("\n".join(lines))

        return "\n\n".join(parts)

    def format_conflict_error(self, new: Constraint, existing: Constraint) -> str:
        """生成冲突错误信息"""
        tier_names = {1: '第一档(已写定)', 2: '第二档(大纲)', 3: '第三档(细纲)'}
        return (
            f"约束冲突！\n"
            f"  新约束：{new.content[:60]}... (等级{tier_names.get(new.tier, '?')})\n"
            f"  已有约束：{existing.content[:60]}... (等级{tier_names.get(existing.tier, '?')})\n"
            f"  冲突规则：高档约束优先，低档约束需服从高档"
        )

    # ── 统计 ────────────────────────────────────────────

    def get_stats(self) -> Dict:
        stats = {}
        for tier in [Tier.IMMUTABLE, Tier.OUTLINE, Tier.CHAPTER]:
            constraints = self._load_tier(tier)
            stats[f'tier{tier.value}'] = len(constraints)
        stats['archive'] = len(list(self.archive_dir.glob('ch*.json'))) if self.archive_dir.exists() else 0
        return stats
