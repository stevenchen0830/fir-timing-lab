# TSMC90 核心 setup 优化实验 · 2026-09-12

**局部算术通过三角零线延迟 setup；完整 FIR 仍未达到 1 GHz。**
没有降低频率/uncertainty，没有新增 MCP/false-path，没有修改历史 v4/v6。
所有候选独立生成；没有进入 CTS/DRT/RCX，没有把早期布局包装为签核。

## 1. 实际 RTL 修改

| 候选 | 结构变化 | MAC 延迟 |
| --- | --- | --- |
| v6 | 本轮重新映射的原始对照 | 9 个使能周期 |
| prefix | 显式前缀加法，减少串行进位 | 9 |
| segmented | 分段 carry-select，局部和/跨段进位拆开 | 20 |
| segmented_kept | 保留跨段进位乘积项，防止映射重新串行化 | 20 |
| segmented_mask | 独立寄存 tap enable 掩码，隔开使能与加法 | 21 |
| deep32 | 部分积 AND、局部和、跨段进位、选择分别寄存 | 32 |
| deep32 + credit | 自由运行 MAC + 64 深输出 FIFO，接收时预留槽位 | 固定流水 + 排队，非原先使能周期语义 |
| one-hot credit | 信用数/读写指针 one-hot 化，去掉双向计数进位链；平衡读选择树 | 同上 |

每个分量 lane 有 50 个 10×8 bit 乘法项。17 bit 中间结果依赖**非负系数、有效
总权重≤128** 的 FIR 契约：`1023×128+64=131008<2^17`，不是任意系数 MAC 的通用截位。
无阻塞时仍每周期接收一组 4 像素；增加的是延迟/状态，仿真吞吐不证明真实 1 GHz。

信用协议：`reserved=已接受−已消费`，包含流水中在途事务；`stored` 只表示 FIFO
中已有结果。先预留再发射，保证下游突然反压时，在途结果仍有存储空间。复位清除
信用/指针/valid，payload 不复位。容量、one-hot、溢出断言见 `mac_credit*.sv`。
没有把外部 ready 固定为 1。

## 2. 匹配条件与单 lane 筛查

Yosys `0.68+ a5af9d690`；OpenROAD `26Q3-1499-g46ab99414e`。
私有 TSMC90：SS 0.9 V/125°C，TT 1.0 V/25°C，FF 1.1 V/−40°C。
固定 period=1 ns，setup/hold uncertainty=**0.150/0.030 ns**，输入 max/min
0.100/0.050 ns，输出 max/min 0.100/−0.050 ns，输入 transition=0.100 ns，
输出 load=0.010 pF。这是**局部筛查预算，不是批准的真实 SRAM 接口预算**。

下表全部为 **一个分量 lane、寄存输入/输出、理想时钟、零线网寄生**：

| 跑次 | SS setup WNS/ns | TT/ns | FF/ns | 映射面积/µm² | SS vectorless power/W |
| --- | ---: | ---: | ---: | ---: | ---: |
| v6-remap | −1.43560 | −0.50995 | −0.01990 | 244,144.66 | 0.116 |
| prefix | −0.75141 | −0.10364 | +0.23914 | 389,947.72 | 见 JSON |
| segmented | −0.39176 | +0.07970 | +0.36342 | 554,816.10 | 0.328 |
| segmented-kept | −0.16384 | +0.24481 | +0.46255 | 574,101.56 | 见 JSON |
| segmented-mask-sized | −0.11460 | +0.25098 | +0.48160 | 597,896.51 | 见 JSON |
| deep32 | **+0.01081** | +0.32725 | +0.51341 | 938,416.95 | 0.615 |
| deep32-credit | −0.96031 | −0.25923 | +0.17588 | 643,517.78 | 0.423 |
| deep32-credit-onehot | −0.55670 | −0.03169 | +0.28412 | 655,038.82 | 0.426 |

