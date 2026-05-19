# Daily Research Intelligence - single-cell, foundation model, perturbation prediction

共 10 条

1. **scArchon: a scalable benchmarking framework for assessing single-cell perturbation models.**
来源：pubmed | 类型：paper | 重要性：high
一句话：scArchon是一个用于单细胞扰动预测模型（如药物响应）的模块化基准测试框架，评估发现现有方法性能差异大，且高定量评分不一定代表能保留关键生物学特征。
要点：
- 发布scArchon：基于Snakemake的可复现、可扩展的单细胞扰动预测模型基准测试平台。
- 横向对比：在6个scRNA-seq数据集上评估了scGen、CPA、trVAE等9种主流方法。
- 评估发现：模型性能异质性强，部分深度学习模型甚至不如线性基线；定量评分与生物学特征保留可能不一致，凸显基因层面评估的必要性。
- 局限性提示：当前评估主要针对传统深度学习模型，对单细胞基础模型的评估覆盖度尚不确定。
相关性：该论文直接针对用户关注的‘基因扰动预测’和‘drug response’，提供了当前主流预测模型的系统性基准测试结果。其指出的‘定量评分与生物学特征不一致’问题，对用户研发或应用相关模型（包括基础模型和BioPatchFM）的评估标准具有重要参考意义。
建议：阅读原文了解scGen、trVAE等主流扰动预测模型的具体优劣势，并考虑引入scArchon框架或其基因层面评估思路来验证自有模型。
链接：https://pubmed.ncbi.nlm.nih.gov/42121287/

2. **RegFormer: a single-cell foundation model powered by gene regulatory hierarchies.**
来源：pubmed | 类型：paper | 重要性：high
一句话：RegFormer是一种结合基因调控网络（GRN）与Mamba架构的单细胞基础模型，在基因扰动预测和药物反应预测任务上展现了潜力。
要点：
- 模型架构：将基因调控网络（GRN）先验与Mamba状态空间模型结合，以解决Transformer在长基因序列上的扩展性限制。
- 嵌入机制：采用双嵌入设计（表达值嵌入+调控身份嵌入），并按GRN引导的顺序组织基因，以捕捉表达动态和层级调控。
- 预训练数据：在涵盖45种组织及多种生物学背景的2500万个人类单细胞上进行预训练。
- 性能声明：作者声称在多项基准测试中优于scGPT、Geneformer等模型，但该结论尚需社区独立验证。
- 下游应用：能够重建GRN，模拟遗传扰动转录响应，并提升癌症细胞系的药物反应预测效果。
相关性：高度契合用户画像。该研究属于单细胞基础模型领域，且明确涉及用户关注的基因扰动预测和药物反应预测。其结合GRN先验与Mamba的架构设计，对关注基础模型演进（如与BioPatchFM等思路的对比）的研究者具有直接参考价值。
建议：阅读原文方法与结果部分，重点关注其GRN引导的基因排序机制，以及在扰动预测和药物反应任务上的具体评估设置与基线对比情况。
链接：https://pubmed.ncbi.nlm.nih.gov/42086551/

3. **GREmLN: A Cellular Graph Structure Aware Transcriptomics Foundation Model.**
来源：pubmed | 类型：paper | 重要性：high
一句话：GREmLN是一个单细胞转录组基础模型，通过将基因调控网络等图结构直接嵌入注意力机制，在细胞注释和反向扰动预测任务上表现出潜力。
要点：
- 针对单细胞RNA数据基因特征无序的问题，利用图信号处理将GRN/PPI等分子互作图结构直接嵌入Transformer的注意力机制中。
- 在细胞类型注释、图结构理解及微调后的反向扰动预测任务上，声称优于现有基线（注：该结论基于bioRxiv预印本，尚未经同行评审完全验证）。
- 引入图结构归纳偏置使得模型架构更参数高效，并加速了训练收敛。
相关性：该研究提出了一个新的单细胞基础模型（GREmLN），且明确在反向扰动预测任务上进行了评估，高度契合用户关注的'单细胞基础模型'和'基因扰动预测'方向；其利用图结构（如PPI/GRN）的思路可能对drug response或BioPatchFM相关研究有启发，但摘要未明确提及drug response应用，存在一定不确定性。
建议：阅读预印本原文，重点关注其图结构嵌入注意力机制的具体实现方式，以及在反向扰动预测任务上的微调方法和评估细节。
链接：https://pubmed.ncbi.nlm.nih.gov/41959137/

