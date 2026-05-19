# Daily Research Intelligence - single-cell foundation model perturbation prediction drug response

共 5 条

1. **MAP: A Knowledge-driven Framework for Predicting Single-cell Responses for Unprofiled Drugs | bioRxiv**
来源：web | 类型：paper | 重要性：medium
一句话：MAP是一个知识增强框架，旨在预测细胞对小分子扰动的转录反应，重点解决未见细胞类型-药物组合的泛化及零样本预测问题。
要点：
- 提出知识增强框架MAP，预测小分子扰动下的单细胞转录反应。
- 解决未见细胞类型与药物组合的泛化挑战。
- 涉及零样本预测能力。
- 注意：由于摘要信息有限，具体模型架构、是否基于基础模型及验证结果存在不确定性。
相关性：该论文关注单细胞层面的药物扰动预测，与用户画像中的‘基因扰动预测’和‘drug response’高度契合；虽然摘要未明确提及单细胞基础模型，但其知识驱动的零样本预测思路对相关领域（如BioPatchFM）的设计可能有参考价值。
建议：阅读原文以确认MAP是否使用了单细胞基础模型架构，以及其零样本预测在具体药物反应任务上的实际表现。
链接：https://www.biorxiv.org/content/10.64898/2026.02.25.708091v1.full

2. **Predicting drug responses of unseen cell types through transfer learning with foundation models | Nature Computational Science**
来源：web | 类型：paper | 重要性：high
一句话：该研究提出CRISP框架，旨在利用基础模型的迁移学习，在单细胞分辨率下预测未见细胞类型的药物扰动响应。
要点：
- 提出名为CRISP的预测框架，专注于单细胞分辨率的药物扰动响应预测。
- 利用基础模型的迁移学习来应对未见细胞类型的泛化挑战。
- （注：受限于摘要信息不足，该框架的具体网络架构、验证数据集及实际预测性能尚不确定）
相关性：高度契合用户画像：论文直接涉及单细胞基础模型、扰动预测和药物反应，其针对未见细胞类型的迁移学习策略，对BioPatchFM等基础模型的下游应用和泛化设计具有重要参考价值。
建议：阅读原文以确认CRISP依赖的具体基础模型架构及其在未见细胞类型上的实际泛化效果。
链接：https://www.nature.com/articles/s43588-025-00887-6

3. **Foundation Models Improve Perturbation Response Prediction**
来源：web | 类型：paper | 重要性：high
一句话：该预印本探讨基础模型在提升多场景下扰动响应预测准确性方面的潜力，但受限于摘要截断，具体结论与验证情况尚不确定。
要点：
- 研究聚焦基础模型在扰动响应预测中的应用
- 模型可能通过学习敲除基因的活性等机制来提升预测表现
- 摘要信息不足，无法确认其是否基于单细胞数据、是否涉及药物响应及具体验证结果
相关性：标题与检索词直接命中用户关注的'基础模型'与'扰动预测'；虽然摘要未完整展示，但基因扰动预测是drug response研究的基础，与用户画像高度相关，具体是否涉及单细胞或BioPatchFM需进一步确认。
建议：阅读全文以确认模型是否基于单细胞数据、是否包含药物响应预测任务，并评估其与BioPatchFM的异同。
链接：https://www.biorxiv.org/content/10.64898/2026.02.18.706454v1.full-text

4. **GitHub - xianglin226/Benchmarking-Single-Cell-Perturbation: Single-Cell (Perturbation) Model Library · GitHub**
来源：web | 类型：code | 重要性：medium
一句话：该GitHub仓库汇总了单细胞扰动预测模型，包含CellBox和scPreGAN等用于预测基因/药物扰动响应的算法。
要点：
- 收录了多个单细胞扰动预测模型（如CellBox、scPreGAN等）。
- CellBox侧重于可解释的机器学习，应用于癌症联合治疗设计（drug response）。
- scPreGAN是基于深度生成模型的单细胞表达扰动响应预测方法。
- 注意：由于页面抓取受限，仓库内具体包含的基础模型或最新更新情况存在不确定性。
相关性：用户关注基因扰动预测和drug response，该仓库直接汇总了相关预测模型，可能为评估或开发单细胞扰动预测及药物响应模型提供基准和代码参考。
建议：访问GitHub仓库查看完整模型列表和基准结果，评估其是否包含与单细胞基础模型或BioPatchFM相关的对比基线。
链接：https://github.com/xianglin226/benchmarking-single-cell-perturbation

5. **Efficient Fine-Tuning of Single-Cell Foundation Models Enables Zero-Shot Molecular Perturbation Prediction | OpenReview**
来源：web | 类型：webpage | 重要性：high
一句话：本研究提出一种药物条件适配器，通过微调不到1%的参数对单细胞基础模型进行高效调整，以尝试实现零样本分子扰动预测。
要点：
- 利用在数千万单细胞上预训练的基础模型处理分子扰动预测问题。
- 引入药物条件适配器，仅需微调不到1%的原始模型参数，实现高效训练。
- 探索零样本分子扰动预测能力（注：因摘要截断，具体实验验证结果与性能尚不确定）。
相关性：该研究直接聚焦单细胞基础模型、分子扰动预测和药物响应，与用户核心关注点高度重合；其参数高效微调（Adapter）的思路可能对BioPatchFM的模块设计或下游任务适配具有参考意义。
建议：点击链接查看OpenReview完整论文，重点关注其零样本预测的验证基准及药物条件适配器的具体架构。
链接：https://openreview.net/forum?id=tkn6gpvlux

## Deduplication summary
- Collected items: 5
- Duplicates skipped: 0
- New items included: 5