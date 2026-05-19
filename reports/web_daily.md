# Daily Research Intelligence - single-cell foundation model perturbation prediction drug response

共 5 条

1. **Deep generative framework for modeling single-cell drug perturbation response - ScienceDirect**
来源：web | 类型：webpage | 重要性：medium
一句话：scDPR框架基于深度生成架构，预测药物扰动后的单细胞转录组状态并分解细胞特异性药物效应，但因页面未抓取，其具体性能与验证情况存在不确定性。
要点：
- 提出名为scDPR的深度生成框架
- 预测药物扰动下的单细胞转录组状态
- 将观察到的响应分解为可解释的、细胞特异性的药物效应
- 因摘要和元数据不足，模型实际性能、验证数据及与同类方法的对比均不确定
相关性：该研究聚焦于单细胞层面的药物扰动响应预测，与用户关注的drug response和基因扰动预测高度契合；但当前信息无法判断其是否采用了单细胞基础模型架构或与BioPatchFM存在关联。
建议：点击原文链接，确认scDPR的具体网络架构、是否结合预训练基础模型，以及其在药物响应预测任务上的实际表现。
链接：https://www.sciencedirect.com/science/article/abs/pii/S0893608026004661

2. **Foundation Models Improve Perturbation Response Prediction | bioRxiv**
来源：web | 类型：webpage | 重要性：medium
一句话：该预印本标题提示基础模型可改善扰动响应预测，但因页面未抓取且摘要仅含过往引文，具体方法与结论存在不确定性。
要点：
- 标题直接涉及基础模型与扰动响应预测，与单细胞及药物响应领域潜在相关。
- 现有摘要片段仅包含Dr. VAE和scGen等早期研究的引文，缺乏本文具体模型架构和验证结果。
- 由于元数据严重不足，该研究是否真正推进了单细胞基因扰动预测尚无法确认。
相关性：标题高度契合用户关注的'单细胞基础模型'、'基因扰动预测'和'drug response'，但受限于摘要缺失，其与BioPatchFM等具体技术路线的相关性存在不确定性。
建议：访问原文链接查看完整摘要，确认其基础模型架构及在单细胞药物扰动预测上的具体表现。
链接：https://www.biorxiv.org/content/10.64898/2026.02.18.706454v1.full

3. **Predicting and interpreting cell-type-specific drug responses in the small-data regime using inductive priors | Nature Machine Intelligence**
来源：web | 类型：webpage | 重要性：high
一句话：PrePR-CT模型旨在利用归纳先验，在小数据场景下实现细胞类型特异性的药物反应预测，为早期药物发现的细胞扰动建模提供基础（注：因原文未完整抓取，具体结论与机制存在不确定性）。
要点：
- 提出PrePR-CT方法，针对小数据条件下的细胞类型特异性药物反应预测问题。
- 该方法结合了可扩展性、对分布偏移的鲁棒性以及可解释性。
- 为早期药物发现中更精确的细胞扰动建模提供潜在基础（基于有限摘要，具体技术细节和验证结果尚不确定）。
相关性：与用户关注的drug response和基因扰动预测高度相关。该研究涉及细胞扰动建模与药物反应预测，且在小数据机制下的探索可能对单细胞基础模型及BioPatchFM的应用场景具有参考价值。但因信息不足，其与单细胞基础模型的具体关联度尚不确定。
建议：阅读原文，重点关注PrePR-CT的归纳先验设计及其在单细胞扰动预测上的表现，评估其方法思路对BioPatchFM的启发或互补性。
链接：https://www.nature.com/articles/s42256-026-01202-2

4. **MAP: A Knowledge-driven Framework for Predicting Single-cell Responses for Unprofiled Drugs | bioRxiv**
来源：web | 类型：webpage | 重要性：medium
一句话：MAP是一个知识增强框架，初步声称可预测细胞对小分子扰动的转录反应，并解决未见细胞类型-药物组合泛化及零样本预测问题（注：因原文未完整获取，具体性能与结论尚待验证）。
要点：
- 提出知识增强框架MAP，用于预测单细胞对小分子扰动的转录反应。
- 旨在解决未见细胞类型与药物组合的泛化挑战。
- 探索对未分析药物的零样本预测能力。
- （不确定性提示：当前仅基于搜索片段，缺乏模型细节、实验数据与验证结果的完整信息）
相关性：该研究聚焦于单细胞层面的药物扰动转录反应预测及零样本泛化，与用户关注的‘基因扰动预测’和‘drug response’高度契合；其知识驱动的框架思路可能对单细胞基础模型或BioPatchFM的架构设计具有参考价值。
建议：点击链接阅读预印本原文，重点关注其知识增强机制的具体实现方式以及零样本预测的基线对比结果。
链接：https://www.biorxiv.org/content/10.64898/2026.02.25.708091v1.full

5. **scREPA: Predicting single-cell perturbation responses with cycle-consistent representation alignment - ScienceDirect**
来源：web | 类型：webpage | 重要性：high
一句话：scREPA采用scGPT作为预训练模型，通过循环一致表征对齐方法预测细胞在药物处理等扰动下的基因表达变化，但受限于摘要信息不全，其确切性能尚待确认。
要点：
- 基于单细胞基础模型scGPT进行构建
- 核心任务为预测多种扰动（含药物处理、细胞因子等）下的基因表达结果
- 采用循环一致表征对齐（cycle-consistent representation alignment）技术
- 注意：由于页面未完整抓取，模型的具体验证效果和对比数据暂不确定
相关性：高度相关：该研究直接使用了单细胞基础模型scGPT，且核心应用场景为基因扰动预测和药物响应，精准匹配用户画像。但受限于信息不足，其与BioPatchFM的潜在关联暂无法判断。
建议：点击链接阅读原文，重点关注其在药物响应预测上的评估指标及与现有扰动预测基线模型的对比结果。
链接：https://www.sciencedirect.com/science/article/pii/S1476927125003731