"""
上下文引擎模块

负责构建写作上下文，管理Token预算，进行智能检索
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# 导入新模块
from .foreshadowing import ForeshadowingManager
from .chapter_connection import ChapterConnectionManager

class ContextEngine:
    """上下文引擎"""
    
    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        self.budget_config = config['context']['budget']
        self.retrieval_config = config['context']['retrieval']
        
        # 初始化伏笔管理器和章节衔接管理器
        self.foreshadowing_manager = ForeshadowingManager(config, project_name)
        self.connection_manager = ChapterConnectionManager(config, project_name)
    
    def build_writing_context(self, project_data: Dict, chapter: int, 
                            volume: Optional[int] = None) -> Dict:
        """构建写作上下文"""
        # 计算当前卷
        if volume is None:
            volume = (chapter - 1) // 96 + 1  # 每卷96章
        
        # 获取项目名称
        project_name = project_data.get('config', {}).get('name', '')
        
        # 获取伏笔信息
        active_foreshadowing = self.foreshadowing_manager.get_active_foreshadowing(project_name)
        foreshadowing_check = self.foreshadowing_manager.check_foreshadowing_for_chapter(project_name, chapter)
        
        # 获取章节衔接信息
        connection_check = self.connection_manager.check_chapter_connection(project_name, chapter)
        transition_prompt = self.connection_manager.generate_chapter_transition_prompt(project_name, chapter)
        
        # 初始化上下文
        context = {
            'chapter': chapter,
            'volume': volume,
            'system_rules': self._load_system_rules(),
            'character_cards': self._load_relevant_characters(project_data, chapter),
            'world_settings': self._load_relevant_world(project_data, chapter),
            'facts': self._load_relevant_facts(project_data, chapter),
            'summaries': self._load_relevant_summaries(project_data, chapter),
            'current_outline': self._load_chapter_outline(project_data, chapter, volume),
            'previous_chapter': self._load_previous_chapter_summary(project_data, chapter),
            'next_chapter_hint': self._load_next_chapter_hint(project_data, chapter),
            # 新增：伏笔和衔接信息
            'active_foreshadowing': [fs.description for fs in active_foreshadowing[:10]],  # 限制数量
            'foreshadowing_check': foreshadowing_check,
            'chapter_connection': connection_check,
            'transition_prompt': transition_prompt
        }
        
        # 计算Token预算
        context['token_budget'] = self._calculate_token_budget(context)
        
        return context
    
    def _load_system_rules(self) -> str:
        """加载系统规则"""
        rules = """
