"""
一致性检查模块测试脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.checker import ConsistencyChecker


def test_checker():
    """测试一致性检查器"""
    print("=" * 60)
    print("一致性检查模块测试")
    print("=" * 60)

    # 配置
    config = {
        'storage': {
            'data_dir': './data/{project}',
        },
        'data_dir': './data/{project}',
        'project': {
            'chapters': 960
        },
        'consistency': {}
    }
    project_name = '全民海上求生'

    # 初始化检查器
    print("\n1. 初始化检查器...")
    checker = ConsistencyChecker(config, project_name)
    print("   [OK] 检查器初始化成功")

    # 测试章节内容
    test_chapter = 1
    test_draft = """
    开业第三天，世界没了。

    八百万贷款与爷爷"看好池子"、暴雨三夜、逆人流拆招牌、洪水灌园、漂流两日、光头按头、招牌发烫沉海、五个大字在水底一个个亮起，金光炸开。

    沈浮抱着招牌漂了一夜，水很冷，但他不敢松手。这是爷爷留下的唯一东西，也是疯狂水世界的招牌。

    "叮！乐园播报：您的乐园已停业九小时，建议尽快恢复营业。"

    中枢的声音在脑海里响起，沈浮苦笑："营业？这水都淹到脖子了，你还想着营业？"

    "营业是本中枢的核心使命。其他问题不在服务范围内。"

    沈浮翻了个白眼，继续划水。远处，光头按着他的头往水里按，想抢走招牌。

    "小子，把招牌交出来，饶你一命。"

    沈浮没说话，只是把招牌抱得更紧了。爷爷说过，招牌在，乐园就在。

    光头见他不配合，加大了力气。就在沈浮快要憋不住的时候，招牌突然发烫，五个大字在水底一个个亮起——"疯狂水世界"。

    金光炸开，光头松手逃命。沈浮被招牌托出海面，钢架金纹流转如通电。

    "叮！中枢觉醒，绑定完成。乐园评级'无'，设施零，游客零。您的乐园已停业九小时，建议尽快恢复营业。"

    沈浮看着手中的招牌，又看了看四周的汪洋大海，深吸一口气："好吧，那就从零开始。"

    当务之急不是乐园，是水。他需要淡水，需要食物，需要一个落脚的地方。

    远处，一块门板漂了过来，上面趴着个两米高的东西...
    """

    print(f"\n2. 测试第{test_chapter}章...")
    result = checker.check_chapter(test_chapter, test_draft)

    print(f"   检查结果：{'[PASS]' if result['passed'] else '[FAIL]'}")
    print(f"   总问题数：{result['summary']['total']}")
    print(f"   错误：{result['summary']['errors']}")
    print(f"   警告：{result['summary']['warnings']}")
    print(f"   信息：{result['summary']['infos']}")

    # 生成报告
    print("\n3. 生成检查报告...")
    report = checker.generate_report(test_chapter, result)
    print(report)

    # 测试章节进度
    print("\n4. 检查章节进度...")
    progression = checker.check_chapter_progression(test_chapter)
    print(f"   章节：{progression['chapter']}")
    print(f"   预期卷：{progression['expected_volume']}")
    print(f"   完成度：{progression['completion_percentage']}%")

    # 测试伏笔状态
    print("\n5. 检查伏笔状态...")
    foreshadowing = checker.check_foreshadowing_status(test_chapter)
    print(f"   伏笔总数：{foreshadowing['foreshadowing_count']}")
    print(f"   已解决：{foreshadowing['resolved_count']}")
    print(f"   待解决：{foreshadowing['pending_count']}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == '__main__':
    test_checker()
