#!/usr/bin/env python3
"""
长篇小说写作助手 - 主程序入口

工作流：生成 → 一致性检查 → 手动编辑 → 保存 → 更新记忆
"""

import os
import sys
import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.storage import StorageManager
from core.memory import MemoryManager
from core.context import ContextEngine
from core.llm import LLMManager
from core.checker import ConsistencyChecker
from core.foreshadowing import ForeshadowingManager
from core.chapter_connection import ChapterConnectionManager

console = Console()


def load_config():
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        console.print("[red]错误：未找到config.yaml配置文件[/red]")
        console.print("请复制config.example.yaml为config.yaml并填入配置")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _init_managers(config):
    """初始化所有管理器"""
    pname = config['project']['name']
    return {
        'storage':   StorageManager(config, pname),
        'memory':    MemoryManager(config, pname),
        'context':   ContextEngine(config, pname),
        'llm':       LLMManager(config),
        'checker':   ConsistencyChecker(config, pname),
        'foreshadow': ForeshadowingManager(config, pname),
        'connection': ChapterConnectionManager(config, pname),
        'project_name': pname,
    }


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """长篇小说写作助手 - 基于GLM的超长小说上下文管理系统"""
    pass


# ═══════════════════════════════════════════════════════════════
#  init — 初始化项目
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--name', prompt='项目名称', help='小说项目名称')
def init(name):
    """初始化新的小说项目"""
    console.print(Panel(f"[bold green]初始化项目：{name}[/bold green]"))
    config = load_config()
    storage = StorageManager(config)
    project_dir = storage.create_project(name)
    console.print(f"[green]✓[/green] 项目目录已创建：{project_dir}")

    table = Table(title="项目结构")
    table.add_column("目录", style="cyan")
    table.add_column("说明", style="white")
    table.add_row("outline/",    "大纲文件（卷/章大纲）")
    table.add_row("characters/", "角色档案")
    table.add_row("world/",      "世界观设定")
    table.add_row("chapters/",   "每章一个文件夹（含草稿、最终版、元数据、本章记忆）")
    table.add_row("memory/",     "全局记忆（时间线、事件流水、角色关系图、事实表、摘要）")
    console.print(table)

    console.print("\n[bold]下一步：[/bold]")
    console.print("  1. 将大纲放入 outline/")
    console.print("  2. 将角色档案放入 characters/")
    console.print("  3. 将世界观设定放入 world/")
    console.print("  4. 运行 python main.py import 导入设定")


