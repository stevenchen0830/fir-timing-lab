# FIR Timing Lab

**可复现的垂直 FIR 微架构与时序优化实验。** 从系数旋转、相关慢时钟 SRAM、
事务队列到分段 MAC 和信用流控，记录“功能测试 → 综合筛查 → 早期布局 → 拒绝不合格候选”的完整实验链。

> **当前整块 FIR 尚未达到全角 1 GHz，不能用于流片签核。**
> deep32 的单通道零线延迟 setup 通过，不等于完整 FIR 通过；FF hold 仍有违例。
> 本仓库不分发 TSMC 库、厂商模型、映射网表或物理数据库。

[架构与设计取舍](docs/architecture.md) · [详细复现步骤](docs/reproduction.md) ·
[IC Design 流程](docs/ic-design-walkthrough.md) · [验证与覆盖](docs/verification.md) ·
[结果与限制](experiments/fir_core_opt/README.md) · [私有模型接口](docs/private-models.md)

## 1. 项目做什么

实现 1～49 个奇数 tap 的垂直 FIR，10-bit RGBA，每个 beat 处理 4 pixels（16 个分量）。
核心思想是**旋转 392-bit 系数，而不是旋转 7,840-bit 行数据**。镜像边界下多个 tap
落到同一 bank 时，先合并系数；49 个逻辑行 bank 固定存储数据，当前行旁路避免单端口读写冲突。

这次实验在该前端上构建：

- 49 个逻辑 bank × 4 个地址条带的慢 SRAM 行为接口；
- 共同源派生的 /3 SRAM 时钟，以及请求 ID、49-bank 返回、系数/旁路统一的事务队列；
- 9/20/21/32 级 MAC 候选，考察算术关键路径与寄存器代价；
- 自由运行 MAC + 预留输出信用，隔开外部反压和巨大的流水使能网络；
- 四状态单元测试、完整帧数学计分板、负对照、可追溯的局部 PPA 筛查。

硬件类型是 **FIR DSP/ASIC 研究 IP**，不是已经验证的 CNN 加速器。
1 ns 时钟、4 pixels/cycle 是目标；仿真中的持续吞吐不能证明硅片在 1 GHz 正确运行。

## 2. 当前结果：先看范围，再看数字

数值来自 2026-09-12 保存的实验；表中时间单位为 **ns**，没有沿用旧 ASAP7 项目的数值。

| 视图 | SS setup WNS | TT | FF | 结论 |
| --- | ---: | ---: | ---: | --- |
| v6 单 lane、零线延迟 | −1.43560 | −0.50995 | −0.01990 | 对照，不通过 |
| deep32 单 lane、零线延迟 | **+0.01081** | +0.32725 | +0.51341 | 仅该视图 setup 通过；FF hold **−0.00421** |
| one-hot credit 单 lane、早期布局 | −1.56332 | −0.62955 | −0.11615 | 相对对照有改善，仍不通过 |
| deep32 完整 FIR、内部 core 路径组、零线延迟 | **−1.85130** | −0.84005 | −0.26161 | 整体核心 setup 未闭合；外部接口未签核 |

固定 1 ns、setup/hold uncertainty **0.150/0.030 ns**。这些是研究预算，不是已经
characterize 的时钟/SRAM 签核契约。PVT：SS 0.9 V/125°C、TT 1.0 V/25°C、
FF 1.1 V/−40°C；尚无合格的逐角 RC 提取闭环。

deep32 单 lane 面积 938,416.95 µm²、SS vectorless power 0.615 W；
相比同轮 v6，分别约 **3.84× / 5.30×**。算术时序改善付出了明显代价，
因此没有把它直接升级为“最终物理实现”。这些数字不包括 SRAM/CTS，也不能乘 16 当整芯片 PPA。

| 完整候选功能回归 | 帧数 | 分量比较 | 错误 |
| --- | ---: | ---: | ---: |
| segmented | 134 | 6,125,564 | 0 |
| deep32 stalled | 134 | 5,914,672 | 0 |
| deep32 one-hot credit | 134 | 6,331,544 | 0 |

原始功能日志、负对照及数值摘要在 [results](experiments/fir_core_opt/results/)。
哈希验证不等于独立 STA；功能 PASS 也不等于时序 PASS。

发布前已从本新仓库独立重跑 one-hot credit：134帧、6,331,544次比较、0错误。
本次编译/仿真日志见 [publication verification](verification/publication/README.md)。

