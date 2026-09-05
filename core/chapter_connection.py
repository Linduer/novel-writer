"""
章前章尾衔接模块

负责管理章节之间的衔接，确保章前和章尾的连贯性
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class ChapterEnding:
    """章节结尾数据"""
    chapter: int
    content: str
    hook_type: str  # 悬念类型：question/cliffhanger/emotional/revelation
    hook_description: str
    key_elements: List[str]  # 关键元素
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

@dataclass
class ChapterBeginning:
    """章节开头数据"""
    chapter: int
    content: str
    connection_type: str  # 衔接类型：direct/time_skip/scene_change/character_focus
    connection_description: str
    references: List[str]  # 引用前文的元素
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

class ChapterConnectionManager:
    """章节衔接管理器"""
    
    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
    
    def load_chapter_data(self, project_name: str, chapter: int) -> Dict:
        """加载章节数据"""
        project_dir = self.base_path
        data_file = project_dir / 'memory' / 'chapter_connections.json'
        
        if not data_file.exists():
            return {}
        
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        chapter_key = f"chapter_{chapter:03d}"
        return data.get(chapter_key, {})
    
    def save_chapter_data(self, project_name: str, chapter: int, data: Dict):
        """保存章节数据"""
        project_dir = self.base_path
        data_file = project_dir / 'memory' / 'chapter_connections.json'
        
        # 读取现有数据
        all_data = {}
        if data_file.exists():
            with open(data_file, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        
        # 更新指定章节的数据
        chapter_key = f"chapter_{chapter:03d}"
        all_data[chapter_key] = data
        all_data['last_updated'] = datetime.now().isoformat()
        
        data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    def analyze_chapter_ending(self, project_name: str, chapter: int, 
                              content: str) -> ChapterEnding:
        """分析章节结尾"""
        # 提取最后几段作为结尾分析
        paragraphs = content.split('\n')
        ending_paragraphs = paragraphs[-3:] if len(paragraphs) >= 3 else paragraphs
        ending_text = '\n'.join(ending_paragraphs)
        
        # 分析结尾类型
        hook_type, hook_description = self._analyze_hook_type(ending_text)
        
        # 提取关键元素
        key_elements = self._extract_key_elements(ending_text)
        
        ending = ChapterEnding(
            chapter=chapter,
            content=ending_text,
            hook_type=hook_type,
            hook_description=hook_description,
            key_elements=key_elements
        )
        
        # 保存数据
        data = self.load_chapter_data(project_name, chapter)
        data['ending'] = asdict(ending)
        self.save_chapter_data(project_name, chapter, data)
        
        return ending
    
    def analyze_chapter_beginning(self, project_name: str, chapter: int, 
                                 content: str) -> ChapterBeginning:
        """分析章节开头"""
        # 提取前几段作为开头分析
        paragraphs = content.split('\n')
        beginning_paragraphs = paragraphs[:3] if len(paragraphs) >= 3 else paragraphs
        beginning_text = '\n'.join(beginning_paragraphs)
        
        # 分析衔接类型
        connection_type, connection_description = self._analyze_connection_type(beginning_text)
        
        # 提取引用元素
        references = self._extract_references(beginning_text)
        
        beginning = ChapterBeginning(
            chapter=chapter,
            content=beginning_text,
            connection_type=connection_type,
            connection_description=connection_description,
            references=references
        )
        
        # 保存数据
        data = self.load_chapter_data(project_name, chapter)
        data['beginning'] = asdict(beginning)
        self.save_chapter_data(project_name, chapter, data)
        
        return beginning
    
    def _analyze_hook_type(self, text: str) -> Tuple[str, str]:
        """分析钩子类型"""
        text_lower = text.lower()
        
        # 悬念型钩子
        question_patterns = [r'为什么', r'怎么', r'什么', r'谁', r'哪里', r'什么时候']
        for pattern in question_patterns:
            if re.search(pattern, text_lower):
                return 'question', '通过提问制造悬念'
        
        # 危机型钩子
        cliffhanger_patterns = [r'突然', r'就在这时', r'然而', r'但是', r'却']
        for pattern in cliffhanger_patterns:
            if re.search(pattern, text_lower):
                return 'cliffhanger', '通过危机或转折制造悬念'
        
        # 情感型钩子
        emotional_patterns = [r'心', r'泪', r'笑', r'怒', r'惊']
        for pattern in emotional_patterns:
            if re.search(pattern, text_lower):
                return 'emotional', '通过情感渲染制造悬念'
        
        # 揭示型钩子
        revelation_patterns = [r'原来', r'真相', r'终于', r'秘密']
        for pattern in revelation_patterns:
            if re.search(pattern, text_lower):
                return 'revelation', '通过揭示信息制造悬念'
        
        return 'unknown', '未识别的钩子类型'
    
    def _analyze_connection_type(self, text: str) -> Tuple[str, str]:
        """分析衔接类型"""
        text_lower = text.lower()
        
        # 直接延续
        direct_patterns = [r'接着', r'继续', r'然后', r'于是']
        for pattern in direct_patterns:
            if re.search(pattern, text_lower):
                return 'direct', '直接延续前章情节'
        
        # 时间跳跃
        time_skip_patterns = [r'第二天', r'一周后', r'一个月后', r'几天后']
        for pattern in time_skip_patterns:
            if re.search(pattern, text_lower):
                return 'time_skip', '时间跳跃衔接'
        
        # 场景转换
        scene_change_patterns = [r'与此同时', r'另一边', r'在另一个地方']
        for pattern in scene_change_patterns:
            if re.search(pattern, text_lower):
                return 'scene_change', '场景转换衔接'
        
        # 角色聚焦
        character_focus_patterns = [r'他', r'她', r'它', r'他们']
        for pattern in character_focus_patterns:
            if re.search(pattern, text_lower):
                return 'character_focus', '角色聚焦衔接'
        
        return 'unknown', '未识别的衔接类型'
    
    def _extract_key_elements(self, text: str) -> List[str]:
        """提取关键元素"""
        elements = []
        
        # 提取人名（简单实现）
        name_patterns = [r'沈浮', r'三姆', r'蜜雪尔', r'小鲲', r'老聂']
        for pattern in name_patterns:
            if pattern in text:
                elements.append(pattern)
        
        # 提取地点
        location_patterns = [r'乐园', r'造浪池', r'儿童戏水池', r'漂流河']
        for pattern in location_patterns:
            if pattern in text:
                elements.append(pattern)
        
        # 提取物品
        item_patterns = [r'招牌', r'甘霖瓶', r'潮汐之心', r'玉玺']
        for pattern in item_patterns:
            if pattern in text:
                elements.append(pattern)
        
        return elements
    
    def _extract_references(self, text: str) -> List[str]:
        """提取引用前文的元素"""
        references = []
        
        # 检查是否引用前文
        reference_patterns = [
            r'上次', r'之前', r'刚才', r'之前',
            r'记得', r'想起', r'回忆'
        ]
        
        for pattern in reference_patterns:
            if re.search(pattern, text):
                references.append(f"引用了前文内容（{pattern}）")
        
        return references
    
    def check_chapter_connection(self, project_name: str, chapter: int) -> Dict:
        """检查章节衔接质量"""
        if chapter <= 1:
            return {
                'chapter': chapter,
                'is_first_chapter': True,
                'connection_quality': 'good',
                'issues': []
            }
        
        # 加载前一章数据
        prev_data = self.load_chapter_data(project_name, chapter - 1)
        curr_data = self.load_chapter_data(project_name, chapter)
        
        issues = []
        
        # 检查前章结尾
        prev_ending = prev_data.get('ending', {})
        if not prev_ending:
            issues.append(f"第{chapter-1}章缺少结尾分析数据")
        
        # 检查本章开头
        curr_beginning = curr_data.get('beginning', {})
        if not curr_beginning:
            issues.append(f"第{chapter}章缺少开头分析数据")
        
        # 检查衔接类型
        if prev_ending and curr_beginning:
            hook_type = prev_ending.get('hook_type', '')
            connection_type = curr_beginning.get('connection_type', '')
            
            # 检查是否自然衔接
            if hook_type == 'cliffhanger' and connection_type == 'time_skip':
                issues.append("危机型钩子后使用时间跳跃可能不够自然")
            
            # 检查关键元素是否延续
            prev_elements = set(prev_ending.get('key_elements', []))
            curr_references = set(curr_beginning.get('references', []))
            
            if prev_elements and not curr_references:
                issues.append("前章关键元素在本章开头未被引用")
        
        # 评估衔接质量
        if len(issues) == 0:
            quality = 'good'
        elif len(issues) <= 2:
            quality = 'fair'
        else:
            quality = 'poor'
        
        return {
            'chapter': chapter,
            'is_first_chapter': False,
            'connection_quality': quality,
            'issues': issues,
            'prev_ending_hook': prev_ending.get('hook_type', 'unknown'),
            'curr_beginning_connection': curr_beginning.get('connection_type', 'unknown')
        }
    
    def generate_chapter_transition_prompt(self, project_name: str, chapter: int) -> str:
        """生成章节过渡提示词"""
        if chapter <= 1:
            return "这是第一章，没有前文需要衔接。"
        
        # 加载前一章数据
        prev_data = self.load_chapter_data(project_name, chapter - 1)
        prev_ending = prev_data.get('ending', {})
        
        if not prev_ending:
            return f"第{chapter-1}章缺少结尾数据，请根据大纲自由发挥。"
        
        # 生成过渡提示
        hook_type = prev_ending.get('hook_type', 'unknown')
        hook_description = prev_ending.get('hook_description', '')
        key_elements = prev_ending.get('key_elements', [])
        
        prompt_parts = [
            f"## 第{chapter-1}章结尾信息",
            f"钩子类型：{hook_type}",
            f"钩子描述：{hook_description}",
            f"关键元素：{', '.join(key_elements) if key_elements else '无'}",
            "",
            "## 衔接要求",
        ]
        
        # 根据钩子类型提供具体的衔接建议
        if hook_type == 'question':
            prompt_parts.append("前章以问题结尾，本章开头应该：")
            prompt_parts.append("1. 直接回应或暗示问题的答案")
            prompt_parts.append("2. 或者通过新情节自然引出答案")
        elif hook_type == 'cliffhanger':
            prompt_parts.append("前章以危机/转折结尾，本章开头应该：")
            prompt_parts.append("1. 直接延续危机场景")
            prompt_parts.append("2. 或者展示危机的后果")
        elif hook_type == 'emotional':
            prompt_parts.append("前章以情感渲染结尾，本章开头应该：")
            prompt_parts.append("1. 延续情感氛围")
            prompt_parts.append("2. 或者通过对比转换情感")
        elif hook_type == 'revelation':
            prompt_parts.append("前章以揭示信息结尾，本章开头应该：")
            prompt_parts.append("1. 展示信息的影响")
            prompt_parts.append("2. 或者引入新的悬念")
        
        if key_elements:
            prompt_parts.append(f"\n前章关键元素：{', '.join(key_elements)}")
            prompt_parts.append("本章开头应该适当提及这些元素，保持连贯性。")
        
        return "\n".join(prompt_parts)
    
    def get_connection_statistics(self, project_name: str, start_chapter: int, 
                                 end_chapter: int) -> Dict:
        """获取章节衔接统计"""
        stats = {
            'total_chapters': end_chapter - start_chapter + 1,
            'hook_types': {},
            'connection_types': {},
            'quality_distribution': {'good': 0, 'fair': 0, 'poor': 0}
        }
        
        for chapter in range(start_chapter, end_chapter + 1):
            connection_check = self.check_chapter_connection(project_name, chapter)
            
            # 统计钩子类型
            hook_type = connection_check.get('prev_ending_hook', 'unknown')
            stats['hook_types'][hook_type] = stats['hook_types'].get(hook_type, 0) + 1
            
            # 统计衔接类型
            connection_type = connection_check.get('curr_beginning_connection', 'unknown')
            stats['connection_types'][connection_type] = stats['connection_types'].get(connection_type, 0) + 1
            
            # 统计质量分布
            quality = connection_check.get('connection_quality', 'unknown')
            if quality in stats['quality_distribution']:
                stats['quality_distribution'][quality] += 1
        
        return stats
    
    def generate_connection_report(self, project_name: str, start_chapter: int, 
                                  end_chapter: int) -> str:
        """生成章节衔接报告"""
        stats = self.get_connection_statistics(project_name, start_chapter, end_chapter)
        
        report_lines = [
            f"# 章节衔接报告（第{start_chapter}-{end_chapter}章）",
            f"生成时间：{datetime.now().isoformat()}",
            "",
            "## 总体统计",
            f"- 总章节数：{stats['total_chapters']}",
            ""
        ]
        
        # 钩子类型分布
        report_lines.append("### 钩子类型分布")
        for hook_type, count in stats['hook_types'].items():
            percentage = round(count / stats['total_chapters'] * 100, 1)
            report_lines.append(f"- {hook_type}: {count}章 ({percentage}%)")
        report_lines.append("")
        
        # 衔接类型分布
        report_lines.append("### 衔接类型分布")
        for connection_type, count in stats['connection_types'].items():
            percentage = round(count / stats['total_chapters'] * 100, 1)
            report_lines.append(f"- {connection_type}: {count}章 ({percentage}%)")
        report_lines.append("")
        
        # 质量分布
        report_lines.append("### 衔接质量分布")
        for quality, count in stats['quality_distribution'].items():
            percentage = round(count / stats['total_chapters'] * 100, 1)
            report_lines.append(f"- {quality}: {count}章 ({percentage}%)")
        report_lines.append("")
        
        # 问题章节
        report_lines.append("## 问题章节")
        problem_chapters = []
        for chapter in range(start_chapter, end_chapter + 1):
            connection_check = self.check_chapter_connection(project_name, chapter)
            if connection_check.get('connection_quality') == 'poor':
                problem_chapters.append(chapter)
        
        if problem_chapters:
            for chapter in problem_chapters:
                connection_check = self.check_chapter_connection(project_name, chapter)
                report_lines.append(f"### 第{chapter}章")
                for issue in connection_check.get('issues', []):
                    report_lines.append(f"- {issue}")
        else:
            report_lines.append("未发现衔接质量较差的章节。")
        
        return "\n".join(report_lines)
