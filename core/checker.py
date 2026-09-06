"""
一致性检查模块

负责检查小说内容的一致性，包括角色、时间线、地点、伏笔等
"""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime

# 导入伏笔管理器
from .foreshadowing import ForeshadowingManager

class ConsistencyChecker:
    """一致性检查器"""
    
    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        self.consistency_config = config.get('consistency', {})
        
        # 初始化伏笔管理器
        self.foreshadowing_manager = ForeshadowingManager(config, project_name)
    
    def check_chapter(self, chapter: int, draft: str, project_data: Dict) -> Dict:
        """检查章节一致性"""
        issues = []
        
        # 1. 角色一致性检查
        character_issues = self._check_character_consistency(draft, project_data)
        issues.extend(character_issues)
        
        # 2. 时间线检查
        timeline_issues = self._check_timeline(draft, chapter, project_data)
        issues.extend(timeline_issues)
        
        # 3. 地点一致性检查
        location_issues = self._check_location_consistency(draft, project_data)
        issues.extend(location_issues)
        
        # 4. 物品状态检查
        item_issues = self._check_item_consistency(draft, project_data)
        issues.extend(item_issues)
        
        # 5. 能力体系检查
        ability_issues = self._check_ability_consistency(draft, project_data)
        issues.extend(ability_issues)
        
        # 6. 伏笔检查（新增）
        foreshadowing_issues = self._check_foreshadowing_consistency(chapter, draft, project_data)
        issues.extend(foreshadowing_issues)
        
        return {
            'chapter': chapter,
            'passed': len(issues) == 0,
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        }
    
    def _check_character_consistency(self, draft: str, project_data: Dict) -> List[str]:
        """检查角色一致性"""
        issues = []
        
        # 获取角色列表
        characters = project_data.get('characters', [])
        
        # 检查角色名字出现
        for char in characters:
            char_name = char.get('filename', '').replace('.txt', '')
            if char_name in draft:
                # 这里可以添加更详细的角色一致性检查
                # 例如：检查角色性格、能力等是否符合设定
                pass
        
        return issues
    
    def _check_timeline(self, draft: str, chapter: int, project_data: Dict) -> List[str]:
        """检查时间线"""
        issues = []
        
        # 检查时间相关词汇
        time_patterns = [
            r'第\d+天',
            r'第\d+章',
            r'\d+年后',
            r'\d+月后',
            r'\d+天后'
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, draft)
            if matches:
                # 这里可以添加时间线逻辑检查
                pass
        
        return issues
    
    def _check_location_consistency(self, draft: str, project_data: Dict) -> List[str]:
        """检查地点一致性"""
        issues = []
        
        # 获取世界观设定
        world = project_data.get('world', {})
        
        # 检查地点名称
        location_keywords = [
            '乐园', '海上', '海底', '陆地', '城市',
            '儿童戏水池', '造浪池', '彩虹滑道', '漂流河'
        ]
        
        for location in location_keywords:
            if location in draft:
                # 这里可以添加地点逻辑检查
                pass
        
        return issues
    
    def _check_item_consistency(self, draft: str, project_data: Dict) -> List[str]:
        """检查物品状态"""
        issues = []
        
        # 检查重要物品
        important_items = [
            '招牌', '甘霖瓶', '潮汐之心', '玉玺', '灯塔火种',
            '小鲲', '三姆', '蜜雪尔'
        ]
        
        for item in important_items:
            if item in draft:
                # 这里可以添加物品状态检查
                pass
        
        return issues
    
    def _check_ability_consistency(self, draft: str, project_data: Dict) -> List[str]:
        """检查能力体系一致性"""
        issues = []
        
        # 检查境界体系
        realm_patterns = [
            r'滴水境',
            r'溪流境',
            r'江河境',
            r'湖泽境',
            r'沧海境',
            r'归墟境'
        ]
        
        for pattern in realm_patterns:
            if re.search(pattern, draft):
                # 这里可以添加能力体系检查
                pass
        
        return issues
    
    def _check_foreshadowing_consistency(self, chapter: int, draft: str, 
                                        project_data: Dict) -> List[str]:
        """检查伏笔一致性"""
        issues = []
        
        # 获取项目名称
        project_name = project_data.get('config', {}).get('name', '')
        
        if not project_name:
            return issues
        
        # 检查伏笔状态
        foreshadowing_check = self.foreshadowing_manager.check_foreshadowing_for_chapter(
            project_name, chapter
        )
        
        # 检查长期未解决伏笔
        unresolved_foreshadowing = foreshadowing_check.get('unresolved_old_foreshadowing', [])
        for fs in unresolved_foreshadowing:
            issues.append(f"伏笔 {fs['id']} 已等待 {fs['chapters_pending']} 章未解决：{fs['description'][:50]}...")
        
        # 检测章节中解决的伏笔
        resolved_in_chapter = self.foreshadowing_manager.detect_resolved_foreshadowing(
            project_name, chapter, draft
        )
        
        # 标记解决的伏笔
        for fs_id in resolved_in_chapter:
            self.foreshadowing_manager.resolve_foreshadowing(project_name, fs_id, f"ch{chapter:04d}")
            issues.append(f"伏笔 {fs_id} 已在本章解决")
        
        return issues
    
    def auto_fix(self, content: str, issues: List[str]) -> str:
        """自动修复简单问题"""
        fixed_content = content
        
        # 这里可以实现简单的自动修复逻辑
        # 例如：修复明显的拼写错误、格式问题等
        
        return fixed_content
    
    def generate_report(self, chapter: int, check_result: Dict) -> str:
        """生成检查报告"""
        report_lines = [
            f"# 第{chapter}章一致性检查报告",
            f"检查时间：{check_result.get('timestamp', '未知')}",
            f"检查结果：{'通过' if check_result['passed'] else '未通过'}",
            ""
        ]
        
        if check_result['issues']:
            report_lines.append("## 发现的问题")
            for i, issue in enumerate(check_result['issues'], 1):
                report_lines.append(f"{i}. {issue}")
        else:
            report_lines.append("## 未发现一致性问题")
        
        return "\n".join(report_lines)
    
    def check_chapter_progression(self, chapter: int, project_data: Dict) -> Dict:
        """检查章节进度"""
        # 检查章节是否符合大纲进度
        outline = project_data.get('outline', [])
        
        progress_info = {
            'chapter': chapter,
            'expected_volume': (chapter - 1) // 96 + 1,
            'total_chapters': self.config['project']['chapters'],
            'completion_percentage': round(chapter / self.config['project']['chapters'] * 100, 2)
        }
        
        return progress_info
    
    def check_foreshadowing_status(self, chapter: int, project_data: Dict) -> Dict:
        """检查伏笔状态"""
        # 获取项目名称
        project_name = project_data.get('config', {}).get('name', '')
        
        if not project_name:
            return {
                'chapter': chapter,
                'foreshadowing_count': 0,
                'resolved_count': 0,
                'pending_count': 0,
                'issues': []
            }
        
        # 检查伏笔状态
        foreshadowing_check = self.foreshadowing_manager.check_foreshadowing_for_chapter(
            project_name, chapter
        )
        
        # 获取活跃和已解决伏笔
        active_foreshadowing = self.foreshadowing_manager.get_active_foreshadowing(project_name)
        resolved_foreshadowing = self.foreshadowing_manager.get_resolved_foreshadowing(project_name)
        
        return {
            'chapter': chapter,
            'foreshadowing_count': len(active_foreshadowing) + len(resolved_foreshadowing),
            'resolved_count': len(resolved_foreshadowing),
            'pending_count': len(active_foreshadowing),
            'unresolved_old': foreshadowing_check.get('unresolved_old_foreshadowing', []),
            'introduced_this_chapter': foreshadowing_check.get('introduced_this_chapter', 0),
            'resolved_this_chapter': foreshadowing_check.get('actually_resolved', 0)
        }