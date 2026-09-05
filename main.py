#!/usr/bin/env python3
"""
长篇小说写作助手 - 主程序入口

基于GLM5.2/5.3的超长小说上下文管理系统
"""

import os
import sys
import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.storage import StorageManager
from core.memory import MemoryManager
from core.context import ContextEngine
from core.llm import LLMManager
from core.checker import ConsistencyChecker

console = Console()

def load_config():
    """加载配置文件"""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        console.print("[red]错误：未找到config.yaml配置文件[/red]")
        console.print("请复制config.example.yaml为config.yaml并填入配置")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """长篇小说写作助手 - 基于GLM的超长小说上下文管理系统"""
    pass

@cli.command()
@click.option('--name', prompt='项目名称', help='小说项目名称')
@click.option('--template', default='default', help='项目模板')
def init(name, template):
    """初始化新的小说项目"""
    console.print(Panel(f"[bold green]初始化项目：{name}[/bold green]"))
    
    config = load_config()
    storage = StorageManager(config)
    
    # 创建项目目录结构
    project_dir = storage.create_project(name)
    
    console.print(f"[green]✓[/green] 项目目录已创建：{project_dir}")
    
    # 显示目录结构
    table = Table(title="项目结构")
    table.add_column("目录", style="cyan")
    table.add_column("说明", style="white")
    
    table.add_row("outline/", "大纲文件")
    table.add_row("characters/", "角色档案")
    table.add_row("world/", "世界观设定")
    table.add_row("chapters/", "章节正文")
    table.add_row("memory/", "记忆数据")
    
    console.print(table)
    console.print("\n[bold]下一步操作：[/bold]")
    console.print("1. 将大纲文件放入 outline/ 目录")
    console.print("2. 将角色档案放入 characters/ 目录")
    console.print("3. 将世界观设定放入 world/ 目录")
    console.print("4. 运行 python main.py import 导入设定")

@cli.command()
@click.option('--chapter', type=int, required=True, help='章节编号')
@click.option('--volume', type=int, help='卷编号（可选）')
def write(chapter, volume):
    """写指定章节"""
    console.print(Panel(f"[bold blue]写作章节：第{chapter}章[/bold blue]"))
    
    config = load_config()
    
    # 初始化各个管理器
    storage = StorageManager(config)
    memory = MemoryManager(config)
    context = ContextEngine(config)
    llm = LLMManager(config)
    checker = ConsistencyChecker(config)
    
    # 1. 加载项目数据
    project_name = config['project']['name']
    project_data = storage.load_project(project_name)
    
    # 2. 构建上下文
    console.print("[cyan]正在构建写作上下文...[/cyan]")
    writing_context = context.build_writing_context(
        project_data=project_data,
        chapter=chapter,
        volume=volume
    )
    
    # 3. 生成草稿
    console.print("[cyan]正在生成章节草稿...[/cyan]")
    draft = llm.generate_chapter(
        context=writing_context,
        chapter=chapter,
        volume=volume
    )
    
    # 4. 保存草稿
    draft_path = storage.save_draft(project_name, chapter, draft)
    console.print(f"[green]✓[/green] 草稿已保存：{draft_path}")
    
    # 5. 一致性检查
    console.print("[cyan]正在进行一致性检查...[/cyan]")
    check_result = checker.check_chapter(
        chapter=chapter,
        draft=draft,
        project_data=project_data
    )
    
    if check_result['passed']:
        console.print("[green]✓[/green] 一致性检查通过")
    else:
        console.print("[yellow]⚠[/yellow] 发现一致性问题：")
        for issue in check_result['issues']:
            console.print(f"  - {issue}")
    
    # 6. 提取事实并更新记忆
    console.print("[cyan]正在提取事实并更新记忆...[/cyan]")
    facts = llm.extract_facts(draft, writing_context)
    memory.update_facts(project_name, chapter, facts)
    
    console.print(f"\n[bold green]第{chapter}章写作完成！[/bold green]")

