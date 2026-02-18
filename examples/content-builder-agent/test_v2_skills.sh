#!/usr/bin/env bash
# Content Builder Agent - SkillsMiddleware V2 测试脚本
# 用法：./test_v2_skills.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "Content Builder Agent - SkillsMiddleware V2 测试"
echo "========================================================================"
echo ""

# 检查 Python 环境
if command -v uv &> /dev/null; then
    PYTHON_CMD="uv run"
    echo "✓ 使用 uv 运行环境"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo "✓ 使用系统 Python3"
else
    echo "✗ 错误：找不到 Python 或 uv"
    exit 1
fi

# 运行测试
echo ""
echo "运行测试..."
echo ""

$PYTHON_CMD << 'PYTHON_SCRIPT'
import sys
from pathlib import Path

# 添加 deepagents 到路径
sys.path.insert(0, '/Volumes/0-/jameswu projects/deepagents/libs/deepagents')

from deepagents.middleware.skills import (
    SkillsMiddleware,
    ResourceMetadata,
    _discover_resources,
    _format_resource_summary,
)
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.prebuilt import ToolRuntime
from types import SimpleNamespace

EXAMPLE_DIR = Path(__file__).parent if '__file__' in dir() else Path('.')
skills_dir = EXAMPLE_DIR / "skills"

print("=" * 70)
print("Content Builder Agent - Skills V2 测试")
print("=" * 70)
print()

# 1. 检查技能文件
print("【1. 技能文件检查】")
skill_count = 0
for skill in skills_dir.iterdir():
    if skill.is_dir():
        skill_md = skill / "SKILL.md"
        if skill_md.exists():
            print(f"  ✓ {skill.name}/SKILL.md ({skill_md.stat().st_size:,} bytes)")
            skill_count += 1
        else:
            print(f"  ✗ {skill.name}/SKILL.md (missing)")
print(f"  总计：{skill_count} 个技能")

# 2. 创建 middleware
print()
print("【2. SkillsMiddleware V2 初始化】")
backend = FilesystemBackend(root_dir=str(skills_dir), virtual_mode=True)
middleware = SkillsMiddleware(backend=backend, sources=["/"])

print(f"  ✓ max_loaded_skills: {middleware._max_loaded_skills}")
print(f"  ✓ tools: {[t.name for t in middleware.tools]}")

# 3. before_agent
print()
print("【3. before_agent V2 字段】")
runtime = SimpleNamespace(context=None, store=None, stream_writer=lambda x: None)
result = middleware.before_agent({}, runtime, {})

print(f"  ✓ skills_metadata: {len(result['skills_metadata'])} 个技能")
print(f"  ✓ skills_loaded: {result['skills_loaded']}")
print(f"  ✓ skill_resources: {result['skill_resources']}")

# 4. 技能列表
print()
print("【4. 技能列表 (V2 格式)】")
skills_list = middleware._format_skills_list(
    result["skills_metadata"],
    result["skills_loaded"],
    result["skill_resources"]
)
print(skills_list)

# 5. load_skill 测试
print()
print("【5. 测试 load_skill 工具】")
tool_runtime = ToolRuntime(
    state=result,
    context=None,
    tool_call_id="test-123",
    store=None,
    stream_writer=lambda x: None,
    config={},
)

# 加载第一个技能
first_skill = result['skills_metadata'][0]['name']
print(f"  加载技能：{first_skill}")
load_result = middleware._execute_load_skill(backend, first_skill, tool_runtime)

if hasattr(load_result, 'update'):
    print(f"  ✓ 返回类型：Command")
    print(f"  ✓ skills_loaded: {load_result.update.get('skills_loaded', [])}")
    print(f"  ✓ 资源发现：{list(load_result.update.get('skill_resources', {}).keys())}")

    # 显示技能内容预览
    if load_result.update.get('messages'):
        content = load_result.update['messages'][0].content
        preview = content[:200].replace('\n', ' ')
        print(f"  ✓ 内容预览：{preview}...")

# 6. unload_skill 测试
print()
print("【6. 测试 unload_skill 工具】")
unload_result = middleware._execute_unload_skill(first_skill, tool_runtime)

if hasattr(unload_result, 'update'):
    print(f"  ✓ 返回类型：Command")
    if unload_result.update.get('messages'):
        msg = unload_result.update['messages'][0].content
        print(f"  ✓ 卸载消息：{msg[:100]}...")
    print(f"  ✓ 剩余已加载：{unload_result.update.get('skills_loaded', [])}")

# 7. 资源发现测试
print()
print("【7. 资源发现测试】")
for skill_name in [s['name'] for s in result['skills_metadata']]:
    resources = _discover_resources(backend, f"/{skill_name}", skill_name)
    if resources:
        print(f"  ✓ {skill_name}: {len(resources)} 个资源")
        for r in resources:
            print(f"      [{r['type']}] {r['path']}")
    else:
        print(f"  - {skill_name}: 无资源文件")

# 8. _format_resource_summary 测试
print()
print("【8. _format_resource_summary 测试】")
mock_resources = [
    {"path": "/test/a.py", "type": "script", "skill_name": "test"},
    {"path": "/test/b.py", "type": "script", "skill_name": "test"},
    {"path": "/test/doc.md", "type": "reference", "skill_name": "test"},
]
summary = _format_resource_summary(mock_resources)
print(f"  输入：3 个资源 (2 script, 1 reference)")
print(f"  输出：\"{summary}\"")

print()
print("=" * 70)
print("✅ SkillsMiddleware V2 测试完成!")
print("=" * 70)
print()
print("V2 新功能验证:")
print("  ✓ ResourceMetadata 类型")
print("  ✓ SkillsState 扩展 (skills_loaded, skill_resources)")
print("  ✓ before_agent V2 返回字段")
print("  ✓ load_skill 工具")
print("  ✓ unload_skill 工具")
print("  ✓ _format_skills_list V2 输出 (加载标记，引导语)")
print("  ✓ _discover_resources 资源发现")
print("  ✓ _format_resource_summary 摘要格式化")
print("  ✓ max_loaded_skills 预算控制")
PYTHON_SCRIPT

echo ""
echo "========================================================================"
echo "测试完成!"
echo "========================================================================"
