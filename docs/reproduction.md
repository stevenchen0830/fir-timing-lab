# Reproduction runbook

以下从新 clone 开始。A 路线完全公开；B 路线需要自行取得授权的私有模型。
所有输出目录必须全新，以避免 make 旧目标或旧结果被误当成本次结果。

## 0. 环境和版本

Linux / WSL2，Python 3.10+。原始记录为 Icarus 11、Verilator 5.050、
Yosys 0.68+（a5af9d690）、OpenROAD 26Q3-1499（46ab99414e）。
不同版本可重新测试，但不能不经检查就把它们当作数值完全一致的复现。

```bash
sudo apt-get update
sudo apt-get install -y git python3 iverilog make g++ time
git clone https://github.com/stevenchen0830/fir-timing-lab.git
cd fir-timing-lab
python3 --version
iverilog -V
git rev-parse HEAD
```

完整帧推荐 Verilator；Icarus 对巨大展开 MAC 的整帧编译可能非常慢，但适合小规模
四状态测试。可以先用发行版的 Verilator 运行 quick 检查；若需要匹配记录版本：

```bash
sudo apt-get install -y autoconf flex bison help2man perl
git clone --branch v5.050 --depth 1 https://github.com/verilator/verilator.git "$HOME/verilator-5.050-src"
cd "$HOME/verilator-5.050-src"
autoconf
./configure --prefix="$HOME/.local/verilator-5.050"
make -j2
make install
"$HOME/.local/verilator-5.050/bin/verilator" --version
# 返回你刚才 clone 的 fir-timing-lab 目录后执行下文。
```