# ═══════════════════════════════════════════════════════════════
#  write — 生成章节草稿（自动触发一致性检查 + 记忆提取）
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--chapter', type=int, required=True, help='章节编号')
@click.option('--volume',  type=int, help='卷编号（可选，默认自动推算）')
def write(chapter, volume):
    """生成章节草稿（自动检查 + 提取记忆）"""
    console.print(Panel(f"[bold blue]写作章节：第{chapter}章[/bold blue]"))
    config = load_config()
    m = _init_managers(config)
    pname = m['project_name']
    volume = volume or (chapter - 1) // 96 + 1

    # 1. 构建上下文
    console.print("[cyan]构建写作上下文...[/cyan]")
    project_data = m['storage'].load_project(pname)
    ctx = m['context'].build_writing_context(project_data, chapter, volume)
    token_report = m['context'].get_token_usage_report(ctx)
    console.print(f"  [dim]{token_report}[/dim]")
    if ctx.get('is_over_budget'):
        console.print("[red]⚠ 上下文已超出Token预算[/red]")

    # 2. 生成草稿（带章节衔接）
    console.print("[cyan]生成章节草稿...[/cyan]")
    draft = m['llm'].generate_chapter_with_connection(ctx, chapter, volume)

    # 3. 保存草稿
    ch_dir = m['storage'].save_chapter(chapter, draft, status="draft")
    console.print(f"[green]✓[/green] 草稿已保存：{ch_dir}")

    # 4. 一致性检查
    console.print("[cyan]一致性检查...[/cyan]")
    check = m['checker'].check_chapter(chapter, draft, project_data)
    if check['passed']:
        console.print("[green]✓[/green] 一致性检查通过")
    else:
        console.print("[yellow]⚠ 发现问题：[/yellow]")
        for issue in check['issues']:
            console.print(f"    - {issue}")

    # 5. 提取记忆（摘要 + 事件 + 时间线 + 角色关系 + 伏笔 + 事实）
    console.print("[cyan]提取章节记忆...[/cyan]")
    mem = m['llm'].extract_chapter_memory(draft, chapter, volume)

    # 保存本章记忆文件
    m['memory'].save_chapter_memory(chapter, mem)

    # 摘要 → memory/summaries/chNNNN.txt（上下文引擎滑动窗口需要）
    m['memory'].save_summary(chapter, mem.get('summary', ''))

    # 事实 → memory/facts/facts.jsonl
    if mem.get('facts'):
        m['memory'].append_facts(chapter, mem['facts'])

    # 事件流水 → memory/event_log.jsonl
    if mem.get('events'):
        m['memory'].append_events(chapter, mem['events'])

    # 时间线 → memory/timeline.jsonl
    if mem.get('timeline'):
        m['memory'].append_timeline(chapter, mem['timeline'])

    # 角色关系图 → memory/character_graph.json
    characters_in_chapter = []
    for ev in mem.get('events', []):
        characters_in_chapter.extend(ev.get('characters', []))
    for cc in mem.get('character_changes', []):
        if cc.get('name') and cc['name'] not in characters_in_chapter:
            characters_in_chapter.append(cc['name'])
    characters_in_chapter = list(set(characters_in_chapter))

    if characters_in_chapter or mem.get('relationship_changes'):
        m['memory'].update_character_graph(
            chapter, characters_in_chapter, mem.get('relationship_changes', [])
        )

    # 伏笔（写入全局 foreshadowing.json）
    for hint in mem.get('foreshadowing', []):
        hint_text = hint.get('hint', '')
        if not hint_text:
            continue
        if hint.get('status') == 'new':
            from core.foreshadowing import Foreshadowing, ForeshadowingStatus
            fs_id = f"ch{chapter:04d}_{len(hint_text[:10])}"
            new_fs = Foreshadowing(
                id=fs_id,
                introduced_in=f"ch{chapter:04d}",
                description=hint_text,
                related_characters=characters_in_chapter[:5],
                status=ForeshadowingStatus.ACTIVE
            )
            m['foreshadow'].add_foreshadowing(pname, new_fs)
        elif hint.get('status') == 'resolved':
            # 按描述模糊匹配已有伏笔并解决
            active = m['foreshadow'].get_active_foreshadowing(pname)
            for fs in active:
                if hint_text[:10] in fs.description or fs.description[:10] in hint_text:
                    m['foreshadow'].resolve_foreshadowing(pname, fs.id, f"ch{chapter:04d}")
                    break

    # 更新项目统计
    m['storage'].update_project_stats(pname)

    # 显示记忆摘要
    console.print(f"\n[bold green]第{chapter}章草稿已生成[/bold green]")
    console.print(f"  摘要：{mem.get('summary', '')[:100]}...")
    console.print(f"  事件：{len(mem.get('events', []))} 条")
    console.print(f"  时间线：{len(mem.get('timeline', []))} 条")
    console.print(f"  角色变化：{len(mem.get('character_changes', []))} 条")
    console.print(f"  关系变化：{len(mem.get('relationship_changes', []))} 条")
    console.print(f"  伏笔：{len(mem.get('foreshadowing', []))} 条")
    console.print(f"\n[dim]如需修改，请运行：python main.py edit --chapter {chapter}[/dim]")
    console.print(f"修改后运行：python main.py save --chapter {chapter} 保存并更新记忆")