deep32 三角 setup TNS=0，但 **FF hold WNS 仍是 −0.00421 ns**，不是全通过。
输入/进位单元尺寸调整另有连接和 Liberty 逻辑签名检查，不是完整 LEC。
旧 v6 历史面积为 244,529.91 µm²，本轮 v6-remap 为 244,144.66 µm²，不混用两次的
面积/TNS。最终参数化入口 `portable-v6` 重新得到与 `v6-remap` 相同的三角 WNS/TNS。

功耗统一 input/global activity=0.1、duty=0.5，是 vectorless 估算，不是匹配
VCD/SAIF 实测，也不包括 CTS/SRAM 宏。**不能乘以 16 当完整 FIR PPA**。
deep32 相对本轮 v6 约 3.84× 面积、5.30× 功耗，不满足直接晋级条件。

## 3. 早期布局：保留失败与否决结果

固定 core `[10,10,1610,1610] µm`、die `[0,0,1620,1620] µm`，GPL density=0.45、
seed=42、4 线程，IO M3 水平/M2 垂直。不同面积的实际利用率不同。流程为
placement → legalization → `estimate_parasitics -placement`，无 CTS/route。

RC 使用 tech LEF 的粗略、保守值。供应商明确只允许其用于早期 P&R，**不适用于
芯片级签核提取**。以下量级依赖这个模型，不能据此承诺最终 Fmax。

| 一 lane 布局跑次 | SS setup WNS/ns | TT/ns | FF/ns | 结论 |
| --- | ---: | ---: | ---: | --- |
| v6 | −2.57908 | −1.18841 | −0.43041 | 不通过 |
| deep32 | −2.45920 | −1.33361 | −0.67029 | 面积代价未换来足够收益 |
| deep32 + 一次 100 µm 线长/电气修复 | −4.82904 | −2.77323 | −1.61906 | 更差，拒绝晋级 |
| one-hot credit | −1.56332 | −0.62955 | −0.11615 | 有改善，仍不通过 |

deep32 最差路径是 `advance` 输入寄存器 → 四级缓冲 → MAC 触发器 E 端，而非
算术进位。再加流水会加重使能/时钟负担。信用方案消掉大 MAC stall 网络，但输出
存储/控制仍需优化，面积也高于基线。因此本轮没有启动长布线。

## 4. 完整 FIR：局部 PASS 不能替代整体

对 deep32 + 原 transaction queue + 原相关时钟边界另做完整层次综合，未应用
局部探针的 input/carry sizing。映射方式不同，不是局部表的同一网表。
全设计约 **2,675,389 个映射实例、25,656,499.41 µm² 标准单元面积**，包含
触发器化的缓冲数组和 fanout≤16 逻辑缓冲，不含外部 SRAM，不是物理布局面积。

完整网表的 `core` 路径组最差 setup 为 SS/TT/FF
**−1.85130 / −0.84005 / −0.26161 ns**。SS 路径由 `u_boundary.ret_id[14]`
到 `u_tx.done[1]`：返回 ID 译码与高扇出、多层缓冲耦合。下一轮应隔离完成标志
译码与大数据缓冲写入分发，不能认为 MAC 通过后这些路径自然通过。

这里仍是**零线延迟内部路径诊断**。没有编造 SRAM IO delay；相关时钟 IO、reset
coverage、全部未约束端点检查仍未签核。min 路径样本不能证明整体 hold PASS。
信用候选尚未重新做完整层次映射。

## 5. 功能、耗时与失败恢复证据

| 完整候选回归 | 帧数 | 分量比较 | 错误 |
| --- | ---: | ---: | ---: |
| segmented 20-cycle | 134 | 6,125,564 | 0 |
| deep32 stalled | 134 | 5,914,672 | 0 |
| deep32 one-hot credit | 134 | 6,331,544 | 0 |

均保留数学 golden、全部奇数 kernel、最小/最大测试宽度、奇数行长、随机反压、
运行中复位及持续输出无气泡断言。延迟 SRAM 行为模型不是批准的物理预算。
不同延迟会改变随机数消耗时序，比较次数不同不等于删减用例。

