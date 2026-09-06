"""
上下文引擎模块

负责构建写作上下文，管理Token预算，进行智能检索。
核心功能：
1. 滑动窗口读取前文（最近N章原文 + 更早章节摘要）
2. Token预算分配和控制
3. 智能截断确保不超限
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .foreshadowing import ForeshadowingManager
from .chapter_connection import ChapterConnectionManager


def estimate_tokens(text: str) -> int:
    """估算文本的Token数
    
    粗略估算规则（适用于中文为主的文本）：
    - 1个中文字符 ≈ 1.5 token
    - 1个英文单词 ≈ 1 token
    - 1个标点符号 ≈ 0.5 token
    
    实际token数可能有±20%的偏差，但对于预算控制足够了。
    """
    if not text:
        return 0
    
    # 统计中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 统计英文单词
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    # 统计标点和其他字符
    other_chars = len(text) - chinese_chars - sum(len(w) for w in re.findall(r'[a-zA-Z]+', text))
    
    tokens = int(chinese_chars * 1.5 + english_words + other_chars * 0.5)
    return max(tokens, 1)


class ContextEngine:
    """上下文引擎"""
    
    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        self.context_config = config['context']
        self.budget_config = self.context_config['budget']
        self.prev_chapter_config = self.context_config.get('previous_chapters', {})
        self.retrieval_config = self.context_config['retrieval']
        
        # 总Token窗口
        self.total_window = self.context_config.get('total_window', 128000)
        
        # 前文读取配置
        self.read_chapters = self.prev_chapter_config.get('read_chapters', 5)
        self.summary_chapters = self.prev_chapter_config.get('summary_chapters', 20)
        self.summary_max_tokens = self.prev_chapter_config.get('summary_max_tokens', 300)
        self.truncate_from = self.prev_chapter_config.get('truncate_from', 'oldest')
        
        # 初始化管理器
        self.foreshadowing_manager = ForeshadowingManager(config, project_name)
        self.connection_manager = ChapterConnectionManager(config, project_name)
        
        # Token使用跟踪
        self.token_usage = {}
    
    def build_writing_context(self, project_data: Dict, chapter: int, 
                            volume: Optional[int] = None) -> Dict:
        """构建写作上下文"""
        if volume is None:
            volume = (chapter - 1) // 96 + 1
        
        project_name = project_data.get('config', {}).get('name', '')
        storage = self._get_storage(project_name)
        
        # === 第一步：计算各部分的Token预算 ===
        budget = self._calculate_token_budget()
        
        # === 第二步：加载各部分内容并控制Token ===
        context = {
            'chapter': chapter,
            'volume': volume,
            'total_window': self.total_window,
            'token_budget': budget,
        }
        
        # 2.1 系统规则（固定内容）
        system_rules = self._load_system_rules()
        context['system_rules'] = system_rules
        context['system_rules_tokens'] = estimate_tokens(system_rules)
        
        # 2.2 角色卡片（按预算截断）
        characters = self._load_relevant_characters(project_data, chapter, budget['character_cards'])
        context['character_cards'] = characters
        context['character_cards_tokens'] = sum(estimate_tokens(c.get('content', '')) for c in characters)
        
        # 2.3 世界观设定（按预算截断）
        world = self._load_relevant_world(project_data, chapter, budget['world_settings'])
        context['world_settings'] = world
        context['world_settings_tokens'] = sum(estimate_tokens(v) for v in world.values())
        
        # 2.4 本章大纲
        outline = self._load_chapter_outline(project_data, chapter, volume, budget['current_outline'])
        context['current_outline'] = outline
        context['current_outline_tokens'] = estimate_tokens(outline)
        
        # 2.5 前文正文（滑动窗口，核心功能）
        previous_chapters = self._load_previous_chapters(
            project_name, chapter, storage, budget['previous_chapters']
        )
        context['previous_chapters'] = previous_chapters
        context['previous_chapters_tokens'] = sum(
            estimate_tokens(ch['content']) for ch in previous_chapters
        )
        
        # 2.6 历史摘要（更早章节的摘要）
        summaries = self._load_chapter_summaries(
            project_name, chapter, storage, budget['summaries']
        )
        context['summaries'] = summaries
        context['summaries_tokens'] = sum(estimate_tokens(s['content']) for s in summaries)
        
        # 2.7 动态事实表
        facts = self._load_relevant_facts(project_name, chapter, storage, budget['facts'])
        context['facts'] = facts
        context['facts_tokens'] = sum(estimate_tokens(f.get('content', '')) for f in facts)
        
        # 2.8 伏笔信息
        active_foreshadowing = self.foreshadowing_manager.get_active_foreshadowing(project_name)
        foreshadowing_check = self.foreshadowing_manager.check_foreshadowing_for_chapter(project_name, chapter)
        fs_text = self._format_foreshadowing(active_foreshadowing, foreshadowing_check, budget['foreshadowing'])
        context['active_foreshadowing'] = [fs.description for fs in active_foreshadowing[:10]]
        context['foreshadowing_check'] = foreshadowing_check
        context['foreshadowing_text'] = fs_text
        context['foreshadowing_tokens'] = estimate_tokens(fs_text)
        
        # 2.9 章节衔接提示
        connection_check = self.connection_manager.check_chapter_connection(project_name, chapter)
        transition_prompt = self.connection_manager.generate_chapter_transition_prompt(project_name, chapter)
        transition_text = self._format_transition(transition_prompt, connection_check, budget['transition'])
        context['chapter_connection'] = connection_check
        context['transition_prompt'] = transition_prompt
        context['transition_text'] = transition_text
        context['transition_tokens'] = estimate_tokens(transition_text)
        
        # === 第三步：计算总Token使用量 ===
        total_used = sum([
            context['system_rules_tokens'],
            context['character_cards_tokens'],
            context['world_settings_tokens'],
            context['current_outline_tokens'],
            context['previous_chapters_tokens'],
            context['summaries_tokens'],
            context['facts_tokens'],
            context['foreshadowing_tokens'],
            context['transition_tokens'],
        ])
        
        context['total_input_tokens'] = total_used
        context['remaining_tokens'] = self.total_window - total_used - budget['output_reserve']
        context['is_over_budget'] = total_used > (self.total_window - budget['output_reserve'])
        
        self.token_usage = context
        
        return context
    
    def _get_storage(self, project_name: str):
        """获取存储管理器（延迟导入避免循环引用）"""
        from .storage import StorageManager
        return StorageManager(self.config, project_name)
    
    def _calculate_token_budget(self) -> Dict:
        """计算Token预算"""
        budget = {}
        for key, percentage in self.budget_config.items():
            budget[key] = int(self.total_window * percentage / 100)
        return budget
    
    def _load_system_rules(self) -> str:
        """加载系统规则"""
        rules = """# 写作系统规则