上述安装由使用者执行，不需要提供任何 GitHub 密钥。工具构建说明以
[Verilator 官方文档](https://verilator.org/guide/latest/install.html)为准。
使用者自己的二进制位置通过 --verilator / --yosys / --openroad 指定，脚本不依赖 /root/ORFS。

## 1. 数学、单元和已有证据

在仓库根目录：

```bash
python3 tools/validate_public.py --out "$HOME/fir-runs/public-001"
python3 tools/check_public_tree.py
```

第一个命令依次执行117组有限架构交叉检查、31文件历史证据hash、结构缓冲单元测试、
6000周期deep32 MAC、6200周期one-hot信用正对照、破坏信用状态的负对照。

输出目录包含各步骤 log、总 summary.json 及单元测试源码/编译日志。
正对照失败或负对照没有触发预期断言，runner 返回非零。详见[验证说明](verification.md)。

## 2. 生成完整 RTL（无需 PDK）

frame runner会自动生成源码。只想看硬件而不运行回归：

```bash
python3 tools/generate_rtl.py --variant deep32 --onehot-credit \
  --out "$HOME/fir-runs/generated-credit-001"
```

输出 top.sv、替换的 MAC、队列/相关时钟RTL、defines、rtl.f 与 source_manifest.json。
顶层 IMG_FILTER；filelist含绝对生成路径，移动后请重新生成。
该入口和 run_frames 共享同一个 snapshot 函数，避免展示RTL与回归RTL分叉。

生成器校验冻结的 rtl/img_filter.v hash。不要为了“运行成功”绕过这个检查；
应更新生成规则、回归并建立新证据。候选不是直接手工修改历史 baseline。

## 3. 从少量帧到完整帧

```bash
python3 experiments/fir_core_opt/run_frames.py --variant deep32 --onehot-credit \
  --suite quick --engine verilator \
  --verilator "$HOME/.local/verilator-5.050/bin/verilator" \
  --out "$HOME/fir-runs/credit-quick-001"

# full: 134 frames；smoke: 13 frames；quick: 1 frame
python3 experiments/fir_core_opt/run_frames.py --variant deep32 --onehot-credit \
  --suite full --engine verilator \
  --verilator "$HOME/.local/verilator-5.050/bin/verilator" \
  --out "$HOME/fir-runs/credit-full-001"

# 分别重现另外两个候选；每次使用新的输出目录。
python3 experiments/fir_core_opt/run_frames.py --variant segmented --suite full \
  --engine verilator --out "$HOME/fir-runs/segmented-full-001"
python3 experiments/fir_core_opt/run_frames.py --variant deep32 --suite full \
  --engine verilator --out "$HOME/fir-runs/stalled-full-001"
```

最后两条默认从PATH找verilator；必要时同样传 --verilator。
完整结果要求 summary.status=FRAME_FUNCTIONAL_PASS_NOT_STA、frames=134、errors=0，
同时 compile 和 frames 两个子命令均正常退出并有 TEST PASSED。

每次运行保存：

```text
<out>/
  source/                 精确源文件快照
  source_manifest.json    原始和生成源文件hash
  run/                    生成顶层/testbench、编译物、compile.log、frames.log、summary
  evidence/               退出前归档summary、frames.log、source_manifest
```

新运行不写入仓库的历史 results。历史日志中的 /root、/home 或 Windows 路径仅是
当时运行的位置，不是本次输入要求。两状态 Verilator不能替代四状态Icarus测试。

## 4. 私有综合与零线延迟 STA

先读[私有模型契约](private-models.md)，确认工具版本和文件hash。不要把模型放入 clone。

```bash
# 使用有授权的本地安装；本仓库不下载模型。
export YOSYS=/path/to/yosys
export OPENROAD=/path/to/openroad

python3 experiments/fir_core_opt/run_probe.py --variant v6 \
  --models /private/tsmc90/models --out /private/fir-runs/v6-001

python3 experiments/fir_core_opt/run_probe.py --variant deep32 \
  --input-cell DFFQX2 --carry-sizing \
  --models /private/tsmc90/models --out /private/fir-runs/deep32-001

python3 experiments/fir_core_opt/run_probe.py --variant deep32 --onehot-credit \
  --input-cell DFFQX2 --carry-sizing \
  --models /private/tsmc90/models --out /private/fir-runs/credit-001
```

输出路径不允许空格，避免Tcl/Yosys路径歧义。默认排除列表在 flow/tsmc90/excluded_cells.json。
--reuse-mapped 只接受相同DUT、库、映射选项、排除列表、工具可执行文件hash；
它不是跨版本通用缓存。输出中记录生成的 synth.ys、SDC/Tcl、模型hash、
映射网表、工具身份、stages.json、summary.json。**这些私有输出不要推送。**

退出码0只表示 SCREEN_COMPLETE_NOT_PHYSICAL_CLOSURE，不是WNS通过。
评估需同时读取 setup/hold、范围、功耗活动、面积和接口假设；不要仅检查exitcode。

## 5. 同条件早期布局

```bash
python3 experiments/fir_core_opt/run_placement.py \
  --source /private/fir-runs/v6-001 --out /private/fir-runs/v6-place-001
python3 experiments/fir_core_opt/run_placement.py \
  --source /private/fir-runs/deep32-001 --out /private/fir-runs/deep32-place-001
python3 experiments/fir_core_opt/run_placement.py \
  --source /private/fir-runs/credit-001 --out /private/fir-runs/credit-place-001
```

固定core/die、density=.45、seed42、4线程、IO层和原探针SDC。面积不同会改变实际利用率，
所以不是“相同利用率”实验。生成 floorplan.odb/global_place.odb/placed.odb、
placed.def和每角诊断。无CTS/DRT/SPEF；tech LEF粗RC不能作为签核RC规则。

--condition-wires 仅重现那次被否决的100µm线长修复实验，不建议默认启用；
历史结果更差，保留它是为了可证伪性，不是把它当优化成功。

## 6. 完整 core 子集筛查（较重，可选）

```bash
python3 experiments/fir_core_opt/run_full_core.py --variant deep32 \
  --models /private/tsmc90/models --out /private/fir-runs/full-core-001 \
  --timeout 600
```

层次映射、不做单lane input/carry sizing；该入口仍是 stalled deep32，不是one-hot信用完整映射。
只报告 core 路径组。外部SRAM IO没有被赋予虚构budget，覆盖保持UNKNOWN。
默认使用path-group查询，避免原来巨大的all_registers集合查询超时。

如果已经有 mapped.v 和 slow.tcl，仅STA失败，可新建报告目录复用它们：

```bash
python3 experiments/fir_core_opt/resume_core_sta.py \
  --source /private/fir-runs/full-core-001 \
  --out /private/fir-runs/full-core-resta-001
```

这不是自动恢复任意物理阶段。placement脚本每次重新建自己的单lane布局，
保留ODB供人工诊断；当前没有提供“继续到最终DRT”的合格实现入口。

## 7. 时间、内存与恢复

历史本机量级，**不是对他人机器的承诺**：

| 工作 | 已观测量级 | 预算 / 恢复 |
| --- | --- | --- |
| Python与hash | 秒级 | 失败先检查文件，不改历史hash绕过 |
| 单lane四状态 | 每项几十秒量级 | compile/run各180s上限 |
| 整帧Verilator | 编译+仿真数分钟；受机器影响 | 各阶段900s；父runner1900s |
| deep32单lane综合/STA | ~60s + 每角~6s | synth600s、STA120s |
| 单laneplacement | ~12–29s | 默认420s；不无限repair |
| 完整FIR综合/导出 | ~395s/~36s，导出峰值~10.1GiB | synth600s、export180s |
| 完整core每角STA | ~97–100s，峰值~9GiB | 默认180s；路径组查询 |

建议重流程至少16GiB可用内存，避免同时运行多个完整综合。依赖与系统开销另计。
使用本地Linux持久SSD目录可避免 /mnt/c 慢IO；/tmp可能随WSL环境消失。

超时保留日志和已写盘检查点，只终止该runner自己的进程组。**内存中的未写盘修复不可恢复**。
停止整帧仿真后默认从该候选的回归开头再跑，没有虚构逐帧断点。重新运行用新目录；
不要回拨mtime、删除基线或清空所有历史输出。

