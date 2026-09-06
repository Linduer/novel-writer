"""
存储管理模块 v2.0

负责项目文件的读写和管理
每章一个文件夹，支持元数据、草稿/最终版切换
优化：添加缓存、批量操作、文件索引
"""

import os
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from functools import lru_cache


class StorageManager:
    """存储管理器"""

    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
        self.project_name = project_name
        
        # 缓存
        self._cache = {
            'chapters': None,
            'project_config': None,
        }
        
        # 文件索引
        self._index = {
            'chapters': {},
            'characters': {},
            'world': {},
        }

    def _chapter_dir(self, chapter: int, chapter_name: str = "") -> Path:
        """获取章节文件夹路径：ch{num}_{name}"""
        if chapter_name:
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', chapter_name).strip()
            folder = f"ch{chapter:04d}_{safe_name}"
        else:
            folder = f"ch{chapter:04d}"
        return self.base_path / 'chapters' / folder

    def create_project(self, project_name: str) -> Path:
        """创建项目目录结构"""
        project_dir = self.base_path

        directories = [
            'outline',
            'characters',
            'world',
            'chapters',
            'memory',
            'memory/vectors',
            'memory/facts',
            'memory/summaries'
        ]

        for dir_name in directories:
            (project_dir / dir_name).mkdir(parents=True, exist_ok=True)

        project_config = {
            'name': project_name,
            'created_at': datetime.now().isoformat(),
            'status': 'initialized',
            'stats': {
                'total_chapters': self.config['project']['chapters'],
                'completed_chapters': 0,
                'total_words': 0
            }
        }

        with open(project_dir / 'project.json', 'w', encoding='utf-8') as f:
            json.dump(project_config, f, ensure_ascii=False, indent=2)

        return project_dir

    def load_project(self, project_name: str) -> Dict:
        """加载项目数据"""
        project_dir = self.base_path

        if not project_dir.exists():
            raise FileNotFoundError(f"项目不存在：{project_name}")

        with open(project_dir / 'project.json', 'r', encoding='utf-8') as f:
            project_config = json.load(f)

        outline = self._load_outline(project_dir / 'outline')
        characters = self._load_characters(project_dir / 'characters')
        world = self._load_world(project_dir / 'world')

        return {
            'config': project_config,
            'outline': outline,
            'characters': characters,
            'world': world
        }

    def _load_outline(self, outline_dir: Path) -> List[Dict]:
        """加载大纲文件"""
        outlines = []
        if outline_dir.exists():
            for ext in ('*.txt', '*.md'):
                for file in outline_dir.glob(ext):
                    outlines.append({
                        'filename': file.name,
                        'content': file.read_text(encoding='utf-8')
                    })
        return outlines

    def _load_characters(self, character_dir: Path) -> List[Dict]:
        """加载角色档案"""
        characters = []
        if character_dir.exists():
            for file in character_dir.glob('*.txt'):
                characters.append({
                    'filename': file.name,
                    'content': file.read_text(encoding='utf-8')
                })
        return characters

    def _load_world(self, world_dir: Path) -> Dict:
        """加载世界观设定"""
        world = {}
        if world_dir.exists():
            for ext in ('*.txt', '*.md'):
                for file in world_dir.glob(ext):
                    world[file.stem] = file.read_text(encoding='utf-8')
        return world

    def save_chapter(self, chapter: int, content: str, 
                     chapter_name: str = "", status: str = "draft",
                     extra_meta: Dict = None) -> Path:
        """
        保存章节到独立文件夹
        
        status: "draft" 或 "final"
        返回章节文件夹路径
        """
        ch_dir = self._chapter_dir(chapter, chapter_name)
        ch_dir.mkdir(parents=True, exist_ok=True)

        # 保存内容
        content_file = ch_dir / f"{status}.txt"
        content_file.write_text(content, encoding='utf-8')

        # 更新元数据
        meta_file = ch_dir / 'metadata.json'
        meta = self._load_meta(chapter)
        meta.update({
            'chapter': chapter,
            'chapter_name': chapter_name,
            'status': status,
            'word_count': len(content),
            'updated_at': datetime.now().isoformat(),
        })
        if meta.get('created_at') is None:
            meta['created_at'] = meta['updated_at']
        if extra_meta:
            meta.update(extra_meta)
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

        return ch_dir

    def _load_meta(self, chapter: int) -> Dict:
        """读取章节元数据（自动查找文件夹）"""
        chapters_dir = self.base_path / 'chapters'
        if not chapters_dir.exists():
            return {}
        for d in chapters_dir.iterdir():
            if d.is_dir() and d.name.startswith(f"ch{chapter:04d}"):
                meta_file = d / 'metadata.json'
                if meta_file.exists():
                    return json.loads(meta_file.read_text(encoding='utf-8'))
        return {}

    def load_chapter(self, chapter: int, status: str = None) -> Optional[str]:
        """
        加载章节内容
        status=None 时优先加载 final，其次 draft
        status="final" 或 "draft" 时精确加载
        """
        chapters_dir = self.base_path / 'chapters'
        if not chapters_dir.exists():
            return None

        for d in chapters_dir.iterdir():
            if d.is_dir() and d.name.startswith(f"ch{chapter:04d}"):
                if status:
                    f = d / f"{status}.txt"
                    return f.read_text(encoding='utf-8') if f.exists() else None
                # 优先 final
                final = d / 'final.txt'
                if final.exists():
                    return final.read_text(encoding='utf-8')
                draft = d / 'draft.txt'
                if draft.exists():
                    return draft.read_text(encoding='utf-8')
        return None

    def load_chapter_meta(self, chapter: int) -> Dict:
        """加载章节元数据"""
        return self._load_meta(chapter)

    def list_chapters(self) -> List[Dict]:
        """列出所有已保存章节（按章节号排序）"""
        chapters_dir = self.base_path / 'chapters'
        if not chapters_dir.exists():
            return []

        result = []
        for d in chapters_dir.iterdir():
            if d.is_dir() and d.name.startswith('ch'):
                meta_file = d / 'metadata.json'
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text(encoding='utf-8'))
                    result.append(meta)

        result.sort(key=lambda x: x.get('chapter', 0))
        return result

    def save_draft(self, project_name: str, chapter: int, content: str) -> Path:
        """保存草稿（兼容旧接口）"""
        ch_dir = self.save_chapter(chapter, content, status="draft")
        return ch_dir / 'draft.txt'

    def save_reviewed_chapter(self, project_name: str, chapter: int, content: str) -> Path:
        """保存审查后最终版（兼容旧接口）"""
        ch_dir = self.save_chapter(chapter, content, status="final")
        return ch_dir / 'final.txt'

    def update_project_stats(self, project_name: str):
        """更新 project.json 中的统计数据"""
        stats = self.get_project_stats(project_name)
        config_path = self.base_path / 'project.json'
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding='utf-8'))
            config['stats'] = stats
            config['updated_at'] = datetime.now().isoformat()
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8'
            )

    def get_project_stats(self, project_name: str) -> Dict:
        """获取项目统计信息"""
        config_path = self.base_path / 'project.json'
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding='utf-8'))
            stats = config.get('stats', {})
            # 动态计算已完成章节数
            chapters = self.list_chapters()
            stats['completed_chapters'] = len([
                c for c in chapters if c.get('status') == 'final'
            ])
            stats['total_words'] = sum(c.get('word_count', 0) for c in chapters)
            return stats
        return {}

    def backup_project(self, project_name: str) -> Path:
        """备份项目"""
        backup_dir = Path(
            self.config['storage']['backup']['backup_dir'].format(project=project_name)
        )
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"backup_{timestamp}"
        shutil.copytree(self.base_path, backup_path)
        return backup_path

    def list_projects(self) -> List[str]:
        """列出所有项目"""
        if not self.base_path.exists():
            return []
        projects = []
        for item in self.base_path.iterdir():
            if item.is_dir() and (item / 'project.json').exists():
                projects.append(item.name)
        return projects

    def delete_project(self, project_name: str) -> bool:
        """删除项目"""
        if not self.base_path.exists():
            return False
        shutil.rmtree(self.base_path)
        return True
    
    # ── 缓存管理 ──────────────────────────────────────────
    
    def clear_cache(self):
        """清除缓存"""
        self._cache = {
            'chapters': None,
            'project_config': None,
        }
        self._index = {
            'chapters': {},
            'characters': {},
            'world': {},
        }
    
    def _build_chapter_index(self):
        """构建章节索引"""
        if self._cache['chapters'] is not None:
            return
        
        chapters_dir = self.base_path / 'chapters'
        if not chapters_dir.exists():
            self._cache['chapters'] = []
            return
        
        result = []
        for d in chapters_dir.iterdir():
            if d.is_dir() and d.name.startswith('ch'):
                meta_file = d / 'metadata.json'
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text(encoding='utf-8'))
                    result.append(meta)
                    # 构建索引
                    chapter_num = meta.get('chapter', 0)
                    self._index['chapters'][chapter_num] = {
                        'path': d,
                        'meta': meta,
                    }
        
        result.sort(key=lambda x: x.get('chapter', 0))
        self._cache['chapters'] = result
    
    def get_chapter_path(self, chapter: int) -> Optional[Path]:
        """获取章节路径（使用索引）"""
        self._build_chapter_index()
        if chapter in self._index['chapters']:
            return self._index['chapters'][chapter]['path']
        return None
    
    def chapter_exists(self, chapter: int) -> bool:
        """检查章节是否存在"""
        return self.get_chapter_path(chapter) is not None
    
    def get_chapter_status(self, chapter: int) -> Optional[str]:
        """获取章节状态"""
        meta = self.load_chapter_meta(chapter)
        return meta.get('status')
    
    def get_all_chapters(self) -> List[int]:
        """获取所有章节号"""
        self._build_chapter_index()
        return sorted(self._index['chapters'].keys())
    
    def get_chapters_by_status(self, status: str) -> List[Dict]:
        """按状态获取章节"""
        self._build_chapter_index()
        return [
            meta for meta in self._cache['chapters']
            if meta.get('status') == status
        ]
    
    def get_chapter_range(self, start: int, end: int) -> List[Dict]:
        """获取章节范围"""
        self._build_chapter_index()
        return [
            meta for meta in self._cache['chapters']
            if start <= meta.get('chapter', 0) <= end
        ]
    
    # ── 批量操作 ──────────────────────────────────────────
    
    def batch_save(self, chapters: List[Dict]) -> List[Path]:
        """批量保存章节"""
        results = []
        for ch_data in chapters:
            chapter = ch_data.get('chapter')
            content = ch_data.get('content', '')
            chapter_name = ch_data.get('chapter_name', '')
            status = ch_data.get('status', 'draft')
            
            if chapter and content:
                path = self.save_chapter(chapter, content, chapter_name, status)
                results.append(path)
        
        # 清除缓存
        self.clear_cache()
        
        return results
    
    def batch_update_status(self, chapters: List[int], status: str) -> int:
        """批量更新章节状态"""
        updated = 0
        for chapter in chapters:
            meta = self.load_chapter_meta(chapter)
            if meta:
                meta['status'] = status
                meta['updated_at'] = datetime.now().isoformat()
                meta_file = self.get_chapter_path(chapter) / 'metadata.json'
                if meta_file.exists():
                    meta_file.write_text(
                        json.dumps(meta, ensure_ascii=False, indent=2),
                        encoding='utf-8'
                    )
                    updated += 1
        
        # 清除缓存
        self.clear_cache()
        
        return updated
    
    # ── 文件优化 ──────────────────────────────────────────
    
    def optimize_storage(self) -> Dict:
        """优化存储空间"""
        stats = {
            'removed_empty': 0,
            'removed_duplicate': 0,
            'compressed': 0,
        }
        
        chapters_dir = self.base_path / 'chapters'
        if not chapters_dir.exists():
            return stats
        
        # 删除空文件夹
        for d in chapters_dir.iterdir():
            if d.is_dir():
                files = list(d.iterdir())
                if not files:
                    d.rmdir()
                    stats['removed_empty'] += 1
        
        # 清除缓存
        self.clear_cache()
        
        return stats
    
    def get_storage_stats(self) -> Dict:
        """获取存储统计"""
        stats = {
            'total_chapters': 0,
            'total_size': 0,
            'by_status': {
                'draft': 0,
                'final': 0,
            },
        }
        
        self._build_chapter_index()
        
        for meta in self._cache['chapters']:
            stats['total_chapters'] += 1
            status = meta.get('status', 'draft')
            if status in stats['by_status']:
                stats['by_status'][status] += 1
        
        # 计算总大小
        if self.base_path.exists():
            for file in self.base_path.rglob('*'):
                if file.is_file():
                    stats['total_size'] += file.stat().st_size
        
        return stats
