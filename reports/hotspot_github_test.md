# Daily Research Intelligence - single-cell, foundation model, perturbation prediction

共 3 条

1. **LiudengZhang/fm-to-virtual-cells**
来源：github | 类型：repository | 重要性：medium
一句话：该仓库是awesome-virtual-cell的扩展版，整理了AI基础模型、单细胞模型及扰动预测相关的知识库，但目前受密码保护且缺乏社区验证。
要点：
- 定位为awesome-virtual-cell的v2扩展版，聚焦AI基础模型与单细胞领域。
- 包含单细胞模型、扰动预测和虚拟细胞的知识库及演讲准备材料。
- 目前为密码门控状态且星标数为0，实际内容质量和可用性存在较大不确定性。
相关性：仓库明确提及AI基础模型、单细胞模型和扰动预测，与用户关注的单细胞基础模型和基因扰动预测高度契合；但未直接提及drug response或BioPatchFM，且因密码门控无法确认具体内容深度。
建议：尝试联系作者获取访问密码以评估知识库内容，或先将其作为追踪虚拟细胞与扰动预测动态的线索进行关注。
链接：https://github.com/LiudengZhang/fm-to-virtual-cells

2. **BaiDing1234/PertAdapt**
来源：github | 类型：repository | 重要性：medium
一句话：该仓库提出PertAdapt，尝试通过条件敏感适应方法将单细胞基础模型应用于基因扰动预测，但目前缺乏详细文档与实验验证结果。
要点：
- 提出条件敏感适应方法，旨在将单细胞基础模型适配至基因扰动预测任务
- 目前仓库星标数极低且无详细README，方法细节、代码完整性与实际效果存在高度不确定性
相关性：该工作直接涉及用户核心关注的'单细胞基础模型'与'基因扰动预测'，其微调适配思路可能对drug response预测有潜在参考价值，但与BioPatchFM的直接关联尚不确定。
建议：快速浏览仓库确认代码可用性，并持续追踪是否有配套论文发布以评估其真实性能。
链接：https://github.com/BaiDing1234/PertAdapt

3. **aaronwtr/PertEval**
来源：github | 类型：repository | 重要性：medium
一句话：这是一个用于评估转录组扰动效应预测模型（包括单细胞基础模型）的开源基准测试套件。
要点：
- 专注于转录组扰动效应预测模型的评估。
- 明确支持单细胞基础模型的基准测试。
- 涉及 CRISPR 等基因扰动场景。
- 注意：当前元数据与摘要信息有限，具体的评估指标、涵盖的数据集及支持的模型范围存在不确定性，需进一步查看仓库代码确认。
相关性：该仓库直接针对用户画像关注的“单细胞基础模型”和“基因扰动预测”，提供了专门的评估工具，有助于客观衡量相关模型在扰动预测任务上的表现，对 drug response 及扰动模型研发具有参考价值。
建议：访问仓库查看其评估指标与支持的基础模型列表，评估是否可用于自身模型（如 BioPatchFM 相关工作）的基准测试。
链接：https://github.com/aaronwtr/PertEval

## Deduplication summary
- Collected items: 3
- Duplicates skipped: 0
- New items included: 3

## Hotspot discovery updates
- Candidates considered: 3
- New topics added: 0
- Existing topics updated: 3