# Daily Research Intelligence - single-cell, foundation model, perturbation prediction

共 10 条

1. **scArchon: a scalable benchmarking framework for assessing single-cell perturbation models.**
来源：pubmed | 类型：paper | 重要性：high
一句话：scArchon是一个基于Snakemake的单细胞扰动预测模型基准测试框架，其评估显示现有方法表现异质性强，且定量高分未必能保留关键生物学特征。
要点：
- 提出scArchon：可复现、模块化的单细胞扰动预测工具评估平台。
- 评估9种主流方法：在6个数据集上对比scGen、CPA、trVAE等，发现trVAE、scGen等相对稳健，部分方法甚至不如线性基线。
- 生物学特征保留问题：定量评分好的模型可能无法保留关键的基因级生物学扰动特征，强调需结合生物学指标评估。
相关性：用户关注“基因扰动预测”和“drug response”，该论文系统评估了当前单细胞扰动预测（含药物反应）的主流模型表现，指出了现有方法在生物学特征保留上的不足，对用户了解该领域模型现状、选择基线模型或开发新模型（如BioPatchFM）具有重要参考价值。
建议：阅读原文以了解scArchon的评估指标体系，特别是基因级生物学特征评估部分，作为后续模型开发或对比的参考基线。
链接：https://pubmed.ncbi.nlm.nih.gov/42121287/

2. **RegFormer: a single-cell foundation model powered by gene regulatory hierarchies.**
来源：pubmed | 类型：paper | 重要性：high
一句话：RegFormer是一种整合基因调控网络(GRN)与Mamba架构的单细胞基础模型，据报道在细胞注释、基因扰动响应及药物反应预测任务上优于现有模型。
要点：
- 引入基于Mamba的状态空间建模，结合GRN先验，旨在解决Transformer长序列扩展性及缺乏调控先验的问题。
- 采用双嵌入机制（表达量嵌入+调控身份嵌入）及GRN引导的基因排序，以捕捉表达动态与层级调控。
- 在2500万人类单细胞上预训练，作者声称在聚类、批次整合等基准上超越scGPT、Geneformer等现有模型。
- 据报道该模型能重建GRN、建模基因扰动转录响应，并提升癌症细胞系药物反应预测效果（需注意这些结论尚待独立验证）。
相关性：高度契合用户画像：该研究属于单细胞基础模型领域，且明确涉及基因扰动预测和drug response预测。其结合GRN先验与Mamba架构的思路，可能对BioPatchFM等模型的设计或改进具有参考价值。
建议：阅读原文方法与实验部分，重点关注其GRN引导机制在基因扰动和药物反应任务上的具体表现，并跟进是否有开源代码可供复现测试。
链接：https://pubmed.ncbi.nlm.nih.gov/42086551/

3. **GREmLN: A Cellular Graph Structure Aware Transcriptomics Foundation Model.**
来源：pubmed | 类型：paper | 重要性：high
一句话：GREmLN是一种将基因调控网络等图结构直接嵌入注意力机制的单细胞转录组基础模型，在细胞注释和反向扰动预测任务上表现出潜力。
要点：
- 针对单细胞RNA数据基因特征无序的问题，引入GRN/PPI等分子互作图结构作为归纳偏置。
- 利用图信号处理将图结构嵌入注意力机制，生成具有生物学信息的基因嵌入。
- 在细胞类型注释、图结构理解及微调的反向扰动预测任务上，声称优于现有基线（注：该论文为bioRxiv预印本，结论尚未经同行评审验证）。
- 图结构的引入使得模型架构更参数高效，并加速训练收敛。
相关性：该论文提出了新的单细胞基础模型(GREmLN)，且明确在“反向扰动预测”任务上进行了微调测试，直接契合用户关注的“单细胞基础模型”和“基因扰动预测”方向；其利用图结构（如PPI/GRN）嵌入注意力的方式，可能对用户关注的“BioPatchFM”或drug response建模有架构参考价值。
建议：阅读预印本原文，重点关注其图结构嵌入注意力机制的具体实现，以及在反向扰动预测任务上的微调方法与评估指标。
链接：https://pubmed.ncbi.nlm.nih.gov/41959137/