4. **LiudengZhang/fm-to-virtual-cells**
来源：github | 类型：repository | 重要性：medium
一句话：这是一个关于AI基础模型、单细胞模型、扰动预测及虚拟细胞的知识库与演讲准备资料库，为awesome-virtual-cell的扩展版本。
要点：
- 聚焦AI基础模型、单细胞模型及扰动预测，与用户关注领域直接相关
- 为awesome-virtual-cell项目的v2扩展版，整合了知识库与演讲准备材料
- 当前星标数为0，且需密码访问，其实际内容深度和可用性存在较大不确定性
相关性：该仓库主题明确包含单细胞基础模型和扰动预测，与用户画像高度契合；但摘要未提及drug response或BioPatchFM，且因密码门控无法确认具体内容，相关性存在一定不确定性。
建议：尝试访问该GitHub仓库获取密码或联系作者，以评估其知识库内容对当前研究的实际参考价值。
链接：https://github.com/LiudengZhang/fm-to-virtual-cells

5. **scREPA: Predicting single-cell perturbation responses with cycle-consistent representation alignment.**
来源：pubmed | 类型：paper | 重要性：high
一句话：本文提出scREPA框架，通过将VAE表征与预训练单细胞基础模型表征对齐，并结合最优传输，提升单细胞扰动响应预测的准确性与泛化能力。
要点：
- 提出scREPA框架，将VAE的潜在表征与预训练单细胞基础模型的高质量外部表征对齐。
- 引入循环一致表征对齐机制，增强生成表达谱的表征质量与双重一致性。
- 推理阶段使用最优传输对齐未配对对照与扰动数据分布，实现稳健预测。
- 作者报告其在差异表达基因及全转录组预测上优于现有方法，且泛化性较好（该结论有待独立验证）。
相关性：本文直接涉及‘单细胞基础模型’的表征应用与‘基因扰动预测’，与用户画像高度契合。但摘要未明确提及在drug response数据集上的验证，也未涉及BioPatchFM，其在药物响应及特定模型上的适用性存在不确定性。
建议：阅读原文方法部分，评估其表征对齐策略是否可迁移至BioPatchFM或drug response预测任务中。
链接：https://pubmed.ncbi.nlm.nih.gov/41129969/

6. **BaiDing1234/PertAdapt**
来源：github | 类型：repository | 重要性：low
一句话：该项目提出PertAdapt，尝试通过条件敏感适应策略将单细胞基础模型应用于基因扰动预测，但目前缺乏详细文档与验证，实际效果存疑。
要点：
- 提出PertAdapt方法，旨在解锁单细胞基础模型在基因扰动预测上的潜力
- 采用条件敏感适应机制
- 目前仓库星标极低(6)，无详细README或实验数据，成熟度与有效性高度不确定
相关性：项目核心主题为‘单细胞基础模型’与‘基因扰动预测’，与用户画像高度重合；但缺乏文档说明其是否涉及drug response或类似BioPatchFM的机制，相关性细节存在不确定性。
建议：克隆仓库查看源码实现细节，或暂时观望等待作者补充文档与验证结果。
链接：https://github.com/BaiDing1234/PertAdapt

7. **Predicting drug responses of unseen cell types through transfer learning with foundation models.**
来源：pubmed | 类型：paper | 重要性：high
一句话：该研究提出CRISP框架，利用单细胞基础模型和细胞类型特异性学习策略，预测未见细胞类型的药物扰动响应，并在跨平台和零样本药物重定位场景中展现了初步泛化能力。
要点：
- 提出CRISP框架，结合基础模型预测单细胞分辨率下未见细胞类型的药物扰动响应。
- 采用细胞类型特异性学习策略，在有限经验数据下实现从对照到扰动状态的信息迁移。
- 在跨平台预测及零样本药物重定位（实体瘤到慢性髓系白血病）中表现出泛化性，其预测的CXCR4抑制机制有独立研究支持（注：临床转化效果仍需进一步验证）。
相关性：高度契合用户画像：1) 核心利用单细胞基础模型解决扰动预测问题；2) 聚焦drug response及未见细胞类型的泛化挑战；3) CRISP的框架思路（基础模型+扰动响应）对关注BioPatchFM的用户具有直接参考价值，尽管论文未明确提及BioPatchFM，其架构设计思路具有较高相关性。
建议：阅读原文方法部分，重点关注CRISP如何整合基础模型与细胞类型特异性策略，评估其架构对BioPatchFM或自身扰动预测任务的借鉴意义。
链接：https://pubmed.ncbi.nlm.nih.gov/41044387/