# ═══════════════════════════════════════════════════════════════
#  edit — 手动编辑章节（打开编辑器或终端内编辑）
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--chapter', type=int, required=True, help='章节编号')
@click.option('--editor',  is_flag=True, help='用系统默认编辑器打开')
def edit(chapter, editor):
    """手动编辑章节内容"""
    config = load_config()
    m = _init_managers(config)
    pname = m['project_name']

    content = m['storage'].load_chapter(chapter)
    if not content:
        console.print(f"[red]错误：未找到第{chapter}章内容，请先 write 生成[/red]")
        return

    console.print(Panel(f"[bold yellow]编辑章节：第{chapter}章[/bold yellow]"))
    console.print(f"[dim]当前字数：{len(content)} 字[/dim]\n")

    if editor:
        # 用系统编辑器打开草稿
        ch_dir = m['storage']._chapter_dir(chapter)
        draft_path = ch_dir / 'draft.txt'
        if not draft_path.exists():
            draft_path = ch_dir / 'final.txt'
        if draft_path.exists():
            os.startfile(str(draft_path))
            console.print(f"[cyan]已用系统编辑器打开：{draft_path}[/cyan]")
            console.print("[dim]编辑完成后按回车继续...[/dim]")
            input()
        else:
            console.print("[red]找不到可编辑的文件[/red]")
            return
    else:
        # 终端内直接编辑（显示内容，让用户粘贴修改后的全文）
        console.print("[dim]当前内容（前500字）：[/dim]")
        console.print(content[:500])
        console.print("[dim]...[/dim]\n")
        console.print("[cyan]请粘贴修改后的完整章节内容，然后按两次回车确认：[/cyan]")

        lines = []
        empty_count = 0
        while True:
            try:
                line = input()
                if line == '':
                    empty_count += 1
                    if empty_count >= 2:
                        break
                    lines.append(line)
                else:
                    empty_count = 0
                    lines.append(line)
            except EOFError:
                break
        content = '\n'.join(lines).strip()

    # 保存为草稿（等待 save 命令确认最终版）
    m['storage'].save_chapter(chapter, content, status="draft")
    console.print(f"[green]✓[/green] 草稿已保存（第{chapter}章）")
    console.print(f"[dim]运行 python main.py save --chapter {chapter} 保存最终版并更新记忆[/dim]")


# ═══════════════════════════════════════════════════════════════
#  save — 确认保存最终版 + 更新记忆
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--chapter', type=int, required=True, help='章节编号')
@click.option('--yes',     is_flag=True, help='跳过确认直接保存')
def save(chapter, yes):
    """确认保存最终版并更新记忆（edit 之后运行）"""
    config = load_config()
    m = _init_managers(config)
    pname = m['project_name']

    content = m['storage'].load_chapter(chapter, status="draft")
    if not content:
        console.print(f"[red]错误：未找到第{chapter}章草稿[/red]")
        return

    console.print(Panel(f"[bold green]保存第{chapter}章最终版[/bold green]"))
    console.print(f"[dim]字数：{len(content)}[/dim]\n")

    if not yes:
        if not Confirm.ask("确认将当前草稿保存为最终版并更新记忆？"):
            console.print("[yellow]已取消[/yellow]")
            return

    # 1. 保存最终版
    m['storage'].save_chapter(chapter, content, status="final")
    console.print(f"[green]✓[/green] 最终版已保存")

    # 2. 重新提取记忆（内容可能已修改）
    volume = (chapter - 1) // 96 + 1
    console.print("[cyan]重新提取章节记忆...[/cyan]")
    mem = m['llm'].extract_chapter_memory(content, chapter, volume)

    # 保存本章记忆
    m['memory'].save_chapter_memory(chapter, mem)
    m['memory'].save_summary(chapter, mem.get('summary', ''))

    if mem.get('facts'):
        m['memory'].append_facts(chapter, mem['facts'])
    if mem.get('events'):
        m['memory'].append_events(chapter, mem['events'])
    if mem.get('timeline'):
        m['memory'].append_timeline(chapter, mem['timeline'])

    characters_in_chapter = []
    for ev in mem.get('events', []):
        characters_in_chapter.extend(ev.get('characters', []))
    for cc in mem.get('character_changes', []):
        if cc.get('name') and cc['name'] not in characters_in_chapter:
            characters_in_chapter.append(cc['name'])
    characters_in_chapter = list(set(characters_in_chapter))

    if characters_in_chapter or mem.get('relationship_changes'):
        m['memory'].update_character_graph(
            chapter, characters_in_chapter, mem.get('relationship_changes', [])
        )

    for hint in mem.get('foreshadowing', []):
        hint_text = hint.get('hint', '')
        if not hint_text:
            continue
        if hint.get('status') == 'new':
            from core.foreshadowing import Foreshadowing, ForeshadowingStatus
            fs_id = f"ch{chapter:04d}_{len(hint_text[:10])}"
            new_fs = Foreshadowing(
                id=fs_id,
                introduced_in=f"ch{chapter:04d}",
                description=hint_text,
                related_characters=characters_in_chapter[:5],
                status=ForeshadowingStatus.ACTIVE
            )
            m['foreshadow'].add_foreshadowing(pname, new_fs)
        elif hint.get('status') == 'resolved':
            active = m['foreshadow'].get_active_foreshadowing(pname)
            for fs in active:
                if hint_text[:10] in fs.description or fs.description[:10] in hint_text:
                    m['foreshadow'].resolve_foreshadowing(pname, fs.id, f"ch{chapter:04d}")
                    break

    m['storage'].update_project_stats(pname)

    console.print(f"\n[bold green]第{chapter}章已保存为最终版，记忆已更新[/bold green]")
    console.print(f"  摘要：{mem.get('summary', '')[:100]}...")
    console.print(f"  事件：{len(mem.get('events', []))} 条")
    console.print(f"  时间线：{len(mem.get('timeline', []))} 条")


