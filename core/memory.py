"""
记忆系统模块 v2.0

每章独立记忆 + 全局聚合记忆
结构：
  chapters/ch{NNNN}/memory.json   ← 本章提取的记忆
  memory/
    timeline.jsonl       ← 全局时间线（append）
    event_log.jsonl      ← 全局事件流水（append）
    character_graph.json ← 角色关系图（整体更新）
    facts.jsonl          ← 动态事实表（append）
    numbers.jsonl        ← 数字记忆（append/update）
    summaries/
      ch{NNNN}.txt       ← 章节摘要（供滑动窗口读取）

优化：添加缓存、索引、批量操作
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from functools import lru_cache


class MemoryManager:
    """记忆管理器"""

    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
        self.memory_dir = self.base_path / 'memory'
        
        # 缓存
        self._cache = {
            'facts': None,
            'events': None,
            'timeline': None,
            'numbers': None,
            'summaries': None,
            'character_graph': None,
        }
        
        # 索引
        self._index = {
            'facts_by_chapter': {},
            'events_by_chapter': {},
            'numbers_by_type': {},
            'numbers_by_chapter': {},
        }

    # ── 按章节清除旧条目（防止重复写入）────────────────────

    def clear_chapter_entries(self, chapter: int):
        """清除指定章节在全局记忆中的所有条目，用于 save 时重新提取前清理"""
        self._remove_lines(self._event_log_path(), chapter)
        self._remove_lines(self._timeline_path(), chapter)
        self._remove_lines(self._facts_path(), chapter)
        self._remove_lines(self._numbers_path(), chapter)
        # 摘要直接覆盖，无需清除

    def _remove_lines(self, path: Path, chapter: int):
        """从 jsonl 文件中移除指定章节的所有行"""
        if not path.exists():
            return
        lines = path.read_text(encoding='utf-8').splitlines()
        kept = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get('chapter') != chapter:
                    kept.append(line)
            except json.JSONDecodeError:
                kept.append(line)
        path.write_text('\n'.join(kept) + ('\n' if kept else ''), encoding='utf-8')

    # ── 全局文件路径 ──────────────────────────────────────────

    def _timeline_path(self) -> Path:
        return self.memory_dir / 'timeline.jsonl'

    def _event_log_path(self) -> Path:
        return self.memory_dir / 'event_log.jsonl'

    def _character_graph_path(self) -> Path:
        return self.memory_dir / 'character_graph.json'

    def _facts_path(self) -> Path:
        return self.memory_dir / 'facts' / 'facts.jsonl'

    def _numbers_path(self) -> Path:
        return self.memory_dir / 'numbers.jsonl'

    def _summary_path(self, chapter: int) -> Path:
        return self.memory_dir / 'summaries' / f"ch{chapter:04d}.txt"

    # ── 本章记忆（保存在 chapters/ch{NNNN}/memory.json）───────

    def save_chapter_memory(self, chapter: int, memory_data: Dict):
        """保存本章提取的记忆（由LLM提取后调用）"""
        chapters_dir = self.base_path / 'chapters'
        for d in chapters_dir.iterdir():
            if d.is_dir() and d.name.startswith(f"ch{chapter:04d}"):
                mem_file = d / 'memory.json'
                mem_file.write_text(
                    json.dumps(memory_data, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
                return

    def load_chapter_memory(self, chapter: int) -> Dict:
        """读取本章记忆"""
        chapters_dir = self.base_path / 'chapters'
        if not chapters_dir.exists():
            return {}
        for d in chapters_dir.iterdir():
            if d.is_dir() and d.name.startswith(f"ch{chapter:04d}"):
                mem_file = d / 'memory.json'
                if mem_file.exists():
                    return json.loads(mem_file.read_text(encoding='utf-8'))
        return {}

    # ── 摘要 ─────────────────────────────────────────────────

    def save_summary(self, chapter: int, summary: str):
        """保存章节摘要（供上下文引擎的滑动窗口读取）"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        (self.memory_dir / 'summaries').mkdir(exist_ok=True)
        self._summary_path(chapter).write_text(summary, encoding='utf-8')

    def get_summaries(self, chapters: List[int] = None) -> List[Dict]:
        """批量获取章节摘要，按章节号排序"""
        summaries_dir = self.memory_dir / 'summaries'
        if not summaries_dir.exists():
            return []

        result = []
        for f in summaries_dir.glob('ch*.txt'):
            try:
                ch_num = int(f.stem[2:])
            except ValueError:
                continue
            if chapters and ch_num not in chapters:
                continue
            result.append({
                'chapter': ch_num,
                'content': f.read_text(encoding='utf-8')
            })
        result.sort(key=lambda x: x['chapter'])
        return result

    def get_summary(self, chapter: int) -> Optional[str]:
        """获取单章摘要"""
        p = self._summary_path(chapter)
        return p.read_text(encoding='utf-8') if p.exists() else None

    # ── 事件流水 ──────────────────────────────────────────────

    def append_events(self, chapter: int, events: List[Dict]):
        """追加事件到全局事件流水"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(self._event_log_path(), 'a', encoding='utf-8') as f:
            for ev in events:
                entry = {
                    'chapter': chapter,
                    'timestamp': datetime.now().isoformat(),
                    **ev
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def get_events(self, chapter_range: List[int] = None) -> List[Dict]:
        """读取事件流水"""
        path = self._event_log_path()
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            if chapter_range and ev.get('chapter') not in chapter_range:
                continue
            events.append(ev)
        return events

    # ── 时间线 ───────────────────────────────────────────────

    def append_timeline(self, chapter: int, entries: List[Dict]):
        """追加时间线条目"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(self._timeline_path(), 'a', encoding='utf-8') as f:
            for entry in entries:
                row = {
                    'chapter': chapter,
                    'timestamp': datetime.now().isoformat(),
                    **entry
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

    def get_timeline(self, chapter_range: List[int] = None) -> List[Dict]:
        """读取时间线"""
        path = self._timeline_path()
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if chapter_range and entry.get('chapter') not in chapter_range:
                continue
            entries.append(entry)
        return entries

    # ── 角色关系图 ──────────────────────────────────────────

    def update_character_graph(self, chapter: int, 
                               characters_involved: List[str],
                               relationship_changes: List[Dict]):
        """
        更新角色关系图
        relationship_changes 格式：
          [{"from": "林远", "to": "系统", "relation": "拥有", "detail": "..."}]
        """
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        graph = self._load_character_graph()

        # 更新角色出场记录
        for name in characters_involved:
            if name not in graph.get('characters', {}):
                graph.setdefault('characters', {})[name] = {
                    'first_appearance': chapter,
                    'last_appearance': chapter,
                    'appearances': [chapter]
                }
            else:
                ch = graph['characters'][name]
                ch['last_appearance'] = chapter
                if chapter not in ch.get('appearances', []):
                    ch.setdefault('appearances', []).append(chapter)

        # 更新关系边
        for change in relationship_changes:
            key = f"{change['from']}→{change['to']}"
            reverse_key = f"{change['to']}→{change['from']}"
            edges = graph.setdefault('relationships', {})

            if key in edges:
                edges[key]['detail'] = change.get('detail', edges[key]['detail'])
                edges[key]['last_seen'] = chapter
            elif reverse_key in edges:
                edges[reverse_key]['detail'] = change.get('detail', edges[reverse_key]['detail'])
                edges[reverse_key]['last_seen'] = chapter
            else:
                edges[key] = {
                    'from': change['from'],
                    'to': change['to'],
                    'relation': change.get('relation', ''),
                    'detail': change.get('detail', ''),
                    'first_seen': chapter,
                    'last_seen': chapter
                }

        graph['updated_at'] = datetime.now().isoformat()
        self._character_graph_path().write_text(
            json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    def _load_character_graph(self) -> Dict:
        path = self._character_graph_path()
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        return {'characters': {}, 'relationships': {}, 'updated_at': None}

    def get_character_graph(self) -> Dict:
        return self._load_character_graph()

    # ── 事实表 ───────────────────────────────────────────────

    def append_facts(self, chapter: int, facts: List[Dict]):
        """追加事实"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        facts_dir = self.memory_dir / 'facts'
        facts_dir.mkdir(exist_ok=True)
        with open(self._facts_path(), 'a', encoding='utf-8') as f:
            for fact in facts:
                entry = {
                    'chapter': chapter,
                    'timestamp': datetime.now().isoformat(),
                    **fact
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def get_facts(self, chapter_range: List[int] = None) -> List[Dict]:
        """读取事实表"""
        path = self._facts_path()
        if not path.exists():
            return []
        facts = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            fact = json.loads(line)
            if chapter_range and fact.get('chapter') not in chapter_range:
                continue
            facts.append(fact)
        return facts

    # ── 数字记忆 ──────────────────────────────────────────────

    def append_numbers(self, chapter: int, numbers: List[Dict]):
        """追加数字记忆"""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(self._numbers_path(), 'a', encoding='utf-8') as f:
            for num in numbers:
                entry = {
                    'chapter': chapter,
                    'timestamp': datetime.now().isoformat(),
                    **num
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def get_numbers(self, chapter_range: List[int] = None,
                     number_type: str = None) -> List[Dict]:
        """读取数字记忆"""
        path = self._numbers_path()
        if not path.exists():
            return []
        numbers = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            num = json.loads(line)
            if chapter_range and num.get('chapter') not in chapter_range:
                continue
            if number_type and num.get('type') != number_type:
                continue
            numbers.append(num)
        return numbers

    def get_number_by_id(self, number_id: str) -> Optional[Dict]:
        """根据ID获取数字记忆"""
        for num in self.get_numbers():
            if num.get('id') == number_id:
                return num
        return None

    def get_numbers_for_chapter(self, chapter: int) -> List[Dict]:
        """获取指定章节需要用到的数字（当前章节出场角色的数字 + 活跃伏笔相关数字）"""
        all_numbers = self.get_numbers()
        relevant = []
        for num in all_numbers:
            # 数字首次出现在当前章节或之前
            if num.get('chapter', 0) <= chapter:
                # 数字状态为活跃
                if num.get('status', 'active') in ['active', 'changed']:
                    relevant.append(num)
        return relevant

    def update_number_status(self, number_id: str, status: str,
                              current_value: str = None,
                              change_chapter: int = None,
                              reason: str = None):
        """更新数字记忆状态"""
        numbers = self.get_numbers()
        updated = False
        for num in numbers:
            if num.get('id') == number_id:
                old_value = num.get('current_value', num.get('value'))
                num['status'] = status
                if current_value:
                    num['current_value'] = current_value
                if change_chapter and reason:
                    change_history = num.get('change_history', [])
                    change_history.append({
                        'chapter': change_chapter,
                        'old_value': old_value,
                        'new_value': current_value,
                        'reason': reason
                    })
                    num['change_history'] = change_history
                num['last_used_in'] = change_chapter
                updated = True
                break
        
        if updated:
            # 重写文件
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            with open(self._numbers_path(), 'w', encoding='utf-8') as f:
                for num in numbers:
                    f.write(json.dumps(num, ensure_ascii=False) + '\n')

    # ── 搜索 ────────────────────────────────────────────────

    def search(self, query: str) -> List[Dict]:
        """跨记忆维度搜索"""
        results = []
        q = query.lower()

        for fact in self.get_facts():
            if q in fact.get('content', '').lower():
                results.append({'type': 'fact', 'chapter': fact['chapter'],
                                'content': fact['content']})

        for num in self.get_numbers():
            if q in num.get('context', '').lower() or q in num.get('value', '').lower():
                results.append({'type': 'number', 'chapter': num['chapter'],
                                'content': f"{num.get('context')}: {num.get('value')}"})

        for s in self.get_summaries():
            if q in s['content'].lower():
                results.append({'type': 'summary', 'chapter': s['chapter'],
                                'content': s['content'][:200]})

        graph = self.get_character_graph()
        for name, info in graph.get('characters', {}).items():
            if q in name.lower():
                results.append({'type': 'character', 'chapter': info.get('first_appearance'),
                                'content': f"{name} 首次出场第{info.get('first_appearance')}章"})

        return results

    # ── 统计 ────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        return {
            'facts_count': self._count_lines(self._facts_path()),
            'events_count': self._count_lines(self._event_log_path()),
            'timeline_count': self._count_lines(self._timeline_path()),
            'numbers_count': self._count_lines(self._numbers_path()),
            'summaries_count': len(list((self.memory_dir / 'summaries').glob('ch*.txt'))
                                   if (self.memory_dir / 'summaries').exists() else []),
            'character_count': len(self.get_character_graph().get('characters', {})),
        }

    def _count_lines(self, path: Path) -> int:
        if not path.exists():
            return 0
        with open(path, 'r', encoding='utf-8') as f:
            return sum(1 for line in f if line.strip())

    # ── 导出/导入 ───────────────────────────────────────────

    def export_memory(self, output_path: Path):
        data = {
            'exported_at': datetime.now().isoformat(),
            'facts': self.get_facts(),
            'events': self.get_events(),
            'timeline': self.get_timeline(),
            'numbers': self.get_numbers(),
            'character_graph': self.get_character_graph(),
            'summaries': [
                {'chapter': s['chapter'], 'content': s['content']}
                for s in self.get_summaries()
            ]
        }
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    def import_memory(self, import_path: Path):
        data = json.loads(import_path.read_text(encoding='utf-8'))
        if 'facts' in data:
            for fact in data['facts']:
                self.append_facts(fact.get('chapter', 0), [fact])
        if 'events' in data:
            for ev in data['events']:
                self.append_events(ev.get('chapter', 0), [ev])
        if 'timeline' in data:
            for entry in data['timeline']:
                self.append_timeline(entry.get('chapter', 0), [entry])
        if 'numbers' in data:
            for num in data['numbers']:
                self.append_numbers(num.get('chapter', 0), [num])
        if 'character_graph' in data:
            path = self._character_graph_path()
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data['character_graph'], ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        if 'summaries' in data:
            for s in data['summaries']:
                self.save_summary(s['chapter'], s['content'])

    def clear_memory(self):
        """清空所有记忆"""
        if self.memory_dir.exists():
            import shutil
            shutil.rmtree(self.memory_dir)
            self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 清除缓存
        self.clear_cache()
    
    # ── 缓存管理 ──────────────────────────────────────────
    
    def clear_cache(self):
        """清除缓存"""
        self._cache = {
            'facts': None,
            'events': None,
            'timeline': None,
            'numbers': None,
            'summaries': None,
            'character_graph': None,
        }
        self._index = {
            'facts_by_chapter': {},
            'events_by_chapter': {},
            'numbers_by_type': {},
            'numbers_by_chapter': {},
        }
    
    def _build_facts_index(self):
        """构建事实索引"""
        if self._cache['facts'] is not None:
            return
        
        facts = self.get_facts()
        self._cache['facts'] = facts
        
        # 构建索引
        for fact in facts:
            chapter = fact.get('chapter', 0)
            if chapter not in self._index['facts_by_chapter']:
                self._index['facts_by_chapter'][chapter] = []
            self._index['facts_by_chapter'][chapter].append(fact)
    
    def _build_events_index(self):
        """构建事件索引"""
        if self._cache['events'] is not None:
            return
        
        events = self.get_events()
        self._cache['events'] = events
        
        # 构建索引
        for event in events:
            chapter = event.get('chapter', 0)
            if chapter not in self._index['events_by_chapter']:
                self._index['events_by_chapter'][chapter] = []
            self._index['events_by_chapter'][chapter].append(event)
    
    def _build_numbers_index(self):
        """构建数字索引"""
        if self._cache['numbers'] is not None:
            return
        
        numbers = self.get_numbers()
        self._cache['numbers'] = numbers
        
        # 构建索引
        for num in numbers:
            # 按类型索引
            num_type = num.get('type', 'other')
            if num_type not in self._index['numbers_by_type']:
                self._index['numbers_by_type'][num_type] = []
            self._index['numbers_by_type'][num_type].append(num)
            
            # 按章节索引
            chapter = num.get('chapter', 0)
            if chapter not in self._index['numbers_by_chapter']:
                self._index['numbers_by_chapter'][chapter] = []
            self._index['numbers_by_chapter'][chapter].append(num)
    
    # ── 优化查询 ──────────────────────────────────────────
    
    def get_facts_by_chapter(self, chapter: int) -> List[Dict]:
        """获取指定章节的事实（使用索引）"""
        self._build_facts_index()
        return self._index['facts_by_chapter'].get(chapter, [])
    
    def get_events_by_chapter(self, chapter: int) -> List[Dict]:
        """获取指定章节的事件（使用索引）"""
        self._build_events_index()
        return self._index['events_by_chapter'].get(chapter, [])
    
    def get_numbers_by_type(self, number_type: str) -> List[Dict]:
        """获取指定类型的数字（使用索引）"""
        self._build_numbers_index()
        return self._index['numbers_by_type'].get(number_type, [])
    
    def get_numbers_by_chapter(self, chapter: int) -> List[Dict]:
        """获取指定章节的数字（使用索引）"""
        self._build_numbers_index()
        return self._index['numbers_by_chapter'].get(chapter, [])
    
    def get_recent_facts(self, count: int = 10) -> List[Dict]:
        """获取最近的事实"""
        self._build_facts_index()
        all_facts = self._cache['facts'] or []
        return sorted(all_facts, key=lambda x: x.get('chapter', 0), reverse=True)[:count]
    
    def get_recent_events(self, count: int = 10) -> List[Dict]:
        """获取最近的事件"""
        self._build_events_index()
        all_events = self._cache['events'] or []
        return sorted(all_events, key=lambda x: x.get('chapter', 0), reverse=True)[:count]
    
    def get_active_numbers(self) -> List[Dict]:
        """获取活跃的数字记忆"""
        self._build_numbers_index()
        all_numbers = self._cache['numbers'] or []
        return [n for n in all_numbers if n.get('status') in ['active', 'changed']]
    
    def get_number_by_value(self, value: str) -> Optional[Dict]:
        """根据值获取数字记忆"""
        self._build_numbers_index()
        for num in (self._cache['numbers'] or []):
            if num.get('value') == value or value in num.get('aliases', []):
                return num
        return None
    
    # ── 批量操作 ──────────────────────────────────────────
    
    def batch_append_facts(self, facts_by_chapter: Dict[int, List[Dict]]) -> int:
        """批量追加事实"""
        total = 0
        for chapter, facts in facts_by_chapter.items():
            self.append_facts(chapter, facts)
            total += len(facts)
        
        # 清除缓存
        self.clear_cache()
        
        return total
    
    def batch_append_events(self, events_by_chapter: Dict[int, List[Dict]]) -> int:
        """批量追加事件"""
        total = 0
        for chapter, events in events_by_chapter.items():
            self.append_events(chapter, events)
            total += len(events)
        
        # 清除缓存
        self.clear_cache()
        
        return total
    
    def batch_save_summaries(self, summaries: Dict[int, str]) -> int:
        """批量保存摘要"""
        total = 0
        for chapter, summary in summaries.items():
            self.save_summary(chapter, summary)
            total += 1
        
        # 清除缓存
        self.clear_cache()
        
        return total
    
    # ── 统计优化 ──────────────────────────────────────────
    
    def get_memory_stats(self) -> Dict:
        """获取记忆统计（优化版本）"""
        self._build_facts_index()
        self._build_events_index()
        self._build_numbers_index()
        
        return {
            'facts_count': len(self._cache['facts'] or []),
            'events_count': len(self._cache['events'] or []),
            'timeline_count': self._count_lines(self._timeline_path()),
            'numbers_count': len(self._cache['numbers'] or []),
            'summaries_count': len(list((self.memory_dir / 'summaries').glob('ch*.txt'))
                                   if (self.memory_dir / 'summaries').exists() else []),
            'character_count': len(self.get_character_graph().get('characters', {})),
            'active_numbers': len(self.get_active_numbers()),
            'chapters_with_facts': len(self._index['facts_by_chapter']),
            'chapters_with_events': len(self._index['events_by_chapter']),
        }
