"""
LLM管理模块

负责GLM API的调用和管理
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from openai import OpenAI

class LLMManager:
    """LLM管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.llm_config = config['llm']
        
        # 初始化GLM客户端
        self.writer_client = self._create_client('writer')
        self.archivist_client = self._create_client('archivist')
        self.reviewer_client = self._create_client('reviewer')
    
    def _create_client(self, role: str) -> OpenAI:
        """创建GLM客户端"""
        role_config = self.llm_config.get(role, {})
        
        api_key = role_config.get('api_key', os.getenv('GLM_API_KEY'))
        api_base = role_config.get('api_base', 'https://open.bigmodel.cn/api/paas/v4')
        
        if not api_key:
            raise ValueError(f"未找到{role}角色的API密钥")
        
        return OpenAI(
            api_key=api_key,
            base_url=api_base
        )
    
    def generate_chapter(self, context: Dict, chapter: int, 
                        volume: Optional[int] = None) -> str:
        """生成章节内容"""
        # 构建提示词
        prompt = self._build_chapter_prompt(context, chapter, volume)
        
        # 调用GLM生成
        response = self.writer_client.chat.completions.create(
            model=self.llm_config['writer']['model'],
            messages=[
                {"role": "system", "content": self._get_writer_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=self.llm_config['writer']['temperature'],
            max_tokens=self.llm_config['writer']['max_tokens']
        )
        
        return response.choices[0].message.content
    
    def _build_chapter_prompt(self, context: Dict, chapter: int, 
                            volume: Optional[int] = None) -> str:
        """构建章节生成提示词"""
        if volume is None:
            volume = (chapter - 1) // 96 + 1
        
        prompt_parts = [
            f"请根据以下信息创作第{chapter}章（第{volume}卷）的内容。",
            f"要求：每章1000-1500字，保持角色性格一致，遵循世界观设定。",
            "",
            "## 上下文信息",
            context.get('formatted_context', ''),
            "",
            "## 创作要求",
            "1. 开头要有吸引力",
            "2. 中间要有冲突和推进",
            "3. 结尾要留有悬念",
            "4. 保持轻快、嘴碎、理直气壮的荒诞风格",
            "5. 爽点当天结算，绝不过夜"
        ]
        
        return "\n".join(prompt_parts)
    
    def _get_writer_system_prompt(self) -> str:
        """获取写手系统提示词"""
        return """你是一位专业的网络小说作家，擅长创作轻喜剧风格的玄幻小说。

你的写作风格特点：
1. 轻快、嘴碎、理直气壮的荒诞
2. 惨是垫场，嗨是正片
3. 笑点来自处境反差和档案乱码的毒舌
4. 爽点当天结算，绝不过夜
5. 章尾必留钩，每章末尾吊住下一章

你需要遵循的规则：
1. 每章1000-1500字
2. 保持角色性格一致
3. 遵循世界观设定
4. 按照大纲推进剧情
5. 不使用原作人名与商标词
6. 不写'命运的齿轮开始转动'
7. 不写'这一刻，他终于明白了'"""
    
    def extract_facts(self, chapter_content: str, context: Dict) -> List[Dict]:
        """从章节内容中提取事实"""
        prompt = f"""请从以下章节内容中提取关键事实，包括：

1. 角色状态变化（位置、能力、关系等）
2. 新出现的角色或物品
3. 重要事件或情节发展
4. 伏笔或悬念
5. 时间线推进

章节内容：
{chapter_content[:2000]}  # 限制长度

请以JSON格式输出提取的事实，格式如下：
[
  {{
    "content": "事实描述",
    "type": "event/character/item/foreshadowing/timeline",
    "entities": ["相关实体"],
    "importance": "high/medium/low"
  }}
]"""
        
        response = self.archivist_client.chat.completions.create(
            model=self.llm_config['archivist']['model'],
            messages=[
                {"role": "system", "content": "你是一位专业的故事分析员，擅长从小说内容中提取关键事实。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.llm_config['archivist']['temperature'],
            max_tokens=self.llm_config['archivist']['max_tokens']
        )
        
        try:
            # 解析JSON响应
            facts_text = response.choices[0].message.content
            # 尝试提取JSON部分
            if "```json" in facts_text:
                facts_text = facts_text.split("```json")[1].split("```")[0]
            elif "[" in facts_text:
                start = facts_text.index("[")
                end = facts_text.rindex("]") + 1
                facts_text = facts_text[start:end]
            
            import json
            facts = json.loads(facts_text)
            return facts if isinstance(facts, list) else []
        except Exception as e:
            print(f"解析事实提取结果失败：{e}")
            return []
    
    def generate_summary(self, chapter_content: str, chapter: int) -> str:
        """生成章节摘要"""
        prompt = f"""请为以下章节内容生成简洁的摘要（200字以内）：

章节内容：
{chapter_content[:2000]}

要求：
1. 概括主要情节发展
2. 记录关键角色行动
3. 提及重要物品或事件
4. 保持客观中立"""
        
        response = self.archivist_client.chat.completions.create(
            model=self.llm_config['archivist']['model'],
            messages=[
                {"role": "system", "content": "你是一位专业的故事摘要员，擅长生成简洁准确的章节摘要。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.llm_config['archivist']['temperature'],
            max_tokens=300
        )
        
        return response.choices[0].message.content
    
    def review_chapter(self, chapter_content: str, chapter: int) -> Dict:
        """审查章节质量"""
        prompt = f"""请从以下维度审查章节质量：

1. 情节连贯性（是否与前文衔接）
2. 角色一致性（性格、能力是否符合设定）
3. 世界观一致性（是否符合设定规则）
4. 节奏把控（是否有张有弛）
5. 文笔质量（是否流畅、有特色）
6. 钩子设计（结尾是否有吸引力）
7. 字数控制（是否在1000-1500字）

章节内容：
{chapter_content[:2000]}

请给出评分（1-10分）和具体评价。"""
        
        response = self.reviewer_client.chat.completions.create(
            model=self.llm_config['reviewer']['model'],
            messages=[
                {"role": "system", "content": "你是一位专业的小说编辑，擅长从多个维度评估章节质量。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.llm_config['reviewer']['temperature'],
            max_tokens=self.llm_config['reviewer']['max_tokens']
        )
        
        review_text = response.choices[0].message.content
        
        # 简单解析评分
        score = 7  # 默认评分
        if "评分：" in review_text:
            try:
                score_text = review_text.split("评分：")[1].split("/")[0].strip()
                score = int(score_text)
            except:
                pass
        
        return {
            'score': score,
            'summary': review_text[:500],
            'full_review': review_text
        }
    
    def check_consistency(self, chapter_content: str, context: Dict, 
                         chapter: int) -> Dict:
        """检查一致性"""
        prompt = f"""请检查以下章节内容的一致性问题：

1. 角色行为是否符合性格设定
2. 能力使用是否符合力量体系
3. 时间线是否合理
4. 地点描述是否一致
5. 物品状态是否连贯

章节内容：
{chapter_content[:2000]}

上下文信息：
{context.get('formatted_context', '')[:1000]}

请列出发现的一致性问题，如果没有问题则说明"一致性检查通过"。"""
        
        response = self.reviewer_client.chat.completions.create(
            model=self.llm_config['reviewer']['model'],
            messages=[
                {"role": "system", "content": "你是一位专业的一致性检查员，擅长发现小说中的逻辑漏洞。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.llm_config['reviewer']['temperature'],
            max_tokens=self.llm_config['reviewer']['max_tokens']
        )
        
        check_text = response.choices[0].message.content
        
        # 简单解析结果
        passed = "一致性检查通过" in check_text
        issues = []
        
        if not passed:
            # 尝试提取问题列表
            lines = check_text.split("\n")
            for line in lines:
                if line.strip() and ("问题" in line or "不一致" in line or "错误" in line):
                    issues.append(line.strip())
        
        return {
            'passed': passed,
            'issues': issues,
            'full_report': check_text
        }
    
    def rewrite_section(self, section_content: str, instruction: str) -> str:
        """重写指定段落"""
        prompt = f"""请根据以下指令重写段落：

原始内容：
{section_content}

重写指令：
{instruction}

要求：
1. 保持与上下文风格一致
2. 执行重写指令
3. 保持字数相近"""
        
        response = self.writer_client.chat.completions.create(
            model=self.llm_config['writer']['model'],
            messages=[
                {"role": "system", "content": "你是一位专业的改稿编辑，擅长根据指令重写段落。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.llm_config['writer']['temperature'],
            max_tokens=self.llm_config['writer']['max_tokens']
        )
        
        return response.choices[0].message.content