# CAPRA

Configuration-Aware Placement and Resource Allocation（配置感知的任务放置与资源分配）。独立的 Sia + Synergy-TUNE 思路整合；不依赖旧 MELD 目录。

第一阶段直接使用官方 Sia goodput MIP、吞吐投影、在线画像和批大小规则。第二阶段固定 GPU 集合/类型/数量/单节点shape，协调节点、CPU和主机RAM。仅比较 SIA-P、CAPRA-Fixed、CAPRA；Fixed/free共用辅助分配实现。

当前支持异构GPU、每类多个节点、数据并行、单作业单节点。默认aws两台4GPU/12CPU/250GB，dgx-ext和rtx各两台8GPU/24CPU/500GB，共40GPU。响应是有来源、假设明确的合成模板转移，不声称实机验证。

## 环境与命令

在本工程根目录PowerShell执行。Python 3.10；环境属于CAPRA。已交付的`.venv`可直接运行。重建环境时将pip缓存和临时目录限定在本工程，启用UTF-8避免中文路径pth编码问题：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:TMP="$PWD\.cache\tmp"
$env:TEMP=$env:TMP
$env:PIP_CACHE_DIR="$PWD\.cache\pip"
New-Item -ItemType Directory -Force .cache/tmp,.cache/pip | Out-Null
# 仅在没有CAPRA环境时创建；pyvenv.cfg允许引用通用Python安装，不引用旧工程环境
python -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install setuptools==75.8.0 wheel==0.45.1
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -X utf8 -m pip install --no-build-isolation -e .
.\.venv\Scripts\python.exe -X utf8 -B scripts/check_small.py
```

上游源码、画像与两份派生负载已vendored，无须下载旧项目或再次生成数据。`scripts/bootstrap_sources.py`是本次获取后的单次补丁记录器，不是常规安装步骤。上游差异与许可边界见[设计](docs/DESIGN.md)。

可复制的单格复现实验（输出必须是不存在的新目录）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/one_cell.py --input data/saturn-2-supported80.csv --method CAPRA --output runs/reproduction-01/CAPRA --max-rounds 6000 --wall-limit 900
.\.venv\Scripts\python.exe -X utf8 -B -m capra.audit runs/reproduction-01/CAPRA
```

本轮六格由`configs/experiment_manifest.json`预登记，`scripts/run_matrix.py`按冻结顺序运行；已有主结果时不得原地重跑。若复现全矩阵，先独立另命名run目录和manifest，不改历史记录。

## 文件入口

- `src/capra/gpu_stage.py`：原Sia GPU接口和共同物理锁可行性处理。
- `src/capra/tune.py`：Fixed/free共用的第二阶段。
- `src/capra/contracts.py`、`execution.py`：完整集合、容量、锁和节点身份迁移提交。
- `src/capra/response.py`：公开模板映射、归一化响应。
- `src/capra/runner.py`、`audit.py`：真实推进、原始事件及独立复算。
- `docs/upstream_versions.json`、`sia_upstream.patch`、`DESIGN.md`：来源和适配。
- `data/provenance.json`：原始行号、选择规则、输入哈希。
- `runs/validation/`：必要检查、互补例、Sia smoke、短pilot。
- `runs/main_v1/`：限定六格原始输出、首份负载小表与结果表。

JCT=完成时刻−原到达；未完成时整体平均/P95/P99/makespan留空。完整决策开销单独报告，不额外扣进模拟时间。迁移、恢复、checkpoint代价实际扣时；CPU/RAM倍率只作用训练一次。详细实验结论见`docs/STAGE_REPORT.md`（完成汇总后生成）。

用户明确要求备份后，工程上传至私有仓库[liuyang12-bb/CAPRA](https://github.com/liuyang12-bb/CAPRA)。完整目录说明见[GitHub备份位置](docs/GITHUB_BACKUP.md)。不自动扩展实验或以旧结果作为CAPRA结果。

交付时`runs/main_v1/frozen_execution_source.zip`保存冻结运行源码、输入和manifest的精确字节，内部逐文件哈希核对。`.gitattributes`关闭本工程的自动换行转换；本地最终提交保存实际运行字节。补充审计命令为`python -X utf8 -B scripts/deep_audit.py`，只读原始输出，不重新调度。

## CAPRA v2 本地交付

新版在`capra/v2-20261122`分支，尚未推送。方法见[CAPRA_V2_DESIGN](docs/CAPRA_V2_DESIGN.md)，结果见[CAPRA_V2_RESULTS](docs/CAPRA_V2_RESULTS.md)。运行入口为`python -X utf8 -B -m capra.runner_v2`；依赖锁为`requirements_v2.lock.txt`。六格原始输出位于`runs/capra_v2/CAPRA_V2_R1`，冻结清单为`configs/experiment_manifest_v2.json`。原v1命令/结果与旧manifest保留；不同版本结果不要拼表。