# ═══════════════════════════════════════════════════════════════
#  review — 审查章节质量
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--chapter', type=int, required=True, help='章节编号')
@click.option('--auto-fix', is_flag=True, help='自动修复问题')
def review(chapter, auto_fix):
    """审查章节质量"""
    console.print(Panel(f"[bold yellow]审查章节：第{chapter}章[/bold yellow]"))
    config = load_config()
    m = _init_managers(config)
    pname = m['project_name']

    content = m['storage'].load_chapter(chapter)
    if not content:
        console.print(f"[red]错误：未找到第{chapter}章内容[/red]")
        return

    console.print("[cyan]多维度审查...[/cyan]")
    project_data = m['storage'].load_project(pname)

    consistency = m['checker'].check_chapter(chapter, content, project_data)
    quality = m['llm'].review_chapter(content, chapter)

    table = Table(title=f"第{chapter}章审查报告")
    table.add_column("维度", style="cyan")
    table.add_column("状态", style="white")
    table.add_column("说明", style="white")
    table.add_row(
        "一致性",
        "✓ 通过" if consistency['passed'] else "✗ 问题",
        "\n".join(consistency['issues'][:3]) if consistency['issues'] else "无问题"
    )
    table.add_row("质量", f"{quality['score']}/10", quality['summary'])
    console.print(table)

    if auto_fix and not consistency['passed']:
        console.print("[cyan]自动修复...[/cyan]")
        fixed = m['checker'].auto_fix(content, consistency['issues'])
        m['storage'].save_chapter(chapter, fixed, status="draft")
        console.print("[green]✓[/green] 修复后已保存为草稿，运行 save 确认最终版")


# ═══════════════════════════════════════════════════════════════
#  status — 查看项目状态
# ═══════════════════════════════════════════════════════════════

@cli.command()
def status():
    """查看项目状态"""
    console.print(Panel("[bold cyan]项目状态[/bold cyan]"))
    config = load_config()
    m = _init_managers(config)
    pname = m['project_name']

    stats = m['storage'].get_project_stats(pname)
    mem_stats = m['memory'].get_stats()
    chapters = m['storage'].list_chapters()

    table = Table(title="项目统计")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="white")
    table.add_row("项目名称", pname)
    table.add_row("总章节数", str(config['project']['chapters']))
    table.add_row("已完成（final）", str(stats.get('completed_chapters', 0)))
    table.add_row("草稿数", str(len([c for c in chapters if c.get('status') == 'draft'])))
    table.add_row("总字数", f"{stats.get('total_words', 0):,}")
    table.add_row("事实记录", str(mem_stats.get('facts_count', 0)))
    table.add_row("事件流水", str(mem_stats.get('events_count', 0)))
    table.add_row("时间线条目", str(mem_stats.get('timeline_count', 0)))
    table.add_row("角色数", str(mem_stats.get('character_count', 0)))
    console.print(table)

    if chapters:
        console.print("\n[bold]章节列表：[/bold]")
        for ch in chapters[-10:]:  # 最近10章
            status_mark = "✓" if ch.get('status') == 'final' else "○"
            console.print(
                f"  [{status_mark}] 第{ch.get('chapter', '?')}章  "
                f"{ch.get('chapter_name', '')}  "
                f"{ch.get('word_count', 0)}字  "
                f"{ch.get('status', '?')}"
            )