# 写作系统规则

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
4. 不写'这一刻，他终于明白了'
"""
        return rules
    
    def _load_relevant_characters(self, project_data: Dict, chapter: int) -> List[Dict]:
        """加载相关角色"""
        characters = project_data.get('characters', [])
        
        # 这里可以实现更智能的角色选择逻辑
        # 目前简化为加载所有角色，但限制数量
        
        relevant_chars = []
        for char in characters[:10]:  # 限制最多10个角色
            relevant_chars.append({
                'name': char.get('filename', '').replace('.txt', ''),
                'content': char.get('content', '')[:500]  # 限制内容长度
            })
        
        return relevant_chars
    
    def _load_relevant_world(self, project_data: Dict, chapter: int) -> Dict:
        """加载相关世界观"""
        world = project_data.get('world', {})
        
        relevant_world = {}
        for key, content in world.items():
            relevant_world[key] = content[:300]  # 限制内容长度
        
        return relevant_world
    
    def _load_relevant_facts(self, project_data: Dict, chapter: int) -> List[Dict]:
        """加载相关事实"""
        # 从项目数据中加载事实
        # 这里需要从记忆系统获取
        
        # 简化实现：返回空列表
        return []
    
    def _load_relevant_summaries(self, project_data: Dict, chapter: int) -> List[Dict]:
        """加载相关摘要"""
        # 从项目数据中加载摘要
        # 这里需要从记忆系统获取
        
        # 简化实现：返回空列表
        return []
    
    def _load_chapter_outline(self, project_data: Dict, chapter: int, volume: int) -> str:
        """加载章节大纲"""
        outline = project_data.get('outline', [])
        
        # 查找相关大纲内容
        for outline_item in outline:
            content = outline_item.get('content', '')
            if f"ch{chapter:03d}" in content or f"第{chapter}章" in content:
                return content[:1000]  # 限制长度
        
        # 如果没有找到具体章节大纲，返回卷大纲
        for outline_item in outline:
            content = outline_item.get('content', '')
            if f"卷{volume}" in content:
                return content[:1000]
        
        return ""
    
    def _load_previous_chapter_summary(self, project_data: Dict, chapter: int) -> str:
        """加载前一章摘要"""
        if chapter <= 1:
            return "这是第一章，没有前文。"
        
        # 这里需要从记忆系统获取前一章摘要
        # 简化实现：返回空字符串
        return ""
    
    def _load_next_chapter_hint(self, project_data: Dict, chapter: int) -> str:
        """加载下一章提示"""
        # 这里可以加载下一章的大纲或提示
        # 简化实现：返回空字符串
        return ""
    
    def _calculate_token_budget(self, context: Dict) -> Dict:
        """计算Token预算"""
        # 假设总预算为128K Token
        total_budget = 128000
        
        budget_allocation = {
            'system_rules': int(total_budget * self.budget_config['system_rules'] / 100),
            'character_cards': int(total_budget * self.budget_config['character_cards'] / 100),
            'world_settings': int(total_budget * self.budget_config['world_settings'] / 100),
            'facts': int(total_budget * self.budget_config['facts'] / 100),
            'summaries': int(total_budget * self.budget_config['summaries'] / 100),
            'current_draft': int(total_budget * self.budget_config['current_draft'] / 100),
            'output_reserve': int(total_budget * self.budget_config['output_reserve'] / 100)
        }
        
        return budget_allocation
    
    def optimize_context(self, context: Dict, max_tokens: int) -> Dict:
        """优化上下文以适应Token限制"""
        # 这里可以实现上下文优化逻辑
        # 例如：截断过长的内容、调整分配比例等
        
        optimized = context.copy()
        
        # 简单优化：截断过长的内容
        for key in ['character_cards', 'world_settings']:
            if key in optimized:
                truncated = []
                for item in optimized[key]:
                    if isinstance(item, dict):
                        truncated_item = item.copy()
                        truncated_item['content'] = truncated_item.get('content', '')[:200]
                        truncated.append(truncated_item)
                    else:
                        truncated.append(str(item)[:200])
                optimized[key] = truncated
        
        return optimized
    
    def format_context_for_llm(self, context: Dict) -> str:
        """格式化上下文为LLM输入"""
        formatted_parts = []
        
        # 系统规则
        if context.get('system_rules'):
            formatted_parts.append(f"## 系统规则\n{context['system_rules']}")
        
        # 角色卡片
        if context.get('character_cards'):
            chars_text = "\n".join([
                f"### {char.get('name', '未命名')}\n{char.get('content', '')}"
                for char in context['character_cards']
            ])
            formatted_parts.append(f"## 角色档案\n{chars_text}")
        
        # 世界观设定
        if context.get('world_settings'):
            world_text = "\n".join([
                f"### {key}\n{value}"
                for key, value in context['world_settings'].items()
            ])
            formatted_parts.append(f"## 世界观设定\n{world_text}")
        
        # 章节衔接提示（重要：章前衔接）
        if context.get('transition_prompt'):
            formatted_parts.append(f"## 章节衔接提示\n{context['transition_prompt']}")
        
        # 章节大纲
        if context.get('current_outline'):
            formatted_parts.append(f"## 本章大纲\n{context['current_outline']}")
        
        # 前文摘要
        if context.get('previous_chapter'):
            formatted_parts.append(f"## 前文摘要\n{context['previous_chapter']}")
        
        # 下一章提示
        if context.get('next_chapter_hint'):
            formatted_parts.append(f"## 下一章提示\n{context['next_chapter_hint']}")
        
        # 伏笔信息（重要：伏笔管理）
        if context.get('active_foreshadowing'):
            foreshadowing_text = "\n".join([
                f"- {fs}" for fs in context['active_foreshadowing']
            ])
            formatted_parts.append(f"## 活跃伏笔\n{foreshadowing_text}")
        
        # 伏笔检查信息
        foreshadowing_check = context.get('foreshadowing_check', {})
        if foreshadowing_check.get('unresolved_old_foreshadowing'):
            unresolved_text = "\n".join([
                f"- {fs['id']}: {fs['description'][:50]}... (等待{fs['chapters_pending']}章)"
                for fs in foreshadowing_check['unresolved_old_foreshadowing']
            ])
            formatted_parts.append(f"## 长期未解决伏笔（需要关注）\n{unresolved_text}")
        
        # 章节衔接检查
        chapter_connection = context.get('chapter_connection', {})
        if chapter_connection.get('issues'):
            issues_text = "\n".join([f"- {issue}" for issue in chapter_connection['issues']])
            formatted_parts.append(f"## 章节衔接问题\n{issues_text}")
        
        return "\n\n".join(formatted_parts)