4. **LiudengZhang/fm-to-virtual-cells**
来源：github | 类型：repository | 重要性：medium
一句话：该仓库是awesome-virtual-cell的扩展版，整理了单细胞基础模型、扰动预测及虚拟细胞相关的知识库，但目前受密码保护且缺乏社区关注，内容可用性存疑。
要点：
- 聚焦AI基础模型、单细胞模型、扰动预测与虚拟细胞的知识库与演讲素材
- 为awesome-virtual-cell项目的v2扩展版本
- 客户端受密码门控，且当前0星0分支，实际内容质量与完整性无法直接验证
相关性：主题直接覆盖用户画像关注的‘单细胞基础模型’与‘基因扰动预测’；虚拟细胞与扰动预测通常与drug response研究密切相关，具有潜在参考价值。但因密码门控，实际内容与用户画像的匹配度存在不确定性。
建议：尝试联系作者获取访问权限以评估知识库内容，或暂作收藏观察其后续公开情况与社区反馈。
链接：https://github.com/LiudengZhang/fm-to-virtual-cells

5. **scREPA: Predicting single-cell perturbation responses with cycle-consistent representation alignment.**
来源：pubmed | 类型：paper | 重要性：high
一句话：本文提出scREPA框架，通过将VAE的潜在表示与预训练单细胞基础模型对齐，并结合最优传输方法，提升了单细胞扰动响应预测的准确性与泛化能力。
要点：
- 核心方法：提出scREPA，将VAE从噪声数据提取的潜在嵌入与预训练单细胞基础模型提供的高质量生物嵌入进行对齐。
- 创新机制：引入循环一致表示对齐，对VAE生成表达谱的重新编码嵌入施加双重一致性约束，以提升表示质量。
- 推理优化：在推理阶段使用最优传输对齐未配对的对照与扰动数据分布，减少不匹配以实现稳健预测。
- 实验表现：在多数据集上预测差异表达基因和全转录组响应优于现有方法，且泛化至未见条件和跨研究场景（注：摘要未明确说明是否包含药物响应数据验证，该部分应用潜力存在不确定性）。
相关性：高度契合用户画像。该研究直接涉及“单细胞基础模型”的下游应用与“基因扰动预测”，其利用scFM表示对齐来改善扰动预测的思路，对关注基础模型应用及扰动预测的用户具有直接参考价值；虽未明确提及drug response和BioPatchFM，但扰动预测是药物响应建模的核心基础，表示对齐策略可能具有迁移启发意义。
建议：阅读原文方法部分，重点关注其提取和对齐scFM嵌入的具体实现，以及OT在未配对扰动推理中的应用，评估该对齐框架是否可迁移至BioPatchFM或药物响应预测场景。
链接：https://pubmed.ncbi.nlm.nih.gov/41129969/

6. **BaiDing1234/PertAdapt**
来源：github | 类型：repository | 重要性：medium
一句话：PertAdapt 提出一种条件敏感的适应方法，旨在将单细胞基础模型应用于基因扰动预测。
要点：
- 聚焦单细胞基础模型在基因扰动预测任务上的应用
- 提出条件敏感适应机制来解锁基础模型的该方面潜力
- 注意：目前仓库缺乏详细 README 和文档，具体方法细节、实验效果及是否涉及 drug response 存在不确定性
相关性：高度相关：项目直接针对用户关注的‘单细胞基础模型’和‘基因扰动预测’。但需注意仓库极新（6星标），缺乏文档，其与 drug response 或 BioPatchFM 的具体关联及实际性能尚不确定。
建议：访问仓库查看 README 和代码，确认其适应机制的具体实现及是否可扩展至药物响应预测场景。
链接：https://github.com/BaiDing1234/PertAdapt

7. **Predicting drug responses of unseen cell types through transfer learning with foundation models.**
来源：pubmed | 类型：paper | 重要性：high
一句话：本研究提出CRISP框架，利用单细胞基础模型和细胞类型特异性学习策略，实现对未见细胞类型的药物扰动响应预测及零样本药物重定位。
要点：
- 提出CRISP框架，结合基础模型预测未见细胞类型的单细胞分辨率药物扰动响应（摘要未详述其具体依赖的基础模型架构，存在一定不确定性）。
- 采用细胞类型特异性学习策略，在有限经验数据下实现从对照到扰动状态的有效信息迁移。
- 在跨平台等场景下展示了泛化性能，并在索拉非尼治疗慢性髓系白血病的零样本预测中，其推断的CXCR4通路抑制机制得到独立研究支持（但实际临床转化效果仍需谨慎看待）。
相关性：高度契合用户画像：该研究直接涉及单细胞基础模型在药物/基因扰动预测（perturbation response）和drug response中的应用，其针对未见细胞类型的泛化能力与BioPatchFM等基础模型关注的下游任务和泛化性问题紧密相关。
建议：阅读原文了解CRISP具体调用的基础模型及特征提取方式，评估其架构对BioPatchFM等模型在drug response任务上的借鉴意义。
链接：https://pubmed.ncbi.nlm.nih.gov/41044387/