# ═══════════════════════════════════════════════════════════════
#  chapters — 列出所有章节
# ═══════════════════════════════════════════════════════════════

@cli.command()
def chapters():
    """列出所有已保存章节"""
    config = load_config()
    m = _init_managers(config)
    chapter_list = m['storage'].list_chapters()

    if not chapter_list:
        console.print("[yellow]暂无章节[/yellow]")
        return

    table = Table(title="章节列表")
    table.add_column("#", style="cyan", width=6)
    table.add_column("章节名", style="white")
    table.add_column("字数", style="white", justify="right")
    table.add_column("状态", style="white")
    table.add_column("更新时间", style="dim")

    for ch in chapter_list:
        table.add_row(
            str(ch.get('chapter', '')),
            ch.get('chapter_name', ''),
            str(ch.get('word_count', 0)),
            ch.get('status', ''),
            ch.get('updated_at', '')[:19]
        )
    console.print(table)


# ═══════════════════════════════════════════════════════════════
#  query — 搜索记忆
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.argument('query')
def query(query):
    """搜索记忆（事实、摘要、角色）"""
    console.print(Panel(f"[bold magenta]搜索：{query}[/bold magenta]"))
    config = load_config()
    m = _init_managers(config)

    results = m['memory'].search(query)
    if results:
        for i, r in enumerate(results, 1):
            console.print(f"\n[bold]{i}. [{r['type']}] 第{r.get('chapter', '?')}章[/bold]")
            console.print(f"   {r['content'][:200]}")
    else:
        console.print("[yellow]未找到相关信息[/yellow]")


# ═══════════════════════════════════════════════════════════════
#  timeline — 查看时间线
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--start', type=int, default=1, help='起始章节')
@click.option('--end',   type=int, default=9999, help='结束章节')
def timeline(start, end):
    """查看时间线"""
    config = load_config()
    m = _init_managers(config)
    entries = m['memory'].get_timeline(
        list(range(start, end + 1))
    )
    if not entries:
        console.print("[yellow]暂无时间线记录[/yellow]")
        return

    table = Table(title=f"时间线（第{start}-{end}章）")
    table.add_column("章节", style="cyan", width=6)
    table.add_column("时间", style="white")
    table.add_column("事件", style="white")
    table.add_column("地点", style="dim")
    for e in entries:
        table.add_row(
            str(e.get('chapter', '')),
            e.get('time_desc', ''),
            e.get('event', ''),
            e.get('location', '')
        )
    console.print(table)


# ═══════════════════════════════════════════════════════════════
#  characters — 查看角色关系图
# ═══════════════════════════════════════════════════════════════

@cli.command()
def characters():
    """查看角色关系图"""
    config = load_config()
    m = _init_managers(config)
    graph = m['memory'].get_character_graph()

    # 角色表
    chars = graph.get('characters', {})
    if chars:
        table = Table(title="角色出场记录")
        table.add_column("角色", style="cyan")
        table.add_column("首次出场", style="white")
        table.add_column("最近出场", style="white")
        table.add_column("出场章节数", style="white", justify="right")
        for name, info in sorted(chars.items(), key=lambda x: x[1].get('first_appearance', 0)):
            table.add_row(
                name,
                str(info.get('first_appearance', '?')),
                str(info.get('last_appearance', '?')),
                str(len(info.get('appearances', [])))
            )
        console.print(table)

    # 关系表
    rels = graph.get('relationships', {})
    if rels:
        table2 = Table(title="角色关系")
        table2.add_column("从", style="cyan")
        table2.add_column("关系", style="white")
        table2.add_column("到", style="cyan")
        table2.add_column("详情", style="dim")
        for key, rel in rels.items():
            table2.add_row(
                rel.get('from', ''),
                rel.get('relation', ''),
                rel.get('to', ''),
                rel.get('detail', '')[:60]
            )
        console.print(table2)


# ═══════════════════════════════════════════════════════════════
#  events — 查看事件流水
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--start', type=int, default=1, help='起始章节')
@click.option('--end',   type=int, default=9999, help='结束章节')
def events(start, end):
    """查看事件流水"""
    config = load_config()
    m = _init_managers(config)
    ev_list = m['memory'].get_events(list(range(start, end + 1)))

    if not ev_list:
        console.print("[yellow]暂无事件记录[/yellow]")
        return

    table = Table(title=f"事件流水（第{start}-{end}章）")
    table.add_column("章节", style="cyan", width=6)
    table.add_column("类型", style="white")
    table.add_column("事件", style="white")
    table.add_column("角色", style="dim")
    for ev in ev_list:
        table.add_row(
            str(ev.get('chapter', '')),
            ev.get('type', ''),
            ev.get('description', ''),
            ', '.join(ev.get('characters', []))
        )
    console.print(table)


