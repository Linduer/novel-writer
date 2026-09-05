#!/usr/bin/env python3
"""
使用示例

展示如何使用长篇小说写作助手
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.storage import StorageManager
from core.memory import MemoryManager
from core.context import ContextEngine
from core.llm import LLMManager
from core.checker import ConsistencyChecker
import yaml

def load_config():
    """加载配置文件"""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        print("错误：未找到config.yaml配置文件")
        print("请先复制config.example.yaml为config.yaml并填入配置")
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def demo_storage():
    """演示存储管理"""
    print("=" * 60)
    print("1. 存储管理演示")
    print("=" * 60)
    
    config = load_config()
    if not config:
        return
    
    storage = StorageManager(config)
    
    # 列出所有项目
    projects = storage.list_projects()
    print(f"找到 {len(projects)} 个项目：")
    for project in projects:
        print(f"  - {project}")
    
    # 加载项目数据
    if projects:
        project_name = projects[0]
        print(f"\n加载项目：{project_name}")
        try:
            project_data = storage.load_project(project_name)
            print(f"  大纲：{len(project_data.get('outline', []))} 个文件")
            print(f"  角色：{len(project_data.get('characters', []))} 个文件")
            print(f"  世界观：{len(project_data.get('world', {}))} 个文件")
        except Exception as e:
            print(f"  加载失败：{e}")

def demo_memory():
    """演示记忆系统"""
    print("\n" + "=" * 60)
    print("2. 记忆系统演示")
    print("=" * 60)
    
    config = load_config()
    if not config:
        return
    
    memory = MemoryManager(config)
    
    # 获取统计信息
    projects = StorageManager(config).list_projects()
    if projects:
        project_name = projects[0]
        stats = memory.get_stats(project_name)
        print(f"项目：{project_name}")
        print(f"  事实记录：{stats.get('facts_count', 0)} 条")
        print(f"  摘要数量：{stats.get('summaries_count', 0)} 个")
        print(f"  向量索引：{stats.get('vector_size', 0)} 条")

def demo_context():
    """演示上下文引擎"""
    print("\n" + "=" * 60)
    print("3. 上下文引擎演示")
    print("=" * 60)
    
    config = load_config()
    if not config:
        return
    
    storage = StorageManager(config)
    context_engine = ContextEngine(config)
    
    # 加载项目
    projects = storage.list_projects()
    if projects:
        project_name = projects[0]
        project_data = storage.load_project(project_name)
        
        # 构建上下文
        print(f"为项目 {project_name} 构建第1章的上下文")
        context = context_engine.build_writing_context(project_data, chapter=1)
        
        print(f"  章节：{context['chapter']}")
        print(f"  卷：{context['volume']}")
        print(f"  Token预算：{context['token_budget']}")
        
        # 格式化上下文
        formatted = context_engine.format_context_for_llm(context)
        print(f"  上下文长度：{len(formatted)} 字符")

def demo_consistency():
    """演示一致性检查"""
    print("\n" + "=" * 60)
    print("4. 一致性检查演示")
    print("=" * 60)
    
    config = load_config()
    if not config:
        return
    
    storage = StorageManager(config)
    checker = ConsistencyChecker(config)
    
    # 加载项目
    projects = storage.list_projects()
    if projects:
        project_name = projects[0]
        project_data = storage.load_project(project_name)
        
        # 检查示例内容
        sample_content = """
        沈浮站在木筏上，看着远处的乐园。他想起了爷爷的话："看好池子。"
        中枢的声音响起："叮！检测到新游客入园，当前信仰值+1。"
        小鲲从造浪池里探出头来，张开嘴等待投喂。
        """
        
        print("检查示例内容的一致性...")
        result = checker.check_chapter(1, sample_content, project_data)
        
        print(f"  检查结果：{'通过' if result['passed'] else '未通过'}")
        if result['issues']:
            print(f"  发现问题：{len(result['issues'])} 个")
            for issue in result['issues'][:3]:
                print(f"    - {issue}")

def main():
    """主函数"""
    print("长篇小说写作助手 - 使用示例")
    print("=" * 60)
    
    # 检查配置
    if not load_config():
        print("\n请先配置config.yaml文件")
        print("步骤：")
        print("1. 复制config.example.yaml为config.yaml")
        print("2. 填入GLM API密钥")
        print("3. 运行此脚本")
        return
    
    # 运行演示
    demo_storage()
    demo_memory()
    demo_context()
    demo_consistency()
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n下一步：")
    print("1. 配置config.yaml中的GLM API密钥")
    print("2. 运行 python main.py write --chapter 1 开始写作")
    print("3. 运行 python main.py review --chapter 1 审查章节")
    print("4. 运行 python main.py status 查看项目状态")

if __name__ == '__main__':
    main()