8. **Characterizing spatial functional microniches with SpaceTravLR.**
来源：pubmed | 类型：paper | 重要性：medium
一句话：SpaceTravLR是一种可解释的机器学习方法，旨在推断基因扰动如何通过空间分子网络重塑细胞及其邻域信号，以定义空间功能微生态位。
要点：
- 现有单细胞扰动预测方法和基础模型缺乏空间分辨率，无法捕捉扰动在空间邻域的传播。
- SpaceTravLR通过空间解析的分子网络传播效应，推断单基因或组合基因扰动对目标细胞及周围邻域的重塑作用。
- 该方法仅基于空间组学数据进行扰动预测，初步结果显示与实验验证或已知机制一致（注：目前为bioRxiv预印本，结论有待同行评审验证）。
- 应用该方法发现了Ccr4驱动致病性T细胞空间定位的新机制假设。
相关性：该研究直接针对‘基因扰动预测’在空间组学层面的扩展，并讨论了现有‘单细胞基础模型’在空间分辨率上的局限性，与用户关注的基因扰动预测和单细胞基础模型高度相关；其空间扰动推断框架可能为药物反应在微环境中的空间传播建模提供参考。
建议：阅读预印本方法部分，评估其空间扰动传播网络架构是否可借鉴于BioPatchFM或drug response的空间建模中。
链接：https://pubmed.ncbi.nlm.nih.gov/41292756/

9. **Heimdall: A Modular Framework for Tokenization in Single-Cell Foundation Models.**
来源：pubmed | 类型：paper | 重要性：medium
一句话：Heimdall是一个系统评估单细胞基础模型tokenization策略的开源框架，研究发现tokenization在分布偏移下对性能起决定性作用，并初步评估了其对反向扰动预测的影响。
要点：
- 提出Heimdall框架，将单细胞基础模型解耦为基因身份编码器(F G)、表达编码器(F E)和细胞句子构造器(F C)等模块，实现细粒度控制与归因。
- 在跨组织、跨物种等分布偏移场景下，tokenization策略对细胞类型分类性能起决定性作用（F G和顺序影响最大），但在分布内影响较小。
- 单独评估了反向扰动预测，但摘要未提供具体量化结论；该研究目前为bioRxiv预印本，结论尚待同行评审验证。
相关性：用户关注单细胞基础模型和基因扰动预测。该论文直接探讨了单细胞基础模型的tokenization设计，并明确评估了反向扰动预测，与用户核心关注点高度契合；虽未直接提及drug response或BioPatchFM，但tokenization优化对下游泛化任务（如药物响应）具有潜在参考价值。
建议：查阅Heimdall开源工具包，重点关注其反向扰动预测评估模块，测试不同tokenization组合对自身基因扰动或药物响应预测任务的影响。
链接：https://pubmed.ncbi.nlm.nih.gov/41292913/

10. **MultiPert: An adversarial alignment and dual attention framework for single-cell multi-omics perturbation prediction.**
来源：pubmed | 类型：paper | 重要性：high
一句话：MultiPert提出了一种结合模态特定预训练、双重注意力与对抗训练的深度学习框架，用于单细胞多组学扰动响应预测，并在未见扰动泛化及免疫调控机制发现上展现了潜力。
要点：
- 针对现有扰动预测多局限于单模态转录组的问题，提出多组学（转录组+蛋白组）扰动预测框架MultiPert。
- 技术路线：采用模态特定预训练编码器、双重注意力机制整合扰动信号、对抗训练实现跨模态对齐。
- 在THP-1和肾脏多组学数据集上，作者声称其预测扰动后基因表达和蛋白丰度的准确度与稳定性优于现有方法（注：该结论尚缺乏外部独立验证，且未见代码可用性说明）。
- 模型可泛化至未见扰动，并基于蛋白组预测揭示了免疫检查点分子的潜在调控机制，为药物发现提供计算参考。
相关性：直接命中用户关注的‘基因扰动预测’核心领域；其采用的预训练编码器和多组学对齐策略，对‘单细胞基础模型’和‘drug response’研究具有技术参考价值；与BioPatchFM同属单细胞扰动建模方向，技术路线可对比借鉴。
建议：阅读论文方法部分，评估其模态特定预训练与双重注意力机制是否可借鉴至BioPatchFM或多组学drug response预测中。
链接：https://pubmed.ncbi.nlm.nih.gov/41811907/