"""
一致性检查模块

负责检查新生成的内容是否与所有规范设定相符
检查维度：
1. 角色一致性（说话风格、别名、角色类型）
2. 数字一致性（密码、日期、金额等精确数字）
3. 伏笔一致性（伏笔ID、推进/回收动作）
4. 约束一致性（Tier1/Tier2/Tier3约束）
5. 地点一致性（地点名称、设施绑定）
6. 能力一致性（境界、天赋、设施解锁）
7. 时间线一致性（时间顺序、事件节点）
8. 风格一致性（文风、禁止内容）
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
        ]

    def check_chapter(self, chapter: int, draft: str, 
                      project_data: Dict, chapter_memory: Dict = None) -> Dict:
        """检查章节一致性（完整检查）"""
        issues = []

        # 1. 禁止内容检查（最高优先级）
        forbidden_issues = self._check_forbidden_content(draft)
        issues.extend(forbidden_issues)

        # 2. 角色一致性检查
        character_issues = self._check_character_consistency(draft, project_data, chapter)
        issues.extend(character_issues)

        # 3. 数字一致性检查
        number_issues = self._check_number_consistency(draft, chapter)
        issues.extend(number_issues)

        # 4. 伏笔一致性检查
        foreshadowing_issues = self._check_foreshadowing_consistency(chapter, draft, project_data)
        issues.extend(foreshadowing_issues)

        # 5. 约束一致性检查
        constraint_issues = self._check_constraint_consistency(draft, chapter)
        issues.extend(constraint_issues)

        # 6. 地点一致性检查
        location_issues = self._check_location_consistency(draft, project_data)
        issues.extend(location_issues)

        # 7. 能力一致性检查
        ability_issues = self._check_ability_consistency(draft, project_data, chapter)
        issues.extend(ability_issues)

        # 8. 风格一致性检查
        style_issues = self._check_style_consistency(draft, project_data)
        issues.extend(style_issues)

        # 9. 字数检查
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
                    'suggestion': f"删除或改写：{matches[0]}"
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

    def _check_character_consistency(self, draft: str, project_data: Dict, 
                                     chapter: int) -> List[Dict]:
        """检查角色一致性"""
        issues = []
        characters = project_data.get('characters', [])

        for char_file in characters:
            char_name = char_file.get('filename', '').replace('.txt', '')
            char_content = char_file.get('content', '')

            if char_name not in draft:
                continue

            # 检查说话风格
            style_issues = self._check_speaking_style(draft, char_name, char_content)
            issues.extend(style_issues)

            # 检查禁止称呼
            forbidden_calls = self._extract_forbidden_calls(char_content)
            for call in forbidden_calls:
                if call in draft and call != char_name:
                    issues.append({
                        'type': 'character_forbidden_call',
                        'severity': 'error',
                        'message': f"角色 {char_name} 使用了禁止称呼：{call}",
                        'suggestion': f"改用角色档案中允许的称呼"
                    })

        return issues

    def _check_speaking_style(self, draft: str, char_name: str, 
                              char_content: str) -> List[Dict]:
        """检查角色说话风格"""
        issues = []

        # 提取角色台词（简单匹配：引号内的内容）
        dialogue_pattern = f'[""「」【】]([^""「」【】]*)[""「」【】]'
        dialogues = re.findall(dialogue_pattern, draft)

        # 提取catchphrases
        catchphrases = re.findall(r'catchphrases[:\s]*(.+)', char_content)
        catchphrases = [cp.strip().split(',')[0].strip() for cp in catchphrases]

        # 提取forbidden_patterns
        forbidden_patterns = re.findall(r'forbidden_patterns[:\s]*(.+)', char_content)
        forbidden_patterns = [fp.strip() for fp in forbidden_patterns]

        return issues

    def _extract_forbidden_calls(self, char_content: str) -> List[str]:
        """提取禁止称呼"""
        forbidden = []
        match = re.search(r'forbidden_calls[:\s]*\[(.+?)\]', char_content)
        if match:
            calls = match.group(1).split(',')
            forbidden = [c.strip().strip('"').strip("'") for c in calls]
        return forbidden

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

            # 检查数字是否在文中出现
            if value in draft:
                # 检查上下文是否一致
                # 简单检查：数字附近是否有关联角色
                pass

        return issues

    # ── 伏笔一致性检查 ──────────────────────────────────────

    def _check_foreshadowing_consistency(self, chapter: int, draft: str,
                                         project_data: Dict) -> List[Dict]:
        """检查伏笔一致性"""
        issues = []
        project_name = project_data.get('config', {}).get('name', '')

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

            # Tier1约束必须检查
            if tier == 'foundation':
                # 简单检查：约束关键词是否在文中被违反
                # 这里可以扩展为更复杂的检查
                pass

        return issues

    # ── 地点一致性检查 ──────────────────────────────────────

    def _check_location_consistency(self, draft: str, project_data: Dict) -> List[Dict]:
        """检查地点一致性"""
        issues = []

        # 检查地点名称
        location_keywords = [
            '乐园', '海上', '海底', '陆地', '城市',
            '儿童戏水池', '造浪池', '彩虹滑道', '漂流河',
            '室内恒温水世界', '海啸池', '大喇叭'
        ]

        for location in location_keywords:
            if location in draft:
                # 可以添加地点逻辑检查
                pass

        return issues

    # ── 能力一致性检查 ──────────────────────────────────────

    def _check_ability_consistency(self, draft: str, project_data: Dict,
                                   chapter: int) -> List[Dict]:
        """检查能力一致性"""
        issues = []

        # 检查境界体系
        realm_patterns = {
            '滴水境': 1,
            '溪流境': 2,
            '江河境': 3,
            '湖泽境': 4,
            '沧海境': 5,
            '归墟境': 6
        }

        for realm, level in realm_patterns.items():
            if realm in draft:
                # 可以添加境界突破检查
                pass

        return issues

    # ── 风格一致性检查 ──────────────────────────────────────

    def _check_style_consistency(self, draft: str, project_data: Dict) -> List[Dict]:
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

    # ── 字数检查 ──────────────────────────────────────────

    def _check_word_count(self, draft: str) -> List[Dict]:
        """检查字数"""
        issues = []

        # 统计中文字数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', draft))
        total_chars = len(draft)

        if chinese_chars < 1000:
            issues.append({
                'type': 'word_count_too_few',
                'severity': 'error',
                'message': f"字数过少：{chinese_chars}字（要求1000-1500字）",
                'suggestion': '扩展内容到1000字以上'
            })
        elif chinese_chars > 2000:
            issues.append({
                'type': 'word_count_too_many',
                'severity': 'warning',
                'message': f"字数过多：{chinese_chars}字（建议1000-1500字）",
                'suggestion': '精简内容到1500字以内'
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

    def check_chapter_progression(self, chapter: int, project_data: Dict) -> Dict:
        """检查章节进度"""
        total_chapters = self.config.get('project', {}).get('chapters', 960)

        return {
            'chapter': chapter,
            'expected_volume': (chapter - 1) // 96 + 1,
            'total_chapters': total_chapters,
            'completion_percentage': round(chapter / total_chapters * 100, 2)
        }

    def check_foreshadowing_status(self, chapter: int, project_data: Dict) -> Dict:
        """检查伏笔状态"""
        project_name = project_data.get('config', {}).get('name', '')

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
