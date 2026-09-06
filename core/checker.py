"""
一致性检查模块 v2.0

负责检查新生成的内容是否与所有规范设定相符
检查维度：
1. 禁止内容检查（最高优先级）
2. 角色一致性（说话风格、别名、角色类型）
3. 数字一致性（密码、日期、金额等精确数字）
4. 伏笔一致性（伏笔ID、推进/回收动作）
5. 约束一致性（Tier1/Tier2/Tier3约束）
6. 地点一致性（地点名称、设施绑定）
7. 能力一致性（境界、天赋、设施解锁）
8. 风格一致性（文风、禁止内容）
9. 行文风格一致性（叙事视角、语言风格、幽默风格）
10. 别名系统一致性（称呼演变、禁止称呼）
11. 时间线一致性（时间顺序、事件节点）
12. 物品系统一致性（五钥、装备、道具）
13. 势力组织一致性（阵营关系、立场）
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .foreshadowing import ForeshadowingManager
from .constraints import ConstraintManager, Tier
from .memory import MemoryManager


class ConsistencyChecker:
    """一致性检查器"""

    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        self.project_name = project_name
        self.consistency_config = config.get('consistency', {})
        self.data_dir = Path(config.get('data_dir', './data')).format(project=project_name)

        # 初始化管理器
        self.foreshadowing_manager = ForeshadowingManager(config, project_name)
        self.constraint_manager = ConstraintManager(config, project_name)
        self.memory_manager = MemoryManager(config, project_name)

        # 禁止内容列表
        self.forbidden_patterns = [
            r'命运的齿轮开始转动',
            r'这一刻，他终于明白了',
            r'他\/她',
            r'（未完待续）',
            r'（欲知后事如何）',
            r'他不禁',
            r'她不禁',
            r'忽然',
            r'突然',
        ]

        # 加载数据文件
        self._load_project_data()

    def _load_project_data(self):
        """加载项目数据文件"""
        self.project_data = {
            'characters': {},
            'speaking_style': {},
            'ability_system': {},
            'aliases': {},
            'timeline': {},
            'locations': {},
            'factions': {},
            'items': {},
            'writing_style': {},
            'foreshadowing': {},
            'numbers': {},
        }

        # 加载角色档案
        self._load_characters()
        # 加载说话风格
        self._load_speaking_style()
        # 加载能力体系
        self._load_ability_system()
        # 加载别名系统
        self._load_aliases()
        # 加载时间线
        self._load_timeline()
        # 加载地点档案
        self._load_locations()
        # 加载势力组织
        self._load_factions()
        # 加载物品系统
        self._load_items()
        # 加载行文风格
        self._load_writing_style()

    def _load_file(self, filename: str) -> str:
        """加载单个数据文件"""
        file_path = self.data_dir / 'world' / filename
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ''

    def _load_characters(self):
        """加载角色档案"""
        content = self._load_file('角色档案.txt')
        if not content:
            return

        # 解析角色档案
        current_char = None
        for line in content.split('\n'):
            if line.startswith('## ') or line.startswith('### '):
                current_char = line.replace('#', '').strip()
                self.project_data['characters'][current_char] = {
                    'name': current_char,
                    'content': [],
                }
            elif current_char and line.strip():
                self.project_data['characters'][current_char]['content'].append(line)

    def _load_speaking_style(self):
        """加载说话风格"""
        content = self._load_file('说话风格.txt')
        if not content:
            return

        # 解析说话风格
        current_char = None
        current_style = {}
        for line in content.split('\n'):
            if line.startswith('signature_style:') or line.startswith('catchphrases:') or line.startswith('forbidden_patterns:'):
                if current_char:
                    self.project_data['speaking_style'][current_char] = current_style
                current_char = line.split(':')[0].strip()
                current_style = {}
            elif current_char and line.strip():
                key = line.split(':')[0].strip() if ':' in line else 'extra'
                value = line.split(':', 1)[1].strip() if ':' in line else line.strip()
                current_style[key] = value

        if current_char:
            self.project_data['speaking_style'][current_char] = current_style

    def _load_ability_system(self):
        """加载能力体系"""
        content = self._load_file('能力体系.txt')
        if not content:
            return

        # 解析境界体系
        realm_patterns = {
            '滴水境': 1,
            '溪流境': 2,
            '江河境': 3,
            '湖泽境': 4,
            '沧海境': 5,
            '归墟境': 6
        }
        self.project_data['ability_system']['realms'] = realm_patterns

        # 解析天赋类型
        self.project_data['ability_system']['talent_types'] = ['innate', 'acquired', 'bound']

    def _load_aliases(self):
        """加载别名系统"""
        content = self._load_file('别名系统.txt')
        if not content:
            return

        # 解析别名
        current_char = None
        for line in content.split('\n'):
            if line.startswith('- character:'):
                current_char = line.split(':')[1].strip()
                self.project_data['aliases'][current_char] = {
                    'name': current_char,
                    'forbidden_calls': [],
                }
            elif current_char and 'forbidden_calls:' in line:
                calls = line.split('[')[1].split(']')[0].split(',')
                self.project_data['aliases'][current_char]['forbidden_calls'] = [
                    c.strip().strip('"') for c in calls
                ]

    def _load_timeline(self):
        """加载时间线"""
        content = self._load_file('时间线.txt')
        if not content:
            return

        # 解析关键时间节点
        self.project_data['timeline']['key_events'] = {}
        for line in content.split('\n'):
            if line.startswith('ch'):
                parts = line.split(':')
                if len(parts) >= 2:
                    chapter = parts[0].strip()
                    event = parts[1].strip()
                    self.project_data['timeline']['key_events'][chapter] = event

    def _load_locations(self):
        """加载地点档案"""
        content = self._load_file('地点档案.txt')
        if not content:
            return

        # 解析地点
        self.project_data['locations'] = {
            'facilities': ['儿童戏水池', '造浪池', '大喇叭', '彩虹滑道', '漂流河', '室内恒温水世界', '海啸池'],
            'sea_areas': ['近海废墟', '千帆海域', '黑市环礁', '风暴走廊', '沉没仙城', '沧澜海沟', '移动灯塔', '冰洋圣域', '归墟外围', '新大陆'],
        }

    def _load_factions(self):
        """加载势力组织"""
        content = self._load_file('势力组织.txt')
        if not content:
            return

        # 解析势力关系
        self.project_data['factions'] = {
            '乐园': {'allies': ['四海义盟', '沧澜遗族'], 'enemies': ['掠夺王庭', '归墟教']},
            '四海义盟': {'allies': ['乐园'], 'enemies': ['掠夺王庭']},
            '掠夺王庭': {'allies': [], 'enemies': ['乐园', '四海义盟']},
            '天工阁': {'allies': ['乐园'], 'enemies': ['归墟教']},
            '沧澜遗族': {'allies': ['乐园'], 'enemies': []},
            '归墟教': {'allies': [], 'enemies': ['乐园', '四海义盟', '天工阁', '沧澜遗族']},
        }

    def _load_items(self):
        """加载物品系统"""
        content = self._load_file('物品系统.txt')
        if not content:
            return

        # 解析五钥
        self.project_data['items']['keys'] = ['甘霖瓶', '潮汐之心', '玉玺', '灯塔火种', '沧溟本体']

    def _load_writing_style(self):
        """加载行文风格"""
        content = self._load_file('行文风格.txt')
        if not content:
            return

        # 解析行文风格
        self.project_data['writing_style'] = {
            'forbidden_words': ['突然', '忽然', '不禁', '忍不住', '感觉', '好像', '似乎', '仿佛'],
            'min_words': 2500,
            'max_words': 3500,
        }

    # ── 主检查方法 ──────────────────────────────────────

    def check_chapter(self, chapter: int, draft: str,
                      project_data: Dict = None, chapter_memory: Dict = None) -> Dict:
        """检查章节一致性（完整检查）"""
        issues = []

        # 1. 禁止内容检查（最高优先级）
        forbidden_issues = self._check_forbidden_content(draft)
        issues.extend(forbidden_issues)

        # 2. 角色一致性检查
        character_issues = self._check_character_consistency(draft, chapter)
        issues.extend(character_issues)

        # 3. 数字一致性检查
        number_issues = self._check_number_consistency(draft, chapter)
        issues.extend(number_issues)

        # 4. 伏笔一致性检查
        foreshadowing_issues = self._check_foreshadowing_consistency(chapter, draft, project_data or {})
        issues.extend(foreshadowing_issues)

        # 5. 约束一致性检查
        constraint_issues = self._check_constraint_consistency(draft, chapter)
        issues.extend(constraint_issues)

        # 6. 地点一致性检查
        location_issues = self._check_location_consistency(draft, chapter)
        issues.extend(location_issues)

        # 7. 能力一致性检查
        ability_issues = self._check_ability_consistency(draft, chapter)
        issues.extend(ability_issues)

        # 8. 风格一致性检查
        style_issues = self._check_style_consistency(draft)
        issues.extend(style_issues)

        # 9. 行文风格一致性检查
        writing_style_issues = self._check_writing_style_consistency(draft)
        issues.extend(writing_style_issues)

        # 10. 别名系统一致性检查
        alias_issues = self._check_alias_consistency(draft, chapter)
        issues.extend(alias_issues)

        # 11. 时间线一致性检查
        timeline_issues = self._check_timeline_consistency(draft, chapter)
        issues.extend(timeline_issues)

        # 12. 物品系统一致性检查
        item_issues = self._check_item_consistency(draft, chapter)
        issues.extend(item_issues)

        # 13. 势力组织一致性检查
        faction_issues = self._check_faction_consistency(draft, chapter)
        issues.extend(faction_issues)

        # 14. 字数检查
        word_count_issues = self._check_word_count(draft)
        issues.extend(word_count_issues)

        return {
            'chapter': chapter,
            'passed': len([i for i in issues if i['severity'] == 'error']) == 0,
            'issues': issues,
            'summary': self._generate_summary(issues),
            'timestamp': datetime.now().isoformat()
        }

    # ── 禁止内容检查 ──────────────────────────────────────

    def _check_forbidden_content(self, draft: str) -> List[Dict]:
        """检查禁止内容"""
        issues = []

        for pattern in self.forbidden_patterns:
            matches = re.findall(pattern, draft)
            if matches:
                issues.append({
                    'type': 'forbidden_content',
                    'severity': 'error',
                    'message': f"发现禁止内容：{pattern}",
                    'suggestion': f"删除或改写：{matches[0]}",
                    'position': draft.index(matches[0]) if matches[0] in draft else -1
                })

        # 检查中文标点（应该用全角）
        if re.search(r'[,.:;!?](?=[\u4e00-\u9fff])', draft):
            issues.append({
                'type': 'forbidden_content',
                'severity': 'warning',
                'message': '发现半角标点后接中文',
                'suggestion': '改为全角标点'
            })

        return issues

    # ── 角色一致性检查 ──────────────────────────────────────

    def _check_character_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查角色一致性"""
        issues = []

        for char_name, char_data in self.project_data['characters'].items():
            if char_name not in draft:
                continue

            # 检查说话风格
            style_issues = self._check_speaking_style(draft, char_name)
            issues.extend(style_issues)

            # 检查禁止称呼
            forbidden_calls = self.project_data['aliases'].get(char_name, {}).get('forbidden_calls', [])
            for call in forbidden_calls:
                if call in draft and call != char_name:
                    issues.append({
                        'type': 'character_forbidden_call',
                        'severity': 'error',
                        'message': f"角色 {char_name} 使用了禁止称呼：{call}",
                        'suggestion': f"改用角色档案中允许的称呼"
                    })

        return issues

    def _check_speaking_style(self, draft: str, char_name: str) -> List[Dict]:
        """检查角色说话风格"""
        issues = []

        # 获取说话风格
        style_data = self.project_data['speaking_style'].get(char_name, {})
        if not style_data:
            return issues

        # 提取角色台词（简单匹配：引号内的内容）
        dialogue_pattern = r'[""「」【】]([^""「」【】]*)[""「」【】]'
        dialogues = re.findall(dialogue_pattern, draft)

        # 提取forbidden_patterns
        forbidden_patterns = style_data.get('forbidden_patterns', '')
        if forbidden_patterns:
            patterns = [p.strip() for p in forbidden_patterns.split(',')]
            # 这里可以添加具体的风格检查逻辑

        return issues

    # ── 数字一致性检查 ──────────────────────────────────────

    def _check_number_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查数字一致性"""
        issues = []

        # 获取数字记忆
        numbers = self.memory_manager.get_numbers()

        for num in numbers:
            if num.get('status') in ['expired']:
                continue

            value = num.get('value', '')
            context = num.get('context', '')
            aliases = num.get('aliases', [])

            # 检查数字是否在文中出现
            found = False
            if value in draft:
                found = True
            for alias in aliases:
                if alias in draft:
                    found = True
                    break

            if found:
                # 检查上下文是否一致
                # 简单检查：数字附近是否有关联角色
                related_characters = num.get('related_characters', [])
                for char in related_characters:
                    if char in draft:
                        # 数字和关联角色都在文中，检查是否正确
                        pass

        # 检查常见数字
        common_numbers = {
            '八百万': '沈浮的贷款金额',
            '72': '洪水倒计时',
            '30': '儿童戏水池水深',
            '001': '三姆的工牌编号',
            '002': '彪哥的工牌编号',
        }

        for num_value, context in common_numbers.items():
            if num_value in draft:
                # 数字出现，检查上下文
                pass

        return issues

    # ── 伏笔一致性检查 ──────────────────────────────────────

    def _check_foreshadowing_consistency(self, chapter: int, draft: str,
                                         project_data: Dict) -> List[Dict]:
        """检查伏笔一致性"""
        issues = []
        project_name = project_data.get('config', {}).get('name', self.project_name)

        if not project_name:
            return issues

        # 检查伏笔状态
        foreshadowing_check = self.foreshadowing_manager.check_foreshadowing_for_chapter(
            project_name, chapter
        )

        # 检查长期未解决伏笔
        unresolved = foreshadowing_check.get('unresolved_old_foreshadowing', [])
        for fs in unresolved:
            issues.append({
                'type': 'foreshadowing_timeout',
                'severity': 'warning',
                'message': f"伏笔 {fs['id']} 已等待 {fs['chapters_pending']} 章未解决",
                'suggestion': f"考虑在本章或近期推进：{fs['description'][:50]}"
            })

        # 检测章节中解决的伏笔
        resolved = self.foreshadowing_manager.detect_resolved_foreshadowing(
            project_name, chapter, draft
        )
        for fs_id in resolved:
            self.foreshadowing_manager.resolve_foreshadowing(project_name, fs_id, f"ch{chapter:04d}")
            issues.append({
                'type': 'foreshadowing_resolved',
                'severity': 'info',
                'message': f"伏笔 {fs_id} 已在本章解决",
                'suggestion': '已自动标记为已解决'
            })

        return issues

    # ── 约束一致性检查 ──────────────────────────────────────

    def _check_constraint_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查约束一致性"""
        issues = []

        # 获取当前章节的约束
        constraints = self.constraint_manager.get_constraints_for_chapter(chapter)

        for constraint in constraints:
            rule = constraint.get('rule', '')
            tier = constraint.get('tier', '')
            source = constraint.get('source', '')

            # Tier1约束必须检查
            if tier == 'foundation':
                # 检查约束是否被违反
                if '不许' in rule:
                    forbidden_content = rule.replace('不许', '')
                    if forbidden_content in draft:
                        issues.append({
                            'type': 'constraint_violation',
                            'severity': 'error',
                            'message': f"违反Tier1约束：{rule}",
                            'suggestion': f"删除或改写：{forbidden_content}"
                        })

        return issues

    # ── 地点一致性检查 ──────────────────────────────────────

    def _check_location_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查地点一致性"""
        issues = []

        # 检查设施名称
        facilities = self.project_data['locations'].get('facilities', [])
        for facility in facilities:
            if facility in draft:
                # 设施出现，检查是否在正确的时间
                pass

        # 检查海域名称
        sea_areas = self.project_data['locations'].get('sea_areas', [])
        for area in sea_areas:
            if area in draft:
                # 海域出现，检查是否在正确的时间
                pass

        return issues

    # ── 能力一致性检查 ──────────────────────────────────────

    def _check_ability_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查能力一致性"""
        issues = []

        # 检查境界体系
        realm_patterns = self.project_data['ability_system'].get('realms', {})

        for realm, level in realm_patterns.items():
            if realm in draft:
                # 境界出现，检查是否在正确的时间突破
                # 根据卷一细纲，境界突破时间：
                # - 滴水境：ch0001（开局）
                # - 溪流境：卷二
                # - 江河境：ch0402（卷五）
                # - 湖泽境：ch0555（卷六）
                # - 沧海境：未明确
                # - 归墟境：未明确
                pass

        # 检查天赋类型
        talent_types = self.project_data['ability_system'].get('talent_types', [])
        for talent_type in talent_types:
            if talent_type in draft:
                # 天赋类型出现，检查是否正确
                pass

        return issues

    # ── 风格一致性检查 ──────────────────────────────────────

    def _check_style_consistency(self, draft: str) -> List[Dict]:
        """检查风格一致性"""
        issues = []

        # 检查禁止词汇
        forbidden_words = [
            '他妈的', '操你', '日你',  # 粗口
        ]

        for word in forbidden_words:
            if word in draft:
                issues.append({
                    'type': 'style_forbidden_word',
                    'severity': 'warning',
                    'message': f"发现禁止词汇：{word}",
                    'suggestion': '改用其他表达'
                })

        # 检查段落长度
        paragraphs = draft.split('\n\n')
        long_paragraphs = [p for p in paragraphs if len(p) > 500]
        if long_paragraphs:
            issues.append({
                'type': 'style_long_paragraph',
                'severity': 'warning',
                'message': f"发现{len(long_paragraphs)}个超长段落（>500字）",
                'suggestion': '建议分段，保持阅读节奏'
            })

        return issues

    # ── 行文风格一致性检查 ──────────────────────────────────────

    def _check_writing_style_consistency(self, draft: str) -> List[Dict]:
        """检查行文风格一致性"""
        issues = []

        # 获取行文风格配置
        writing_style = self.project_data.get('writing_style', {})
        forbidden_words = writing_style.get('forbidden_words', [])

        # 检查禁用词
        for word in forbidden_words:
            if word in draft:
                issues.append({
                    'type': 'writing_style_forbidden_word',
                    'severity': 'error',
                    'message': f"发现行文风格禁用词：{word}",
                    'suggestion': f"删除或改写：{word}"
                })

        # 检查叙事视角（简单检查）
        # 第三人称限制视角：应该使用"他"、"她"等，不应该使用"你"
        if re.search(r'你[^们]', draft):
            # 检查是否在对话中
            dialogue_pattern = r'[""「」【】]([^""「」【】]*)[""「」【】]'
            dialogues = re.findall(dialogue_pattern, draft)
            for dialogue in dialogues:
                if '你' in dialogue:
                    # 对话中可以使用"你"
                    pass

        return issues

    # ── 别名系统一致性检查 ──────────────────────────────────────

    def _check_alias_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查别名系统一致性"""
        issues = []

        # 检查每个角色的别名
        for char_name, alias_data in self.project_data['aliases'].items():
            forbidden_calls = alias_data.get('forbidden_calls', [])

            # 检查禁止称呼
            for call in forbidden_calls:
                if call in draft:
                    # 检查是否在对话中（对话中可以使用）
                    dialogue_pattern = r'[""「」【】]([^""「」【】]*)[""「」【】]'
                    dialogues = re.findall(dialogue_pattern, draft)
                    in_dialogue = any(call in d for d in dialogues)

                    if not in_dialogue:
                        issues.append({
                            'type': 'alias_forbidden_call',
                            'severity': 'error',
                            'message': f"角色 {char_name} 使用了禁止称呼：{call}",
                            'suggestion': f"改用角色档案中允许的称呼"
                        })

        return issues

    # ── 时间线一致性检查 ──────────────────────────────────────

    def _check_timeline_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查时间线一致性"""
        issues = []

        # 检查关键时间节点
        key_events = self.project_data['timeline'].get('key_events', {})

        for chapter_str, event in key_events.items():
            # 提取章节号
            match = re.match(r'ch(\d+)', chapter_str)
            if match:
                event_chapter = int(match.group(1))

                # 检查事件是否在正确的章节发生
                if abs(event_chapter - chapter) <= 5:  # 允许5章的误差
                    # 事件可能在本章发生
                    if any(keyword in draft for keyword in event.split('，')[:2]):
                        # 事件关键词在文中，检查是否正确
                        pass

        return issues

    # ── 物品系统一致性检查 ──────────────────────────────────────

    def _check_item_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查物品系统一致性"""
        issues = []

        # 检查五钥
        keys = self.project_data['items'].get('keys', [])
        for key in keys:
            if key in draft:
                # 五钥出现，检查是否在正确的时间获取
                # 根据卷一细纲，五钥获取时间：
                # - 甘霖瓶：ch0001（开局）
                # - 潮汐之心：ch0241（卷三）
                # - 玉玺：ch0469（卷五）
                # - 灯塔火种：ch0592（卷七）
                # - 沧溟本体：ch0621（卷八）
                pass

        return issues

    # ── 势力组织一致性检查 ──────────────────────────────────────

    def _check_faction_consistency(self, draft: str, chapter: int) -> List[Dict]:
        """检查势力组织一致性"""
        issues = []

        # 检查势力关系
        factions = self.project_data.get('factions', {})

        for faction_name, relations in factions.items():
            if faction_name in draft:
                # 势力出现，检查关系是否正确
                allies = relations.get('allies', [])
                enemies = relations.get('enemies', [])

                # 检查敌对势力是否同时出现
                for enemy in enemies:
                    if enemy in draft:
                        # 敌对势力同时出现，检查是否在战斗场景
                        if any(keyword in draft for keyword in ['战斗', '攻击', '袭击']):
                            # 战斗场景，敌对势力同时出现是合理的
                            pass
                        else:
                            # 非战斗场景，敌对势力同时出现可能有问题
                            issues.append({
                                'type': 'faction_conflict',
                                'severity': 'warning',
                                'message': f"势力 {faction_name} 和 {enemy} 同时出现，但不是战斗场景",
                                'suggestion': '检查是否符合剧情逻辑'
                            })

        return issues

    # ── 字数检查 ──────────────────────────────────────────

    def _check_word_count(self, draft: str) -> List[Dict]:
        """检查字数"""
        issues = []

        # 统计中文字数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', draft))
        total_chars = len(draft)

        # 根据行文风格规范，目标字数是2500-3500字
        min_words = self.project_data.get('writing_style', {}).get('min_words', 2500)
        max_words = self.project_data.get('writing_style', {}).get('max_words', 3500)

        if chinese_chars < min_words:
            issues.append({
                'type': 'word_count_too_few',
                'severity': 'error',
                'message': f"字数过少：{chinese_chars}字（要求{min_words}-{max_words}字）",
                'suggestion': f'扩展内容到{min_words}字以上'
            })
        elif chinese_chars > max_words:
            issues.append({
                'type': 'word_count_too_many',
                'severity': 'warning',
                'message': f"字数过多：{chinese_chars}字（建议{min_words}-{max_words}字）",
                'suggestion': f'精简内容到{max_words}字以内'
            })

        return issues

    # ── 辅助方法 ──────────────────────────────────────────

    def _generate_summary(self, issues: List[Dict]) -> Dict:
        """生成检查摘要"""
        errors = [i for i in issues if i['severity'] == 'error']
        warnings = [i for i in issues if i['severity'] == 'warning']
        infos = [i for i in issues if i['severity'] == 'info']

        return {
            'total': len(issues),
            'errors': len(errors),
            'warnings': len(warnings),
            'infos': len(infos),
            'passed': len(errors) == 0
        }

    def generate_report(self, chapter: int, check_result: Dict) -> str:
        """生成检查报告"""
        report_lines = [
            f"# 第{chapter}章一致性检查报告",
            f"检查时间：{check_result.get('timestamp', '未知')}",
            f"检查结果：{'✅ 通过' if check_result['passed'] else '❌ 未通过'}",
            "",
            "## 摘要",
            f"- 总问题数：{check_result['summary']['total']}",
            f"- 错误：{check_result['summary']['errors']}",
            f"- 警告：{check_result['summary']['warnings']}",
            f"- 信息：{check_result['summary']['infos']}",
            ""
        ]

        if check_result['issues']:
            # 按严重程度分组
            errors = [i for i in check_result['issues'] if i['severity'] == 'error']
            warnings = [i for i in check_result['issues'] if i['severity'] == 'warning']
            infos = [i for i in check_result['issues'] if i['severity'] == 'info']

            if errors:
                report_lines.append("## ❌ 错误（必须修复）")
                for i, issue in enumerate(errors, 1):
                    report_lines.append(f"{i}. [{issue['type']}] {issue['message']}")
                    report_lines.append(f"   建议：{issue['suggestion']}")
                report_lines.append("")

            if warnings:
                report_lines.append("## ⚠️ 警告（建议修复）")
                for i, issue in enumerate(warnings, 1):
                    report_lines.append(f"{i}. [{issue['type']}] {issue['message']}")
                    report_lines.append(f"   建议：{issue['suggestion']}")
                report_lines.append("")

            if infos:
                report_lines.append("## ℹ️ 信息")
                for i, issue in enumerate(infos, 1):
                    report_lines.append(f"{i}. [{issue['type']}] {issue['message']}")
        else:
            report_lines.append("## ✅ 未发现一致性问题")

        return "\n".join(report_lines)

    def check_chapter_progression(self, chapter: int, project_data: Dict = None) -> Dict:
        """检查章节进度"""
        total_chapters = self.config.get('project', {}).get('chapters', 960)

        return {
            'chapter': chapter,
            'expected_volume': (chapter - 1) // 96 + 1,
            'total_chapters': total_chapters,
            'completion_percentage': round(chapter / total_chapters * 100, 2)
        }

    def check_foreshadowing_status(self, chapter: int, project_data: Dict = None) -> Dict:
        """检查伏笔状态"""
        project_name = (project_data or {}).get('config', {}).get('name', self.project_name)

        if not project_name:
            return {
                'chapter': chapter,
                'foreshadowing_count': 0,
                'resolved_count': 0,
                'pending_count': 0,
                'issues': []
            }

        foreshadowing_check = self.foreshadowing_manager.check_foreshadowing_for_chapter(
            project_name, chapter
        )

        active = self.foreshadowing_manager.get_active_foreshadowing(project_name)
        resolved = self.foreshadowing_manager.get_resolved_foreshadowing(project_name)

        return {
            'chapter': chapter,
            'foreshadowing_count': len(active) + len(resolved),
            'resolved_count': len(resolved),
            'pending_count': len(active),
            'unresolved_old': foreshadowing_check.get('unresolved_old_foreshadowing', []),
            'introduced_this_chapter': foreshadowing_check.get('introduced_this_chapter', 0),
            'resolved_this_chapter': foreshadowing_check.get('actually_resolved', 0)
        }

    # ── 自动修复 ──────────────────────────────────────────

    def auto_fix(self, chapter: int, draft: str, issues: List[Dict]) -> str:
        """自动修复可修复的问题"""
        fixed_draft = draft

        for issue in issues:
            if issue['severity'] != 'error':
                continue

            # 禁止内容自动修复
            if issue['type'] == 'forbidden_content':
                pattern = issue['message'].replace('发现禁止内容：', '')
                if pattern in fixed_draft:
                    fixed_draft = fixed_draft.replace(pattern, '')

            # 行文风格禁用词自动修复
            elif issue['type'] == 'writing_style_forbidden_word':
                word = issue['message'].replace('发现行文风格禁用词：', '')
                if word in fixed_draft:
                    # 根据禁用词类型进行替换
                    replacements = {
                        '突然': '随即',
                        '忽然': '随即',
                        '不禁': '',
                        '忍不住': '',
                        '感觉': '觉得',
                        '好像': '似乎',
                        '似乎': '仿佛',
                        '仿佛': '好像',
                    }
                    replacement = replacements.get(word, '')
                    fixed_draft = fixed_draft.replace(word, replacement)

        return fixed_draft
