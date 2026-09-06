"""
记忆系统模块

每章独立记忆 + 全局聚合记忆
结构：
  chapters/ch{NNNN}/memory.json   ← 本章提取的记忆
  memory/
    timeline.jsonl       ← 全局时间线（append）
    event_log.jsonl      ← 全局事件流水（append）
    character_graph.json ← 角色关系图（整体更新）
    facts.jsonl          ← 动态事实表（append）
    summaries/
      ch{NNNN}.txt       ← 章节摘要（供滑动窗口读取）
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class MemoryManager:
    """记忆管理器"""

    def __init__(self, config: Dict, project_name: str = ""):
        self.config = config
        data_dir = config['storage']['data_dir']
        if project_name:
            data_dir = data_dir.replace('{project}', project_name)
        self.base_path = Path(data_dir)
        self.memory_dir = self.base_path / 'memory'

    # ── 全局文件路径 ──────────────────────────────────────────

    def _timeline_path(self) -> Path:
        return self.memory_dir / 'timeline.jsonl'

    def _event_log_path(self) -> Path:
        return self.memory_dir / 'event_log.jsonl'

    def _character_graph_path(self) -> Path:
        return self.memory_dir / 'character_graph.json'

    def _facts_path(self) -> Path:
        return self.memory_dir / 'facts' / 'facts.jsonl'

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

    # ── 搜索 ────────────────────────────────────────────────

    def search(self, query: str) -> List[Dict]:
        """跨记忆维度搜索"""
        results = []
        q = query.lower()

        for fact in self.get_facts():
            if q in fact.get('content', '').lower():
                results.append({'type': 'fact', 'chapter': fact['chapter'],
                                'content': fact['content']})

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
