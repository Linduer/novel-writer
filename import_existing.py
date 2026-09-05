#!/usr/bin/env python3
"""
导入现有小说材料

将已有的大纲、角色、世界观等材料导入到项目中
"""

import os
import shutil
from pathlib import Path
import yaml

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print("错误：未找到config.yaml配置文件")
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def import_materials(project_name: str):
    """导入现有材料"""
    config = load_config()
    if not config:
        return
    
    # 项目目录
    project_dir = Path(config['storage']['data_dir']) / project_name
    
    # 确保项目目录存在
    if not project_dir.exists():
        print(f"项目目录不存在：{project_dir}")
        return
    
    # 定义要导入的文件
    files_to_import = {
        '全书大纲.txt': 'outline/',
        '角色档案.txt': 'characters/',
        '故事圣经.txt': 'world/',
        '伏笔.txt': 'world/foreshadowing.txt'
    }
    
    print(f"开始导入材料到项目：{project_name}")
    print("-" * 50)
    
    imported_count = 0
    
    for filename, target_path in files_to_import.items():
        source_file = Path.cwd() / filename
        
        if source_file.exists():
            target_file = project_dir / target_path
            target_file.mkdir(parents=True, exist_ok=True)
            
            # 处理目标路径
            if target_path.endswith('/'):
                target_file = target_file / filename
            else:
                target_file = project_dir / target_path
            
            # 复制文件
            shutil.copy2(source_file, target_file)
            print(f"✓ 导入：{filename} -> {target_path}")
            imported_count += 1
        else:
            print(f"✗ 未找到：{filename}")
    
    print("-" * 50)
    print(f"导入完成：{imported_count} 个文件")
    
    # 显示项目结构
    print("\n项目结构：")
    for root, dirs, files in os.walk(project_dir):
        level = root.replace(str(project_dir), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")

def create_sample_project():
    """创建示例项目"""
    config = load_config()
    if not config:
        return
    
    project_name = "全民海上求生示例"
    project_dir = Path(config['storage']['data_dir']) / project_name
    
    # 创建目录结构
    directories = [
        'outline',
        'characters',
        'world',
        'chapters/drafts',
        'chapters/final',
        'memory/facts',
        'memory/summaries',
        'memory/vectors'
    ]
    
    for dir_name in directories:
        dir_path = project_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
    
    print(f"已创建示例项目：{project_dir}")
    
    # 创建示例文件
    sample_outline = """# 全书大纲示例

## 卷一：开业大吉
- 章节1-96
- 主要内容：洪水之夜招牌漂流、中枢觉醒
- 关键角色：沈浮、乐园中枢
- 重要事件：新手三捞验货、收拢流民

## 卷二：千帆海域
- 章节97-192
- 主要内容：程霜携查封令登岛、义盟三派博弈
- 关键角色：程霜、卫崇仓
- 重要事件：二期开工、小鲲出壳
"""
    
    sample_character = """# 沈浮 - 主角

## 基本信息
- 身份：前"疯狂水世界"乐园园长
- 年龄：二十五六岁
- 性格：嘴贫心硬，报恩当场报，报仇也当场报

## 关键特征
- 对"乐园"二字有信仰级的执念
- 报价式吐槽，万物可折成票价
- 提爷爷就闭嘴，转去巡园

## 当前状态
- 开局一块木筏一块招牌一个瓶子
- 终局新大陆免票的园长
"""
    
    sample_world = """# 世界观设定

## 基本背景
- 大洪水吞没大陆
- 公认说法：冰川融化
- 真相：归墟封印渗漏，渊以四海之水作攻城锤

## 力量体系
- 滴水境
- 溪流境
- 江河境
- 湖泽境
- 沧海境
- 归墟境

## 核心设定
- 乐园中枢：金手指本体
- 打捞网：园长专属
- 信仰值：唯一高级货币
- 设施即神通
"""
    
    # 写入示例文件
    with open(project_dir / 'outline' / '全书大纲示例.txt', 'w', encoding='utf-8') as f:
        f.write(sample_outline)
    
    with open(project_dir / 'characters' / '沈浮.txt', 'w', encoding='utf-8') as f:
        f.write(sample_character)
    
    with open(project_dir / 'world' / '世界观设定.txt', 'w', encoding='utf-8') as f:
        f.write(sample_world)
    
    print("已创建示例文件")

if __name__ == '__main__':
    print("长篇小说写作助手 - 材料导入工具")
    print("=" * 50)
    
    choice = input("请选择操作：\n1. 导入现有材料\n2. 创建示例项目\n请输入选择（1/2）：")
    
    if choice == '1':
        project_name = input("请输入项目名称：")
        import_materials(project_name)
    elif choice == '2':
        create_sample_project()
    else:
        print("无效选择")