# ═══════════════════════════════════════════════════════════════
#  foreshadowing / connection / transition（保留原有）
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.option('--chapter', type=int, help='查看指定章节的伏笔状态')
def foreshadowing(chapter):
    """查看伏笔状态"""
    console.print(Panel("[bold magenta]伏笔状态[/bold magenta]"))
    config = load_config()
    m = _init_managers(config)
    pname = m['project_name']

    if chapter:
        console.print(f"[cyan]第{chapter}章伏笔状态：[/cyan]")
        status = m['checker'].check_foreshadowing_status(chapter, {'config': {'name': pname}})
        table = Table(title=f"第{chapter}章伏笔统计")
        table.add_column("指标", style="cyan")
        table.add_column("数值", style="white")
        table.add_row("伏笔总数", str(status['foreshadowing_count']))
        table.add_row("已解决",   str(status['resolved_count']))
        table.add_row("待解决",   str(status['pending_count']))
        table.add_row("本章引入", str(status['introduced_this_chapter']))
        table.add_row("本章解决", str(status['resolved_this_chapter']))
        console.print(table)
        if status.get('unresolved_old'):
            console.print("\n[yellow]长期未解决伏笔：[/yellow]")
            for fs in status['unresolved_old']:
                console.print(f"  - {fs['id']}: {fs['description'][:50]}... (等待{fs['chapters_pending']}章)")
    else:
        summary = m['foreshadow'].get_foreshadowing_summary(pname)
        table = Table(title="伏笔统计")
        table.add_column("指标", style="cyan")
        table.add_column("数值", style="white")
        table.add_row("伏笔总数", str(summary['total']))
        table.add_row("活跃伏笔", str(summary['active']))
        table.add_row("已解决",   str(summary['resolved']))
        console.print(table)
        active = m['foreshadow'].get_active_foreshadowing(pname)
        if active:
            console.print("\n[bold]活跃伏笔：[/bold]")
            for fs in active:
                console.print(f"  [cyan]{fs.id}[/cyan]: {fs.description[:80]}...  (引入于第{fs.introduced_in}章)")


@cli.command()
@click.option('--start', type=int, default=1)
@click.option('--end',   type=int, default=10)
def connection(start, end):
    """查看章节衔接状态"""
    console.print(Panel(f"[bold blue]章节衔接（第{start}-{end}章）[/bold blue]"))
    config = load_config()
    m = _init_managers(config)
    report = m['connection'].generate_connection_report(m['project_name'], start, end)
    console.print(report)


@cli.command()
@click.argument('chapter', type=int)
def transition(chapter):
    """查看章节过渡提示"""
    console.print(Panel(f"[bold green]第{chapter}章过渡提示[/bold green]"))
    config = load_config()
    m = _init_managers(config)
    prompt = m['connection'].generate_chapter_transition_prompt(m['project_name'], chapter)
    console.print(prompt)


@cli.command()
def import_data():
    """导入现有设定数据"""
    console.print(Panel("[bold green]导入设定数据[/bold green]"))
    current_dir = Path.cwd()
    files_to_import = {
        '全书大纲.txt': 'outline/',
        '角色档案.txt': 'characters/',
        '故事圣经.txt': 'world/',
        '伏笔.txt': 'world/foreshadowing.txt'
    }
    console.print(f"[cyan]扫描目录：{current_dir}[/cyan]")
    imported = []
    for filename, target_dir in files_to_import.items():
        if (current_dir / filename).exists():
            imported.append((filename, target_dir))
            console.print(f"  [green]✓[/green] 找到：{filename}")
    if not imported:
        console.print("[yellow]未找到可导入的文件[/yellow]")
        return
    console.print(f"\n[bold]将导入 {len(imported)} 个文件[/bold]")
    console.print("[yellow]导入功能需要进一步实现[/yellow]")


if __name__ == '__main__':
    cli()
