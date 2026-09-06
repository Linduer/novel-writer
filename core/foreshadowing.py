"""
伏笔管理模块

负责管理小说的伏笔系统，包括伏笔的添加、检查、删除和状态追踪
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

class ForeshadowingStatus(Enum):
    """伏笔状态枚举"""
    ACTIVE = "active"      # 活跃状态
    RESOLVED = "resolved"  # 已解决

@dataclass
class Foreshadowing:
    """伏笔数据类"""
    id: str
    introduced_in: str  # 章节格式：ch001 或 ch001-003
    description: str
    related_characters: List[str]
    resolved_in: Optional[str] = None  # 解决章节
    status: ForeshadowingStatus = ForeshadowingStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

class ForeshadowingManager:
    """伏笔管理器"""
    
    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
    
    def load_foreshadowing(self, project_name: str) -> Dict[str, Foreshadowing]:
        """加载项目的所有伏笔"""
        project_dir = self.base_path
        foreshadowing_json = project_dir / 'world' / 'foreshadowing.json'
        foreshadowing_txt = project_dir / 'world' / '伏笔.txt'
        
        foreshadowing_map = {}
        
        if foreshadowing_json.exists():
            with open(foreshadowing_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data.get('active', []):
                fs = self._parse_foreshadowing_item(item, ForeshadowingStatus.ACTIVE)
                if fs:
                    foreshadowing_map[fs.id] = fs
            
            for item in data.get('resolved', []):
                fs = self._parse_foreshadowing_item(item, ForeshadowingStatus.RESOLVED)
                if fs:
                    foreshadowing_map[fs.id] = fs
        
        elif foreshadowing_txt.exists():
            foreshadowing_map = self._load_from_txt(foreshadowing_txt)
            self.save_foreshadowing(project_name, foreshadowing_map)
        
        return foreshadowing_map
    
    def _load_from_txt(self, txt_path: Path) -> Dict[str, Foreshadowing]:
        """从旧格式txt文件加载伏笔"""
        import yaml
        
        foreshadowing_map = {}
        
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            data = yaml.safe_load(content)
            if not data:
                return foreshadowing_map
            
            resolved_list = data.get('resolved', [])
            if not isinstance(resolved_list, list):
                resolved_list = []
            
            for item in resolved_list:
                if not isinstance(item, dict):
                    continue
                
                fs_id = item.get('id', '')
                if not fs_id:
                    continue
                
                fs = Foreshadowing(
                    id=fs_id,
                    introduced_in=item.get('introduced_in', ''),
                    description=item.get('description', ''),
                    related_characters=item.get('related_characters', []) or [],
                    resolved_in=item.get('resolved_in', ''),
                    status=ForeshadowingStatus.RESOLVED
                )
                foreshadowing_map[fs_id] = fs
            
            active_list = data.get('active', [])
            if isinstance(active_list, list):
                for item in active_list:
                    if not isinstance(item, dict):
                        continue
                    
                    fs_id = item.get('id', '')
                    if not fs_id:
                        continue
                    
                    fs = Foreshadowing(
                        id=fs_id,
                        introduced_in=item.get('introduced_in', ''),
                        description=item.get('description', ''),
                        related_characters=item.get('related_characters', []) or [],
                        resolved_in=item.get('resolved_in', ''),
                        status=ForeshadowingStatus.ACTIVE
                    )
                    foreshadowing_map[fs_id] = fs
            
        except Exception as e:
            print(f"从txt文件加载伏笔失败：{e}")
            import traceback
            traceback.print_exc()
        
        return foreshadowing_map
    
    def _parse_foreshadowing_item(self, item: Dict, status: ForeshadowingStatus) -> Optional[Foreshadowing]:
        """解析伏笔条目"""
        try:
            return Foreshadowing(
                id=item.get('id', ''),
                introduced_in=item.get('introduced_in', ''),
                description=item.get('description', ''),
                related_characters=item.get('related_characters', []),
                resolved_in=item.get('resolved_in'),
                status=status,
                created_at=item.get('created_at', ''),
                updated_at=item.get('updated_at', '')
            )
        except Exception as e:
            print(f"解析伏笔条目失败：{e}")
            return None
    
    def save_foreshadowing(self, project_name: str, foreshadowing_map: Dict[str, Foreshadowing]):
        """保存伏笔数据"""
        project_dir = self.base_path
        foreshadowing_file = project_dir / 'world' / 'foreshadowing.json'
        
        # 分离活跃和已解决的伏笔
        active_list = []
        resolved_list = []
        
        for fs in foreshadowing_map.values():
            fs_dict = asdict(fs)
            fs_dict['status'] = fs.status.value  # 转换枚举为字符串
            
            if fs.status == ForeshadowingStatus.ACTIVE:
                active_list.append(fs_dict)
            else:
                resolved_list.append(fs_dict)
        
        data = {
            'active': active_list,
            'resolved': resolved_list,
            'last_updated': datetime.now().isoformat()
        }
        
        foreshadowing_file.parent.mkdir(parents=True, exist_ok=True)
        with open(foreshadowing_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_foreshadowing(self, project_name: str, foreshadowing: Foreshadowing) -> bool:
        """添加新伏笔"""
        try:
            foreshadowing_map = self.load_foreshadowing(project_name)
            foreshadowing_map[foreshadowing.id] = foreshadowing
            self.save_foreshadowing(project_name, foreshadowing_map)
            return True
        except Exception as e:
            print(f"添加伏笔失败：{e}")
            return False
    
    def resolve_foreshadowing(self, project_name: str, foreshadowing_id: str, 
                             resolved_in: str) -> bool:
        """解决伏笔（标记为已解决）"""
        try:
            foreshadowing_map = self.load_foreshadowing(project_name)
            
            if foreshadowing_id in foreshadowing_map:
                fs = foreshadowing_map[foreshadowing_id]
                fs.status = ForeshadowingStatus.RESOLVED
                fs.resolved_in = resolved_in
                fs.updated_at = datetime.now().isoformat()
                
                self.save_foreshadowing(project_name, foreshadowing_map)
                return True
            else:
                print(f"伏笔 {foreshadowing_id} 不存在")
                return False
        except Exception as e:
            print(f"解决伏笔失败：{e}")
            return False
    
    def delete_foreshadowing(self, project_name: str, foreshadowing_id: str) -> bool:
        """删除伏笔"""
        try:
            foreshadowing_map = self.load_foreshadowing(project_name)
            
            if foreshadowing_id in foreshadowing_map:
                del foreshadowing_map[foreshadowing_id]
                self.save_foreshadowing(project_name, foreshadowing_map)
                return True
            else:
                print(f"伏笔 {foreshadowing_id} 不存在")
                return False
        except Exception as e:
            print(f"删除伏笔失败：{e}")
            return False
    
    def get_active_foreshadowing(self, project_name: str) -> List[Foreshadowing]:
        """获取所有活跃伏笔"""
        foreshadowing_map = self.load_foreshadowing(project_name)
        return [fs for fs in foreshadowing_map.values() 
                if fs.status == ForeshadowingStatus.ACTIVE]
    
    def find_foreshadowing_by_hint(self, project_name: str, hint: str) -> Optional[Foreshadowing]:
        """根据描述模糊匹配活跃伏笔（优先匹配最长公共子串）"""
        active = self.get_active_foreshadowing(project_name)
        if not active or not hint:
            return None
        best_fs = None
        best_len = 0
        for fs in active:
            desc = fs.description
            # 双向检查子串
            if hint[:20] in desc or desc[:20] in hint:
                overlap = min(len(hint), len(desc), 20)
                if overlap > best_len:
                    best_len = overlap
                    best_fs = fs
        return best_fs
    
    def get_resolved_foreshadowing(self, project_name: str) -> List[Foreshadowing]:
        """获取所有已解决伏笔"""
        foreshadowing_map = self.load_foreshadowing(project_name)
        return [fs for fs in foreshadowing_map.values() 
                if fs.status == ForeshadowingStatus.RESOLVED]
    
    def get_foreshadowing_by_chapter(self, project_name: str, chapter: int) -> List[Foreshadowing]:
        """获取指定章节相关的伏笔"""
        foreshadowing_map = self.load_foreshadowing(project_name)
        chapter_str = f"ch{chapter:03d}"
        
        related_foreshadowing = []
        for fs in foreshadowing_map.values():
            # 检查引入章节
            if self._chapter_in_range(chapter, fs.introduced_in):
                related_foreshadowing.append(fs)
            # 检查解决章节
            elif fs.resolved_in and self._chapter_in_range(chapter, fs.resolved_in):
                related_foreshadowing.append(fs)
        
        return related_foreshadowing
    
    def _chapter_in_range(self, chapter: int, chapter_range: str) -> bool:
        """检查章节是否在指定范围内"""
        if not chapter_range:
            return False
        
        # 处理单个章节：ch001
        if re.match(r'^ch\d{3}$', chapter_range):
            target_chapter = int(chapter_range[2:])
            return chapter == target_chapter
        
        # 处理章节范围：ch001-003 或 ch001-010
        if re.match(r'^ch\d{3}-\d{3}$', chapter_range):
            parts = chapter_range.split('-')
            start = int(parts[0][2:])
            end = int(parts[1][2:])
            return start <= chapter <= end
        
        # 处理多个范围：ch001-003；ch050-055
        if '；' in chapter_range:
            ranges = chapter_range.split('；')
            for r in ranges:
                if self._chapter_in_range(chapter, r.strip()):
                    return True
            return False
        
        # 处理卷描述：卷一闲笔
        if '卷' in chapter_range:
            # 这里可以添加卷的解析逻辑
            return False
        
        return False
    
    def check_foreshadowing_for_chapter(self, project_name: str, chapter: int) -> Dict:
        """检查指定章节的伏笔状态"""
        active_foreshadowing = self.get_active_foreshadowing(project_name)
        chapter_foreshadowing = self.get_foreshadowing_by_chapter(project_name, chapter)
        
        # 统计信息
        stats = {
            'chapter': chapter,
            'total_active': len(active_foreshadowing),
            'introduced_this_chapter': 0,
            'should_resolve_this_chapter': 0,
            'actually_resolved': 0,
            'unresolved_old_foreshadowing': []
        }
        
        for fs in chapter_foreshadowing:
            if self._chapter_in_range(chapter, fs.introduced_in):
                stats['introduced_this_chapter'] += 1
            
            if fs.status == ForeshadowingStatus.ACTIVE:
                # 检查是否应该在本章或之前解决
                if fs.introduced_in:
                    introduced_chapter = self._extract_first_chapter(fs.introduced_in)
                    if introduced_chapter and (chapter - introduced_chapter) > 50:  # 超过50章未解决
                        stats['unresolved_old_foreshadowing'].append({
                            'id': fs.id,
                            'description': fs.description[:100],
                            'introduced_in': fs.introduced_in,
                            'chapters_pending': chapter - introduced_chapter
                        })
            
            if fs.status == ForeshadowingStatus.RESOLVED and self._chapter_in_range(chapter, fs.resolved_in):
                stats['actually_resolved'] += 1
        
        return stats
    
    def _extract_first_chapter(self, chapter_range: str) -> Optional[int]:
        """从章节范围中提取第一个章节号"""
        match = re.search(r'ch(\d{3})', chapter_range)
        if match:
            return int(match.group(1))
        return None
    
    def detect_resolved_foreshadowing(self, project_name: str, chapter: int, 
                                     chapter_content: str) -> List[str]:
        """检测章节中解决的伏笔"""
        active_foreshadowing = self.get_active_foreshadowing(project_name)
        resolved_ids = []
        
        for fs in active_foreshadowing:
            # 检查伏笔描述中的关键词是否出现在章节中
            if self._check_foreshadowing_resolved(fs, chapter_content):
                resolved_ids.append(fs.id)
        
        return resolved_ids
    
    def _check_foreshadowing_resolved(self, foreshadowing: Foreshadowing, 
                                     chapter_content: str) -> bool:
        """检查伏笔是否在章节中被解决"""
        description = foreshadowing.description.lower()
        content = chapter_content.lower()
        
        # 提取描述中的关键词
        keywords = self._extract_keywords(description)
        
        # 检查是否有解决相关的词汇
        resolution_keywords = ['解决', '揭示', '真相', '原来', '终于', '答案', '解开']
        
        for resolution_keyword in resolution_keywords:
            if resolution_keyword in content:
                # 检查关键词是否在附近出现
                for keyword in keywords:
                    if keyword in content:
                        return True
        
        return False
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 简单的关键词提取：提取名词和动词
        keywords = []
        
        # 移除标点符号
        text = re.sub(r'[^\w\s]', '', text)
        
        # 分词（简单实现）
        words = text.split()
        
        # 过滤停用词和短词
        stop_words = {'的', '了', '是', '在', '和', '与', '或', '但', '却', '这', '那'}
        for word in words:
            if len(word) >= 2 and word not in stop_words:
                keywords.append(word)
        
        return keywords[:10]  # 返回前10个关键词
    
    def get_foreshadowing_summary(self, project_name: str) -> Dict:
        """获取伏笔统计摘要"""
        foreshadowing_map = self.load_foreshadowing(project_name)
        
        active_count = sum(1 for fs in foreshadowing_map.values() 
                          if fs.status == ForeshadowingStatus.ACTIVE)
        resolved_count = sum(1 for fs in foreshadowing_map.values() 
                            if fs.status == ForeshadowingStatus.RESOLVED)
        
        # 按引入章节分组
        by_chapter = {}
        for fs in foreshadowing_map.values():
            chapter = fs.introduced_in
            if chapter not in by_chapter:
                by_chapter[chapter] = {'active': 0, 'resolved': 0}
            
            if fs.status == ForeshadowingStatus.ACTIVE:
                by_chapter[chapter]['active'] += 1
            else:
                by_chapter[chapter]['resolved'] += 1
        
        return {
            'total': len(foreshadowing_map),
            'active': active_count,
            'resolved': resolved_count,
            'by_chapter': by_chapter
        }
    
    def generate_foreshadowing_report(self, project_name: str, chapter: int) -> str:
        """生成伏笔报告"""
        stats = self.check_foreshadowing_for_chapter(project_name, chapter)
        active_foreshadowing = self.get_active_foreshadowing(project_name)
        
        report_lines = [
            f"# 第{chapter}章伏笔报告",
            f"检查时间：{datetime.now().isoformat()}",
            "",
            "## 统计信息",
            f"- 活跃伏笔总数：{stats['total_active']}",
            f"- 本章引入伏笔：{stats['introduced_this_chapter']}",
            f"- 本章解决伏笔：{stats['actually_resolved']}",
            ""
        ]
        
        if stats['unresolved_old_foreshadowing']:
            report_lines.append("## 长期未解决伏笔")
            for fs in stats['unresolved_old_foreshadowing']:
                report_lines.append(f"- {fs['id']}: {fs['description']}...")
                report_lines.append(f"  引入于：{fs['introduced_in']}，已等待 {fs['chapters_pending']} 章")
            report_lines.append("")
        
        # 列出所有活跃伏笔
        report_lines.append("## 活跃伏笔列表")
        for fs in active_foreshadowing:
            report_lines.append(f"- **{fs.id}**: {fs.description[:100]}...")
            report_lines.append(f"  引入于：{fs.introduced_in}")
            if fs.related_characters:
                report_lines.append(f"  相关角色：{', '.join(fs.related_characters)}")
            report_lines.append("")
        
        return "\n".join(report_lines)