## 基本要求
1. 每章1000-1500字
2. 保持角色性格一致
3. 遵循世界观设定
4. 按照大纲推进剧情

## 风格要求
1. 轻快、嘴碎、理直气壮的荒诞
2. 惨是垫场，嗨是正片
3. 笑点来自处境反差和档案乱码的毒舌
4. 爽点当天结算，绝不过夜

## 禁止事项
1. 不致郁
2. 不使用原作人名与商标词
3. 不写'命运的齿轮开始转动'
4. 不写'这一刻，他终于明白了'"""
        return rules
    
    def _load_relevant_characters(self, project_data: Dict, chapter: int, 
                                 budget_tokens: int) -> List[Dict]:
        """加载相关角色（按Token预算截断）"""
        characters = project_data.get('characters', [])
        
        relevant_chars = []
        used_tokens = 0
        
        for char in characters:
            content = char.get('content', '')
            name = char.get('filename', '').replace('.txt', '')
            tokens = estimate_tokens(content)
            
            # 如果加入这个角色会超预算，截断内容
            if used_tokens + tokens > budget_tokens:
                remaining = budget_tokens - used_tokens
                if remaining > 100:  # 至少保留100 token的内容
                    truncated_content = content[:int(remaining / 1.5)]
                    relevant_chars.append({'name': name, 'content': truncated_content})
                break
            
            relevant_chars.append({'name': name, 'content': content})
            used_tokens += tokens
        
        return relevant_chars
    
    def _load_relevant_world(self, project_data: Dict, chapter: int, 
                            budget_tokens: int) -> Dict:
        """加载相关世界观（按Token预算截断）"""
        world = project_data.get('world', {})
        
        relevant_world = {}
        used_tokens = 0
        
        for key, content in world.items():
            tokens = estimate_tokens(content)
            
            if used_tokens + tokens > budget_tokens:
                remaining = budget_tokens - used_tokens
                if remaining > 100:
                    relevant_world[key] = content[:int(remaining / 1.5)]
                break
            
            relevant_world[key] = content
            used_tokens += tokens
        
        return relevant_world
    
    def _load_chapter_outline(self, project_data: Dict, chapter: int, volume: int,
                             budget_tokens: int) -> str:
        """加载章节大纲（按Token预算截断）"""
        outline = project_data.get('outline', [])
        
        # 查找本章大纲
        for outline_item in outline:
            content = outline_item.get('content', '')
            if f"ch{chapter:03d}" in content or f"第{chapter}章" in content:
                if estimate_tokens(content) <= budget_tokens:
                    return content
                return content[:int(budget_tokens / 1.5)]
        
        # 查找卷大纲
        for outline_item in outline:
            content = outline_item.get('content', '')
            if f"卷{volume}" in content:
                if estimate_tokens(content) <= budget_tokens:
                    return content
                return content[:int(budget_tokens / 1.5)]
        
        return ""
    
    def _load_previous_chapters(self, project_name: str, current_chapter: int,
                               storage, budget_tokens: int) -> List[Dict]:
        """加载前文正文（滑动窗口策略）
        
        策略：
        1. 读取最近 N 章的完整原文（read_chapters）
        2. 如果 Token 超预算，从最远的章节开始截断
        """
        if current_chapter <= 1:
            return []
        
        # 确定要读取的章节范围
        start_chapter = max(1, current_chapter - self.read_chapters)
        end_chapter = current_chapter - 1
        
        chapters = []
        used_tokens = 0
        
        # 按时间顺序加载（从远到近）
        for ch in range(start_chapter, end_chapter + 1):
            content = storage.load_chapter(ch)
            if not content:
                continue
            
            tokens = estimate_tokens(content)
            
            # 如果加入这章会超预算
            if used_tokens + tokens > budget_tokens:
                remaining = budget_tokens - used_tokens
                if remaining > 200:
                    # 截断这章的内容
                    truncated = content[:int(remaining / 1.5)]
                    chapters.append({
                        'chapter': ch,
                        'content': truncated,
                        'is_truncated': True,
                        'original_tokens': tokens,
                        'truncated_tokens': remaining
                    })
                break
            
            chapters.append({
                'chapter': ch,
                'content': content,
                'is_truncated': False,
                'original_tokens': tokens,
                'truncated_tokens': tokens
            })
            used_tokens += tokens
        
        # 按时间倒序排列（最近的在前）
        chapters.sort(key=lambda x: x['chapter'], reverse=True)
        
        return chapters
    
    def _load_chapter_summaries(self, project_name: str, current_chapter: int,
                               storage, budget_tokens: int) -> List[Dict]:
        """加载历史摘要（更早章节的摘要）
        
        策略：
        1. 读取 read_chapters 之前到 summary_chapters 范围的摘要
        2. 按时间倒序排列
        3. 按Token预算截断
        """
        from .memory import MemoryManager
        memory = MemoryManager(self.config, project_name)
        
        # 摘要范围：从 max(1, current - read_chapters - summary_chapters) 到 max(1, current - read_chapters)
        summary_end = max(1, current_chapter - self.read_chapters)
        summary_start = max(1, summary_end - self.summary_chapters)
        
        if summary_start >= summary_end:
            return []
        
        chapter_range = list(range(summary_start, summary_end))
        summaries = memory.get_summaries(chapters=chapter_range)
        
        # 按时间倒序排列
        summaries.sort(key=lambda x: x.get('chapter', 0), reverse=True)
        
        # 按Token预算截断
        result = []
        used_tokens = 0
        
        for summary in summaries:
            content = summary.get('content', '')
            # 限制每章摘要的长度
            if estimate_tokens(content) > self.summary_max_tokens:
                content = content[:int(self.summary_max_tokens / 1.5)]
            
            tokens = estimate_tokens(content)
            
            if used_tokens + tokens > budget_tokens:
                break
            
            result.append({
                'chapter': summary.get('chapter', 0),
                'content': content,
                'tokens': tokens
            })
            used_tokens += tokens
        
        return result
    
    def _load_relevant_facts(self, project_name: str, chapter: int,
                            storage, budget_tokens: int) -> List[Dict]:
        """加载相关事实（按Token预算截断）"""
        from .memory import MemoryManager
        memory = MemoryManager(self.config, project_name)
        
        # 获取最近50章的事实
        start_chapter = max(1, chapter - 50)
        chapter_range = list(range(start_chapter, chapter))
        
        facts = memory.get_facts(chapter_range=chapter_range)
        
        # 按重要性排序（high > medium > low）
        importance_order = {'high': 0, 'medium': 1, 'low': 2}
        facts.sort(key=lambda x: importance_order.get(x.get('importance', 'medium'), 1))
        
        # 按Token预算截断
        result = []
        used_tokens = 0
        
        for fact in facts:
            content = fact.get('content', '')
            tokens = estimate_tokens(content)
            
            if used_tokens + tokens > budget_tokens:
                break
            
            result.append(fact)
            used_tokens += tokens
        
        return result
    
    def _format_foreshadowing(self, active_foreshadowing, foreshadowing_check, 
                             budget_tokens: int) -> str:
        """格式化伏笔信息（按Token预算截断）"""
        parts = []
        used_tokens = 0
        
        # 活跃伏笔列表
        fs_list = []
        for fs in active_foreshadowing[:10]:
            entry = f"- {fs.id}: {fs.description[:80]}"
            if estimate_tokens(entry) + used_tokens <= budget_tokens:
                fs_list.append(entry)
                used_tokens += estimate_tokens(entry)
        
        if fs_list:
            parts.append("### 活跃伏笔\n" + "\n".join(fs_list))
        
        # 长期未解决伏笔
        unresolved = foreshadowing_check.get('unresolved_old_foreshadowing', [])
        if unresolved:
            unresolved_list = []
            for fs in unresolved:
                entry = f"- {fs['id']}: {fs['description'][:50]}... (等待{fs['chapters_pending']}章)"
                if estimate_tokens(entry) + used_tokens <= budget_tokens:
                    unresolved_list.append(entry)
                    used_tokens += estimate_tokens(entry)
            
            if unresolved_list:
                parts.append("### 长期未解决伏笔\n" + "\n".join(unresolved_list))
        
        return "\n\n".join(parts)
    
    def _format_transition(self, transition_prompt: str, connection_check: Dict,
                          budget_tokens: int) -> str:
        """格式化衔接信息（按Token预算截断）"""
        parts = []
        used_tokens = 0
        
        # 过渡提示
        if transition_prompt and estimate_tokens(transition_prompt) <= budget_tokens:
            parts.append(transition_prompt)
            used_tokens += estimate_tokens(transition_prompt)
        
        # 衔接问题
        issues = connection_check.get('issues', [])
        if issues:
            issue_text = "### 衔接问题\n" + "\n".join(f"- {issue}" for issue in issues)
            if estimate_tokens(issue_text) + used_tokens <= budget_tokens:
                parts.append(issue_text)
        
        return "\n\n".join(parts)
    
    def format_context_for_llm(self, context: Dict) -> str:
        """格式化上下文为LLM输入"""
        formatted_parts = []
        
        # 系统规则
        if context.get('system_rules'):
            formatted_parts.append(f"## 系统规则\n{context['system_rules']}")
        
        # 章节衔接提示
        transition_text = context.get('transition_text', '')
        if transition_text:
            formatted_parts.append(f"## 章节衔接提示\n{transition_text}")
        
        # 角色卡片
        characters = context.get('character_cards', [])
        if characters:
            chars_text = "\n".join([
                f"### {char.get('name', '未命名')}\n{char.get('content', '')}"
                for char in characters
            ])
            formatted_parts.append(f"## 角色档案\n{chars_text}")
        
        # 世界观设定
        world = context.get('world_settings', {})
        if world:
            world_text = "\n".join([
                f"### {key}\n{value}" for key, value in world.items()
            ])
            formatted_parts.append(f"## 世界观设定\n{world_text}")
        
        # 本章大纲
        if context.get('current_outline'):
            formatted_parts.append(f"## 本章大纲\n{context['current_outline']}")
        
        # 前文正文（核心：最近N章的原文）
        previous_chapters = context.get('previous_chapters', [])
        if previous_chapters:
            prev_text_parts = []
            for ch in previous_chapters:
                ch_num = ch.get('chapter', '?')
                content = ch.get('content', '')
                truncated_mark = " [已截断]" if ch.get('is_truncated') else ""
                prev_text_parts.append(f"### 第{ch_num}章{truncated_mark}\n{content}")
            formatted_parts.append(f"## 前文正文\n" + "\n\n".join(prev_text_parts))
        
        # 历史摘要
        summaries = context.get('summaries', [])
        if summaries:
            summary_text = "\n".join([
                f"- 第{s['chapter']}章：{s['content']}" for s in summaries
            ])
            formatted_parts.append(f"## 历史摘要\n{summary_text}")
        
        # 动态事实表
        facts = context.get('facts', [])
        if facts:
            facts_text = "\n".join([
                f"- [{f.get('importance', 'medium')}] {f.get('content', '')}"
                for f in facts
            ])
            formatted_parts.append(f"## 动态事实表\n{facts_text}")
        
        # 伏笔信息
        foreshadowing_text = context.get('foreshadowing_text', '')
        if foreshadowing_text:
            formatted_parts.append(f"## 伏笔信息\n{foreshadowing_text}")
        
        return "\n\n".join(formatted_parts)
    
    def get_token_usage_report(self, context: Dict) -> str:
        """生成Token使用报告"""
        report_lines = [
            "# Token使用报告",
            f"总窗口大小：{self.total_window:,} tokens",
            f"输出预留：{context['token_budget'].get('output_reserve', 0):,} tokens",
            "",
            "## 各部分Token使用",
            f"- 系统规则：{context.get('system_rules_tokens', 0):,} / {context['token_budget'].get('system_rules', 0):,}",
            f"- 角色卡片：{context.get('character_cards_tokens', 0):,} / {context['token_budget'].get('character_cards', 0):,}",
            f"- 世界观设定：{context.get('world_settings_tokens', 0):,} / {context['token_budget'].get('world_settings', 0):,}",
            f"- 本章大纲：{context.get('current_outline_tokens', 0):,} / {context['token_budget'].get('current_outline', 0):,}",
            f"- 前文正文：{context.get('previous_chapters_tokens', 0):,} / {context['token_budget'].get('previous_chapters', 0):,}",
            f"- 历史摘要：{context.get('summaries_tokens', 0):,} / {context['token_budget'].get('summaries', 0):,}",
            f"- 动态事实：{context.get('facts_tokens', 0):,} / {context['token_budget'].get('facts', 0):,}",
            f"- 伏笔信息：{context.get('foreshadowing_tokens', 0):,} / {context['token_budget'].get('foreshadowing', 0):,}",
            f"- 衔接提示：{context.get('transition_tokens', 0):,} / {context['token_budget'].get('transition', 0):,}",
            "",
            "## 总计",
            f"- 输入Token总计：{context.get('total_input_tokens', 0):,}",
            f"- 剩余可用：{context.get('remaining_tokens', 0):,}",
            f"- 是否超预算：{'是' if context.get('is_over_budget', False) else '否'}",
        ]
        
        # 前文章节详情
        previous_chapters = context.get('previous_chapters', [])
        if previous_chapters:
            report_lines.append("")
            report_lines.append("## 前文章节详情")
            for ch in previous_chapters:
                mark = " [已截断]" if ch.get('is_truncated') else ""
                report_lines.append(
                    f"- 第{ch['chapter']}章{mark}: "
                    f"{ch.get('truncated_tokens', 0):,} tokens "
                    f"(原始: {ch.get('original_tokens', 0):,})"
                )
        
        return "\n".join(report_lines)