8. **Characterizing spatial functional microniches with SpaceTravLR.**
来源：pubmed | 类型：paper | 重要性：high
一句话：SpaceTravLR是一种可解释的机器学习方法，旨在弥补现有单细胞基础模型缺乏空间分辨率的不足，通过空间分子网络推断基因扰动对组织微环境信号的重塑作用。
要点：
- 针对现有单细胞扰动预测和基础模型缺乏空间分辨率的痛点，提出SpaceTravLR模型。
- 能够推断单基因或组合基因扰动（转录因子、配体和受体）如何通过空间分子网络重塑目标细胞及其周围微环境。
- 在多种组织背景下定义了空间功能微环境，其扰动预测与实验验证较吻合（注：目前为bioRxiv预印本，结论待同行评审确认）。
相关性：该研究直接针对用户关注的‘基因扰动预测’和‘单细胞基础模型’在空间维度的局限性，将扰动预测扩展至空间微环境，与空间patch建模（如BioPatchFM相关概念）有潜在关联；但摘要未明确提及drug response，其在药物反应上的直接应用尚存不确定性。
建议：阅读预印本原文，重点关注其空间扰动推断机制是否可借鉴至单细胞基础模型或空间patch建模中，并评估其对drug response预测的扩展潜力。
链接：https://pubmed.ncbi.nlm.nih.gov/41292756/

9. **Heimdall: A Modular Framework for Tokenization in Single-Cell Foundation Models.**
来源：pubmed | 类型：paper | 重要性：medium
一句话：Heimdall是一个开源框架，用于系统评估单细胞基础模型的Token化策略，发现其在分布偏移下对模型性能（含逆向扰动预测）有显著影响。
要点：
- 提出Heimdall框架，将单细胞基础模型解耦为基因身份编码器、表达编码器和细胞句子构造器，以精细评估和重组Token化策略。
- 在跨组织、跨物种等分布偏移场景下，Token化选择对细胞类型分类起决定性作用（基因编码和排序影响最大），但在分布内影响较小。
- 单独评估了逆向扰动预测，表明Token化策略对扰动预测任务同样重要（注：摘要未明确提及drug response结果，其对药物响应的直接影响尚不确定）。
相关性：该研究直接针对单细胞基础模型的Token化设计，且明确评估了逆向扰动预测，与用户关注的单细胞基础模型和基因扰动预测高度相关；虽然未直接验证drug response，但扰动预测的优化可能对后续drug response建模有间接启发。
建议：查阅预印本原文，重点关注其逆向扰动预测的评估细节及开源工具包，评估是否可将其Token化模块应用于自身的基因扰动或drug response模型中。
链接：https://pubmed.ncbi.nlm.nih.gov/41292913/

10. **MultiPert: An adversarial alignment and dual attention framework for single-cell multi-omics perturbation prediction.**
来源：pubmed | 类型：paper | 重要性：medium
一句话：MultiPert提出了一种结合模态特异性预训练编码器、双重注意力机制和对抗训练的深度学习框架，用于预测单细胞多组学扰动响应。
要点：
- 针对现有扰动预测多局限于单模态转录组的问题，提出了多组学（转录组+蛋白质组）扰动预测框架MultiPert。
- 技术路线上，采用模态特异性预训练编码器，利用双重注意力机制整合扰动信息，并通过对抗训练实现跨模态对齐。
- 在THP-1和肾脏数据集上，模型预测了扰动后的基因表达与蛋白质丰度，作者声称其优于现有方法且能泛化至未见扰动（注：此优越性及泛化能力基于作者自身基准测试，有待独立验证）。
- 应用层面，模型预测揭示了免疫检查点分子的调控机制，为药物发现提供方法学参考。
相关性：该论文核心任务直接契合用户关注的‘基因扰动预测’；其采用的模态特异性预训练编码器与‘单细胞基础模型’的预训练思路存在关联；多组学扰动预测及免疫相关机制挖掘对‘drug response’研究有参考价值。但该模型是否属于大规模基础模型，以及其架构与BioPatchFM的直接关联度，当前摘要信息不足以确认，存在不确定性。
建议：阅读原文方法部分，重点关注其模态特异性预训练策略和双重注意力机制整合扰动的设计，评估该思路是否可迁移至单细胞基础模型或BioPatchFM的扰动模块中。
链接：https://pubmed.ncbi.nlm.nih.gov/41811907/