"""
存储管理模块

负责项目文件的读写和管理
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

class StorageManager:
    """存储管理器"""
    
    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
        self.project_name = project_name
    
    def create_project(self, project_name: str) -> Path:
        """创建项目目录结构"""
        project_dir = self.base_path
        
        # 创建目录结构
        directories = [
            'outline',
            'characters',
            'world',
            'chapters',
            'chapters/drafts',
            'chapters/final',
            'memory',
            'memory/vectors',
            'memory/facts',
            'memory/summaries'
        ]
        
        for dir_name in directories:
            dir_path = project_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 创建项目配置文件
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
        
        config_path = project_dir / 'project.json'
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(project_config, f, ensure_ascii=False, indent=2)
        
        return project_dir
    
    def load_project(self, project_name: str) -> Dict:
        """加载项目数据"""
        project_dir = self.base_path
        
        if not project_dir.exists():
            raise FileNotFoundError(f"项目不存在：{project_name}")
        
        # 加载项目配置
        config_path = project_dir / 'project.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            project_config = json.load(f)
        
        # 加载大纲
        outline = self._load_outline(project_dir / 'outline')
        
        # 加载角色
        characters = self._load_characters(project_dir / 'characters')
        
        # 加载世界观
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
            for file in outline_dir.glob('*.txt'):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                outlines.append({
                    'filename': file.name,
                    'content': content
                })
            for file in outline_dir.glob('*.md'):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                outlines.append({
                    'filename': file.name,
                    'content': content
                })
        return outlines
    
    def _load_characters(self, character_dir: Path) -> List[Dict]:
        """加载角色档案"""
        characters = []
        if character_dir.exists():
            for file in character_dir.glob('*.txt'):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                characters.append({
                    'filename': file.name,
                    'content': content
                })
        return characters
    
    def _load_world(self, world_dir: Path) -> Dict:
        """加载世界观设定"""
        world = {}
        if world_dir.exists():
            for file in world_dir.glob('*.txt'):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                world[file.stem] = content
            for file in world_dir.glob('*.md'):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                world[file.stem] = content
        return world
    
    def save_draft(self, project_name: str, chapter: int, content: str) -> Path:
        """保存章节草稿"""
        project_dir = self.base_path
        draft_dir = project_dir / 'chapters' / 'drafts'
        draft_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"chapter_{chapter:04d}.txt"
        draft_path = draft_dir / filename
        
        with open(draft_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return draft_path
    
    def load_chapter(self, project_name: str, chapter: int) -> Optional[str]:
        """加载章节内容"""
        project_dir = self.base_path
        
        # 优先加载最终版
        final_path = project_dir / 'chapters' / 'final' / f"chapter_{chapter:04d}.txt"
        if final_path.exists():
            with open(final_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # 加载草稿
        draft_path = project_dir / 'chapters' / 'drafts' / f"chapter_{chapter:04d}.txt"
        if draft_path.exists():
            with open(draft_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
    
    def save_reviewed_chapter(self, project_name: str, chapter: int, content: str) -> Path:
        """保存审查后的章节"""
        project_dir = self.base_path
        final_dir = project_dir / 'chapters' / 'final'
        final_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"chapter_{chapter:04d}.txt"
        final_path = final_dir / filename
        
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return final_path
    
    def get_project_stats(self, project_name: str) -> Dict:
        """获取项目统计信息"""
        project_dir = self.base_path
        
        if not project_dir.exists():
            return {}
        
        # 加载项目配置
        config_path = project_dir / 'project.json'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('stats', {})
        
        return {}
    
    def backup_project(self, project_name: str) -> Path:
        """备份项目"""
        project_dir = self.base_path
        backup_dir = Path(self.config['storage']['backup']['backup_dir'].format(project=project_name))
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}"
        backup_path = backup_dir / backup_name
        
        shutil.copytree(project_dir, backup_path)
        
        return backup_path
    
    def list_projects(self) -> List[str]:
        """列出所有项目"""
        if not self.base_path.exists():
            return []
        
        projects = []
        for item in self.base_path.iterdir():
            if item.is_dir():
                config_path = item / 'project.json'
                if config_path.exists():
                    projects.append(item.name)
        
        return projects
    
    def delete_project(self, project_name: str) -> bool:
        """删除项目"""
        project_dir = self.base_path
        
        if not project_dir.exists():
            return False
        
        shutil.rmtree(project_dir)
        return True