四种算术候选各通过 6000-cycle 独立四状态 MAC 检查；两个信用候选各通过
6200-cycle 独立事务计分板（长反压填满、5 个 reset、顺序、排空、无效 tap X）。
另外，故意把信用 one-hot 状态破坏为零的负对照触发 `CREDIT_ONEHOT_CORRUPTION`，
仿真以 exit 1 退出，runner 确认检测成功；它不是正常设计的失败。
原二进制信用版 Icarus 整帧编译近十分钟未完成，主动停止（终端记录）；
one-hot 整帧改用 Verilator。单元四状态测试与二状态整帧证据不互相替代。

deep32 局部综合约 60 s、STA 每角约 6 s；布局约 12–29 s。完整层次综合约
395 s，导出约 36 s/峰值约 10.1 GiB。首轮巨大寄存器集合路径查询在 180 s 超时，
复用网表改查 `core` 路径组后每角约 97–100 s/峰值约 9 GiB 完成。
旧 IO random 参数及错误的 M2/M3 方向在几秒内报错；修正后才形成有效布局。
没有回拨 mtime、重新清空历史结果或无限 repair。

首轮三个通过回归位于 WSL `/tmp`，环境重启后临时文件被清空，故首轮原始日志
不能作为当前可下载证据。随后迁到 `/home/ibex` 持久目录重跑同样三组用例；
`run_frames.py` 当时自动归档到本目录的 `results/<run>/`。
本独立仓库的便携入口已改成归档到每次输出目录的 `evidence/`，不改写历史证据。
当前证据以持久重跑的日志/哈希为准，而不是补写丢失日志。

## 6. 复现与证据边界

仓库根运行，输出目录必须全新：

```bash
python3 experiments/fir_core_opt/test_mac.py --variant deep32 --latency 32 --out /tmp/mac32-test
python3 experiments/fir_core_opt/test_credit.py --onehot --out /tmp/mac-credit-test
python3 experiments/fir_core_opt/test_credit.py --onehot --negative --out /tmp/mac-credit-negative
python3 experiments/fir_core_opt/run_frames.py --variant deep32 --suite full \
  --engine verilator --verilator /path/to/verilator --out /persistent/mac32-frames
python3 experiments/fir_core_opt/run_frames.py --variant deep32 --onehot-credit \
  --suite full --engine verilator --verilator /path/to/verilator --out /persistent/credit-frames

# Requires legally available matching private models and recorded exclusion list.
python3 experiments/fir_core_opt/run_probe.py --variant deep32 --input-cell DFFQX2 \
  --carry-sizing --models /private/tsmc90/models --exclude-cells /private/excludes.json \
  --yosys /path/to/yosys --openroad /path/to/openroad --out /private/mac32-screen
python3 experiments/fir_core_opt/run_placement.py --source /private/mac32-screen \
  --out /private/mac32-placement --timeout 420
python3 experiments/fir_core_opt/verify_results.py
```

`run_probe.py` 记录库/排除列表/源文件 hash、runner 快照，拒绝不匹配的 mapping cache。
需匹配工具版本，历史跑次以保存的 Tcl/SDC/Yosys 脚本为准。
本独立仓库已将工具路径和私有模型目录参数化，探针缓存同时校验工具二进制hash；
完整核入口默认使用core路径组查询。便携运行方法见 [复现指南](../../docs/reproduction.md)。
这些入口仍是诊断，不是完整签核流程；历史日志不因运行器重构而被改写。

公开数字：[screen_summary.json](results/screen_summary.json)。测试日志和汇总在
`results/`，由 [manifest.sha256](results/manifest.sha256) 覆盖。原始 STA 日志、
映射网表和厂商模型本地私有保留；公开摘要含原报告 SHA-256。**哈希校验不等于独立 STA**。

最终晋级仍受内部 setup、面积/功耗、真实 SRAM 时序与合格物理资产阻塞。
不混用 ASAP7/TSMC90，不虚构 RCX，不宣称全角 1 GHz 或零违例。
