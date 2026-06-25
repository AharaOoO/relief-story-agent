# LTX 2.3 三 LoRA 永久融合设计

## 目标

生成一颗在 ComfyUI 中以 `strength=1.0` 加载时，等效于以下运行时叠加的 LTX 2.3 LoRA：

- `LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors`：`1.50`
- `Singularity-LTX-2.3_OmniCine_V1.safetensors`：`0.55`
- `Ltx2.3-Licon-VBVR-I2V-390K-R32.safetensors`：`0.73`

输出两个运行版本：

- BF16 基准版：无 SVD、无降秩。
- FP8 E4M3 版：从同一 FP32 融合过程量化得到，并附带误差报告。

## 原文件保护

三个源文件只读使用，不移动、不重命名、不修改，也不在其所在目录写入任何输出。执行前记录源文件的绝对路径、字节数、修改时间和 SHA-256。随后复制到工作区 `source_copies`，验证副本 SHA-256 与源文件一致，融合过程只读取副本。

## 已确认的输入结构

三个文件均为 Diffusers 风格的 `.lora_A.weight` / `.lora_B.weight`，全部为 BF16，均无 `.alpha` 张量：

- OmniNFT：1,344 个模块，rank 32。
- OmniCine：1,632 个模块，rank 128。
- VBVR：1,248 个模块，rank 32。
- 三者并集：1,632 个模块；公共模块 1,248 个。
- 输入/输出维度冲突：0。

ComfyUI 对缺少 alpha 的普通 LoRA 使用系数 1.0，因此融合必须复现：

`1.50 * B1A1 + 0.55 * B2A2 + 0.73 * B3A3`

## 融合算法

采用 rank 拼接，不对完整增量矩阵做 SVD。对每个模块分别处理。为改善 BF16 和 FP8 量化时的数值平衡，将每个正权重 `s` 均匀分配到 A、B 两侧：

`A' = concat(sqrt(s1)A1, sqrt(s2)A2, sqrt(s3)A3, dim=0)`

`B' = concat(sqrt(s1)B1, sqrt(s2)B2, sqrt(s3)B3, dim=1)`

于是 `B'A'` 等于三颗 LoRA 的加权增量之和。BF16 文件继续省略 alpha。FP8 文件为了减少小权重下溢，增加逐模块 F32 alpha 补偿；两版在 ComfyUI 中都以 strength 1.0 加载。

各模块的输出 rank：

- 三颗均覆盖：192。
- OmniNFT 与 OmniCine 覆盖：160。
- 只有 OmniCine 覆盖：128。

## 精度与输出

融合计算在 CPU FP32 中逐模块完成，避免一次性展开完整 22B 增量矩阵。

- BF16：拼接结果转换为 BF16 后保存。
- FP8：同一 FP32 拼接结果先进行逐 rank 通道平衡，再将每个模块缩放至适合 E4M3 的范围，A/B 保存为 `torch.float8_e4m3fn`，补偿 alpha 保存为 F32。

FP8 是有损版本。它的主要收益是文件与常驻权重内存约减半；ComfyUI 加载后仍会转换到模型计算 dtype，因此不承诺采样速度翻倍。

## 验证

1. 融合前后重新计算三个源文件 SHA-256，必须保持不变。
2. 三个副本 SHA-256 必须分别等于源文件。
3. 检查所有 A/B 成对、形状合法、无未知训练张量、无 NaN/Inf。
4. 对每个模块使用固定随机向量，比较三颗输入的加权输出与融合输出。
5. BF16 和 FP8 分别输出最大绝对误差、相对 L2 误差和余弦相似度汇总。
6. 使用本地 safetensors 读取器重新打开成品，核对 dtype、键数、形状和元数据。

## 输出位置

所有文件只写入：

`D:\codex工作区\ltx23_lora_merge`

不会自动复制回 ComfyUI 的原 LoRA 目录。
