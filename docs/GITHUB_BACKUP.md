# GitHub 完整交付备份

GitHub 私有仓库：https://github.com/liuyang12-bb/CAPRA

本仓库保存CAPRA独立工程源码、固定官方上游快照、依赖锁、独立数据、全部本阶段实验结果、原始日志、验证结果及报告。保留实验负收益和场景差异，没有把旧MELD结果加入本轮比较。

## 存放位置

- 算法源码：`src/capra/`；第一阶段`gpu_stage.py`，第二阶段`tune.py`，执行语义`execution.py`。
- 官方上游源码与原许可证：`third_party/`；版本和适配补丁：`docs/upstream_versions.json`、`docs/sia_upstream.patch`。
- 画像、输入与来源：`data/`；冻结集群及六格清单：`configs/`。
- 主实验完整目录：`runs/main_v1/`；六个单元分别位于`saturn-2-supported80/`与`saturn-6-supported80/`下的`SIA-P/`、`CAPRA-Fixed/`、`CAPRA/`。
- 原始轮次事件：每单元`events.jsonl.gz`；控制台日志为单元目录旁的`方法名.stdout.log`。
- 结果主表：`runs/main_v1/results.csv`；逐作业数据：各单元`per_job.csv`及总表`paired_jobs.csv`。
- 资源、审计、命令：各单元`node_resources.csv`、`process.json`及各类hash文件；全局`deep_audit.json`、`final_verification.json`、`evidence_hashes.json`。
- 精确运行源码归档：`runs/main_v1/frozen_execution_source.zip`，SHA256 `8457c139bbb7c4c4c6c4140c66cef66567729ed165612319a131f49259c23bdf`。
- 小验证、controlled机制例、Sia smoke和短pilot：`runs/validation/`，包含原始日志。
- 阶段报告：`docs/STAGE_REPORT.md`；方法定义：`docs/DESIGN.md`；安装与复现命令：`README.md`。

`.venv`、依赖下载缓存、临时文件和官方克隆的Git数据库不属于源码/实验结果，不上传；使用`requirements.lock.txt`和README重建CAPRA专属环境。仓库本身保留全部必要上游源文件，不需要旧项目目录。

`docs/github_upload_manifest.json`列出本次交付文件的大小与SHA256（不包含清单自身），用于远端树覆盖核对。首次上传使用普通Git提交和推送，不覆盖旧Sia仓库、不强推。