@cli.command()
@click.option('--chapter', type=int, required=True, help='章节编号')
@click.option('--auto-fix', is_flag=True, help='自动修复问题')
def review(chapter, auto_fix):
    """审查章节质量"""
    console.print(Panel(f"[bold yellow]审查章节：第{chapter}章[/bold yellow]"))
    
    config = load_config()
    storage = StorageManager(config)
    llm = LLMManager(config)
    checker = ConsistencyChecker(config)
    
    project_name = config['project']['name']
    
    # 加载章节
    chapter_content = storage.load_chapter(project_name, chapter)
    if not chapter_content:
        console.print(f"[red]错误：未找到第{chapter}章内容[/red]")
        return
    
    # 多维度审查
    console.print("[cyan]正在进行多维度审查...[/cyan]")
    
    # 1. 一致性检查
    consistency_result = checker.check_chapter(
        chapter=chapter,
        draft=chapter_content,
        project_data=storage.load_project(project_name)
    )
    
    # 2. AI质量审查
    quality_result = llm.review_chapter(chapter_content, chapter)
    
    # 显示审查结果
    table = Table(title=f"第{chapter}章审查报告")
    table.add_column("维度", style="cyan")
    table.add_column("状态", style="white")
    table.add_column("说明", style="white")
    
    # 一致性检查
    table.add_row(
        "一致性",
        "✓ 通过" if consistency_result['passed'] else "✗ 问题",
        "\n".join(consistency_result['issues'][:3]) if consistency_result['issues'] else "无问题"
    )
    
    # 质量检查
    table.add_row(
        "质量",
        f"评分：{quality_result['score']}/10",
        quality_result['summary']
    )
    
    console.print(table)
    
    if auto_fix and not consistency_result['passed']:
        console.print("[cyan]正在自动修复一致性问题...[/cyan]")
        fixed_content = checker.auto_fix(chapter_content, consistency_result['issues'])
        storage.save_reviewed_chapter(project_name, chapter, fixed_content)
        console.print("[green]✓[/green] 已保存修复后的版本")

@cli.command()
@click.argument('query')
@click.option('--type', 'query_type', type=click.Choice(['character', 'plot', 'setting']), 
              default='plot', help='查询类型')
def query(query, query_type):
    """查询项目信息"""
    console.print(Panel(f"[bold magenta]查询：{query}[/bold magenta]"))
    
    config = load_config()
    storage = StorageManager(config)
    memory = MemoryManager(config)
    
    project_name = config['project']['name']
    
    # 执行查询
    results = memory.search(project_name, query, query_type)
    
    if results:
        for i, result in enumerate(results, 1):
            console.print(f"\n[bold]{i}. {result['title']}[/bold]")
            console.print(f"   类型：{result['type']}")
            console.print(f"   内容：{result['content'][:200]}...")
    else:
        console.print("[yellow]未找到相关信息[/yellow]")

@cli.command()
def status():
    """查看项目状态"""
    console.print(Panel("[bold cyan]项目状态[/bold cyan]"))
    
    config = load_config()
    storage = StorageManager(config)
    memory = MemoryManager(config)
    
    project_name = config['project']['name']
    
    # 获取项目统计
    stats = storage.get_project_stats(project_name)
    memory_stats = memory.get_stats(project_name)
    
    # 显示统计信息
    table = Table(title="项目统计")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="white")
    
    table.add_row("项目名称", project_name)
    table.add_row("总章节数", str(config['project']['chapters']))
    table.add_row("已完成章节", str(stats.get('completed_chapters', 0)))
    table.add_row("总字数", f"{stats.get('total_words', 0):,}")
    table.add_row("事实记录数", str(memory_stats.get('facts_count', 0)))
    table.add_row("向量索引大小", f"{memory_stats.get('vector_size', 0):,} 条")
    
    console.print(table)

@cli.command()
def import_data():
    """导入现有设定数据"""
    console.print(Panel("[bold green]导入设定数据[/bold green]"))
    
    # 检查当前目录的文件
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
        source_file = current_dir / filename
        if source_file.exists():
            imported.append((filename, target_dir))
            console.print(f"  [green]✓[/green] 找到：{filename}")
    
    if not imported:
        console.print("[yellow]未找到可导入的文件[/yellow]")
        return
    
    console.print(f"\n[bold]将导入 {len(imported)} 个文件[/bold]")
    
    # 这里需要实现实际的导入逻辑
    console.print("[yellow]导入功能需要进一步实现[/yellow]")

if __name__ == '__main__':
    cli()