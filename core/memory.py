"""
记忆系统模块

负责管理小说的记忆系统，包括事实表、向量数据库和摘要
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
    
    def update_facts(self, project_name: str, chapter: int, facts: List[Dict]):
        """更新事实表"""
        project_dir = self.base_path
        facts_dir = project_dir / 'memory' / 'facts'
        facts_dir.mkdir(parents=True, exist_ok=True)
        
        facts_file = facts_dir / 'facts.jsonl'
        
        # 读取现有事实
        existing_facts = []
        if facts_file.exists():
            with open(facts_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        existing_facts.append(json.loads(line))
        
        # 添加新事实
        for fact in facts:
            fact_entry = {
                'chapter': chapter,
                'timestamp': datetime.now().isoformat(),
                'content': fact.get('content', ''),
                'type': fact.get('type', 'general'),
                'entities': fact.get('entities', []),
                'importance': fact.get('importance', 'medium')
            }
            existing_facts.append(fact_entry)
        
        # 保存更新后的事实
        with open(facts_file, 'w', encoding='utf-8') as f:
            for fact in existing_facts:
                f.write(json.dumps(fact, ensure_ascii=False) + '\n')
    
    def get_facts(self, project_name: str, chapter_range: Optional[List[int]] = None) -> List[Dict]:
        """获取事实表"""
        project_dir = self.base_path
        facts_file = project_dir / 'memory' / 'facts' / 'facts.jsonl'
        
        if not facts_file.exists():
            return []
        
        facts = []
        with open(facts_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    fact = json.loads(line)
                    if chapter_range:
                        if fact.get('chapter') in chapter_range:
                            facts.append(fact)
                    else:
                        facts.append(fact)
        
        return facts
    
    def update_summaries(self, project_name: str, chapter: int, summary: str, summary_type: str = 'chapter'):
        """更新摘要"""
        project_dir = self.base_path
        summaries_dir = project_dir / 'memory' / 'summaries'
        summaries_dir.mkdir(parents=True, exist_ok=True)
        
        if summary_type == 'chapter':
            filename = f"chapter_{chapter:04d}_summary.txt"
        elif summary_type == 'volume':
            filename = f"volume_{chapter:04d}_summary.txt"
        else:
            filename = f"{summary_type}_{chapter:04d}_summary.txt"
        
        summary_file = summaries_dir / filename
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)
    
    def get_summaries(self, project_name: str, chapter_range: Optional[List[int]] = None, 
                     summary_type: str = 'chapter') -> List[Dict]:
        """获取摘要"""
        project_dir = self.base_path
        summaries_dir = project_dir / 'memory' / 'summaries'
        
        if not summaries_dir.exists():
            return []
        
        summaries = []
        for file in summaries_dir.glob(f"*_{summary_type}_*.txt"):
            # 从文件名提取章节号
            parts = file.stem.split('_')
            if len(parts) >= 2:
                try:
                    chapter_num = int(parts[1])
                    if chapter_range and chapter_num not in chapter_range:
                        continue
                    
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    summaries.append({
                        'chapter': chapter_num,
                        'type': summary_type,
                        'content': content
                    })
                except ValueError:
                    continue
        
        return summaries
    
    def search(self, project_name: str, query: str, query_type: str = 'plot') -> List[Dict]:
        """搜索记忆"""
        # 这里可以实现更复杂的搜索逻辑
        # 目前简化为关键词搜索
        
        results = []
        
        # 搜索事实
        facts = self.get_facts(project_name)
        for fact in facts:
            if query.lower() in fact.get('content', '').lower():
                results.append({
                    'title': f"事实：{fact.get('content', '')[:50]}...",
                    'type': 'fact',
                    'content': fact.get('content', ''),
                    'chapter': fact.get('chapter'),
                    'timestamp': fact.get('timestamp')
                })
        
        # 搜索摘要
        summaries = self.get_summaries(project_name)
        for summary in summaries:
            if query.lower() in summary.get('content', '').lower():
                results.append({
                    'title': f"摘要：第{summary.get('chapter')}章",
                    'type': 'summary',
                    'content': summary.get('content', ''),
                    'chapter': summary.get('chapter')
                })
        
        return results
    
    def get_stats(self, project_name: str) -> Dict:
        """获取记忆统计信息"""
        project_dir = self.base_path
        
        stats = {
            'facts_count': 0,
            'summaries_count': 0,
            'vector_size': 0
        }
        
        # 统计事实数
        facts_file = project_dir / 'memory' / 'facts' / 'facts.jsonl'
        if facts_file.exists():
            with open(facts_file, 'r', encoding='utf-8') as f:
                stats['facts_count'] = sum(1 for line in f if line.strip())
        
        # 统计摘要数
        summaries_dir = project_dir / 'memory' / 'summaries'
        if summaries_dir.exists():
            stats['summaries_count'] = len(list(summaries_dir.glob('*.txt')))
        
        # 统计向量数（简化实现）
        vectors_dir = project_dir / 'memory' / 'vectors'
        if vectors_dir.exists():
            stats['vector_size'] = len(list(vectors_dir.glob('*.json')))
        
        return stats
    
    def export_memory(self, project_name: str, output_path: Path):
        """导出记忆数据"""
        project_dir = self.base_path
        
        export_data = {
            'project': project_name,
            'exported_at': datetime.now().isoformat(),
            'facts': [],
            'summaries': []
        }
        
        # 导出事实
        facts = self.get_facts(project_name)
        export_data['facts'] = facts
        
        # 导出摘要
        summaries = self.get_summaries(project_name)
        export_data['summaries'] = summaries
        
        # 保存导出文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def import_memory(self, project_name: str, import_path: Path):
        """导入记忆数据"""
        with open(import_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        # 导入事实
        if 'facts' in import_data:
            self.update_facts(project_name, 0, import_data['facts'])
        
        # 导入摘要
        if 'summaries' in import_data:
            for summary in import_data['summaries']:
                self.update_summaries(
                    project_name, 
                    summary.get('chapter', 0), 
                    summary.get('content', ''),
                    summary.get('type', 'chapter')
                )
    
    def clear_memory(self, project_name: str):
        """清空记忆数据"""
        project_dir = self.base_path
        memory_dir = project_dir / 'memory'
        
        if memory_dir.exists():
            import shutil
            shutil.rmtree(memory_dir)
            memory_dir.mkdir(parents=True, exist_ok=True)