## 3. 五分钟入口：不需要 TSMC 库

支持 Linux / WSL2。先安装 Python 3、Icarus Verilog、Git；下面的公开单元验证不需要商业工具：

```bash
sudo apt-get update
sudo apt-get install -y git python3 iverilog
git clone https://github.com/stevenchen0830/fir-timing-lab.git
cd fir-timing-lab

python3 verification/reference_model.py
python3 experiments/fir_core_opt/verify_results.py
# 每次使用一个新输出目录；使用持久磁盘，不要把长实验放在 /tmp。
python3 tools/validate_public.py --out "$HOME/fir-runs/public-001"
```

预期得到 117 组有限架构交叉检查通过、`EVIDENCE_PASS` 和
`PUBLIC_TESTS_PASS`。中途任何测试失败均返回非零；信用状态破坏的负对照只有被断言检测到才算通过。

**完整帧复现**需要 Verilator、make 和 C++ 编译器。已验证版本 Verilator 5.050；
精确版本安装、quick/smoke/full 命令见 [复现指南](docs/reproduction.md)。

```bash
python3 experiments/fir_core_opt/run_frames.py \
  --variant deep32 --onehot-credit --suite full --engine verilator \
  --verilator /path/to/verilator \
  --out "$HOME/fir-runs/credit-full-001"
```

期望 134 frames、0 errors 和 `FRAME_FUNCTIONAL_PASS_NOT_STA`。
这是实际生成的完整 FIR 与 SRAM 行为模型的回归，不只是单个乘法器测试。

## 4. 两级复现承诺

| 层级 | 公共 clone 能做什么 | 额外条件 |
| --- | --- | --- |
| A：公开功能复现 | Python 模型、RTL 生成、Icarus 单元/负对照、Verilator 整帧、已有证据哈希 | 开源软件；无需 PDK |
| B：私有模型筛查 | 同一脚本重新综合、三 PVT 零线延迟 STA、单 lane 早期布局 | 使用者自行合法取得匹配 Liberty/LEF 和工具版本 |
| 尚不提供 | 最终 DRT → SPEF → MMMC、LVS、EM/IR、SRAM macro signoff | 缺少合格资产和完整闭合结果 |

不能同时“不公开受限工艺库”又保证所有人只靠匿名 clone 完成同工艺物理复现。
本仓库提供公开代码、明确的私有输入接口与哈希，**不会自动下载、伪造或绕过授权取得模型**。

## 5. 仓库地图

```text
rtl/                         冻结的 FIR 前端与定义（generator 校验哈希）
verification/                独立 Python 模型、原始自检帧 testbench
experiments/sram_multirate/   生成完整候选、事务队列、相关时钟边界、行为 SRAM
experiments/fir_core_opt/     分段/深流水/信用候选、运行器与历史验证证据
experiments/fir_pipeline/     结构缓冲工具及单元测试
flow/tsmc90/                  本项目自写的筛查配置元数据；没有库
tools/                       一键公开验证与发布边界检查
docs/                        架构、IC 流程、复现、验证、模型需求
.github/workflows/           轻量 CI；完整帧手动触发
```

顶层生成器未修改冻结前端；基线文件头中的旧延迟/接口描述不代表新候选。
新顶层接口和交易契约见 [architecture.md](docs/architecture.md)。

## 6. 下一步与不应宣称的内容

当前完整 FIR 最差路径是返回 ID 到事务完成标记的分发，而非已经拆开的局部算术。
应继续隔离完成译码、写入分发和输出流控，再比较完整候选面积/功耗/延迟；
只有满足晋级条件后才值得做 CTS、DRT 与新 SPEF。

尚未证明：所有合法输入的无界功能等价、完整 mapped LEC/SDF GLS、
真实 SRAM 命令/返回时序、全部未约束端点覆盖、最终 setup/hold/DRV 零违例、
匹配 RC corner、LVS/EM/IR。**不宣称全角 1 GHz，也不宣称 tapeout-ready。**

本项目延续 [vfir-7nm-rtl2gds](https://github.com/stevenchen0830/vfir-7nm-rtl2gds)
的设计研究，但此仓库单独保存 TSMC90 阶段的开放 RTL 实验，不重写旧项目历史。
原创开放代码采用 [MIT](LICENSE)；上游工具保留各自许可，见 [ATTRIBUTION.md](ATTRIBUTION.md)。
