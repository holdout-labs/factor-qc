# factor-qc

![PyPI version](https://img.shields.io/pypi/v/factor-qc.svg)
![PyPI downloads](https://img.shields.io/pypi/dm/factor-qc.svg)
![CI](https://github.com/holdout-labs/factor-qc/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

> 收录于 [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) —— 量化库精选清单（Factor Analysis 板块）。

## 中文说明

`factor-qc` 是一个面向量化回测的质量闸门，也适用于 A 股因子研究。
它把 DSR、PBO、Harvey-Liu 多重检验折减和 MinTRL 放在同一次检查中，
并要求明确填写尝试过的参数组合数量。数据不完整或指标未达到门槛时，
工具会给出分级结果并默认不放行；它不保证策略盈利，也不会替研究者选择因子。

面向回测的**默认不放行（fail-closed）质量闸门**：一个仅依赖 numpy 的引擎，
涵盖平减夏普比率（Deflated Sharpe Ratio）、回测过拟合概率（Probability of
Backtest Overfitting，CSCV）、Harvey-Liu 多重检验折减（haircut）和最小业绩
记录长度（Minimum Track Record Length）——按 P0/P1/P2 分级，并且**它拒绝
评判不肯声明尝试过多少组配置的回测**。Python 3.11+，仅一个依赖（`numpy`），
支持 Windows / Linux / macOS。

**状态：** v0.1.3 alpha，已发布到 PyPI。这些统计量在生产研究流水线中经过
实战检验，并对照已发表的参考值验证过，但这个独立包是新的：v1.0 之前 CLI
可能会变动。

## 为什么存在这个项目

标准故事：你尝试了 200 组因子配置，最好的那组夏普比率达到 1.65，你感觉良好。
诚实的故事：在 200 次纯粹噪声的试验中，*总会有人* 拿到 1.65 的夏普比率——
这是 200 次真实夏普比率为零的试验的期望最大值——那不是你的本事，而是你的
选择偏差（selection bias）。

大多数回测工具只是计算统计量并打印报告。`factor-qc` 是一道**闸门（gate）**：
它以分级的严重程度决定候选是否可以通过——而它的默认答案是*不*：

- **P0（致命）** ——DSR 低于阈值、PBO 高于阈值、折减后夏普比率低于底线、
  MinTRL 长于样本 -> 候选不得通过。
- **P1（警告）** ——相对零的 PSR 较弱、样本较短、试验次数过于激进 -> 可以
  继续，但要睁大眼睛。
- **P2（信息）** ——矩非正态、试验次数极少 -> 仅记录，不采取行动。

## 理念

**诚实是默认原则；闸门默认不放行（fail-closed）。**

唯一不可讨价还价的输入是 `n_trials`：你实际尝试过的配置数量的诚实计数。
没有它，就没有平减基准（[Bailey & López de Prado 2014](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)）、
没有折减（[Harvey, Liu & Zhu 2016, RFS](https://doi.org/10.1093/rfs/hhv059)）、
没有业绩记录底线（[Bailey & López de Prado 2012, JPM 39(1)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643)）、
也没有过拟合概率（[Bailey, Borwein, López de Prado & Zhu 2017, JCF](https://escholarship.org/uc/item/4w1110bb)）。
拒绝申报，闸门就拒绝评判——这种不对称正是关键所在。`qc check` 在出现任何
P0 失败时以非零码退出，因此它可以作为硬性拦截器（hard blocker）而非建议，
接入 CI、pre-commit 钩子和研究闸门。

两项让工具保持诚实的设计承诺：

1. **只用 numpy，不用 scipy** ——标准正态逆 CDF 采用 Acklam 有理近似加一次
   Newton 精化；报告中的每一个数字都可以用本仓库中的代码复现，没有隐藏的黑箱。
2. **PBO 可选但必须显式声明** ——没有试验矩阵时，闸门会说明 PBO *未计算*，
   DSR 的跨试验方差则退化为保守的单试验估计。证据缺失会被如实报告为缺失，
   而绝不会被当作证据。

## 快速开始

```bash
# install the published package from PyPI
pip install factor-qc

# or run without installing anything:
#   PYTHONPATH=src python -m factor_qc --help

python examples/demo.py   # try it on reproducible synthetic cases
```

你自己的回测：

```bash
# returns.json = JSON list of per-period returns of the selected candidate
# trials.json   = JSON 2D matrix (T x N) of every configuration you tried

qc check --returns returns.json --trials trials.json --n-trials 200
# -> FAIL - P0 blocker(s): dsr: 0.63 vs 0.95; mintrl: 250.8 vs <= 1000; ...

qc check --returns returns.json --n-trials 5 --json   # machine-readable
```

退出码：`0` = 无 P0 失败（P1/P2 仍可能有失败项），`1` = 至少一个 P0 失败
（或缺少 `n_trials`），`2` = 用法错误。把它作为硬性闸门接入 CI。

## 命令

| 命令 | 作用 |
| --- | --- |
| `check` | 运行闸门：DSR、PBO（当提供 `--trials` 时）、折减后夏普比率、MinTRL 作为 P0；相对零的 PSR、样本长度、试验激进程度作为 P1；矩与试验次数作为 P2。人类可读或 `--json` 输出 |
| `version` | 打印版本号 |

参数：`--returns`（必填）、`--trials`（可选）、`--n-trials`（必填，除非在
代码中禁用了 `require_declared_trials`）、`--periods-per-year`（默认 252）、
`--n-blocks`（CSCV 粒度，默认 16）。

## 各项检查

| 检查项 | 严重程度 | 方法 | 参考文献 |
| --- | --- | --- | --- |
| `dsr` | P0 | 平减夏普比率（Deflated Sharpe Ratio）：非正态矩下 P(SR > E[max SR of N trials]) | [Bailey & López de Prado (2014), JPM 40(5)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) |
| `pbo` | P0 | 回测过拟合概率：组合对称交叉验证（Combinatorially-Symmetric Cross-Validation，CSCV）（n_blocks=16 时为 12,870 个划分） | [Bailey, Borwein, López de Prado & Zhu (2017), JCF](https://escholarship.org/uc/item/4w1110bb) |
| `haircut_sharpe` | P0 | 夏普比率的多重检验折减（Bonferroni/Holm/BHY） | [Harvey & Liu (2015), "Backtesting"](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489) |
| `mintrl` | P0 | 最小业绩记录长度（Minimum Track Record Length）：SR 显著之前所需的观测数 | [Bailey & López de Prado (2012), JPM 39(1)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643) |
| `psr_vs_zero` | P1 | 相对零的概率夏普比率（Probabilistic Sharpe Ratio） | [Bailey & López de Prado (2012), JPM 39(1)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643) |
| `sample_length` | P1 | ≥252 个观测值 | — |
| `trial_aggression` | P1 | n_trials ≥ n_obs / 5 | — |
| `return_moments` | P2 | skew ≥0, kurtosis ≥3 | — |
| `trial_count` | P2 | n_trials ≥5 | — |

P0 组与 [Harvey, Liu & Zhu (2016), "“And the Cross-Section of Expected Returns"](https://doi.org/10.1093/rfs/hhv059)
的精神一脉相承：一个因子必须经受住多重检验校正，才有资格被称为因子。这道闸门
就是那种编辑部立场的机器化版本。

## 性能说明

CSCV 会枚举 C(n_blocks, n_blocks/2) 个划分——默认 16 时为 12,870 个。对于大型
试验矩阵（T=1000, N=200），这需要几分钟；可以使用 `--n-blocks 8`（70 个划分）
或 `10`（252 个划分）来获得交互式速度，代价是粒度略粗。

## 开发

```bash
python -m pip install -e . pytest
python -m pytest
```

CI 在 Ubuntu、Windows 和 macOS 上以 Python 3.11 和 3.12 运行完整测试套件。
问题（issues）在周末处理；欢迎提交拉取请求（pull request）。

## 相关工作

- [Bailey & López de Prado (2014), The Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
- [Bailey, Borwein, López de Prado & Zhu (2017), The Probability of Backtest Overfitting](https://escholarship.org/uc/item/4w1110bb)
- [Harvey, Liu & Zhu (2016), “And the Cross-Section of Expected Returns (RFS)](https://doi.org/10.1093/rfs/hhv059)
- [Harvey & Liu (2021), Lucky Factors (JFE)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2528780)
- [Mobarekeh & López de Prado (2024), Backtest Overfitting in the Machine Learning Era (SSRN 4778909)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4778909) ——为什么 OOS（样本外，out-of-sample）方法仍然需要诚实的试验记账

## 项目家族

[Holdout](https://github.com/holdout-labs) 的组成部分——一个对抗量化研究中
自欺欺人的工具链：

- [pit-adjuster](https://github.com/holdout-labs/pit-adjuster) ——PIT（时点，point-in-time）后复权调整，带静态前复权（forward-adjustment）漂移检测
- [falsification-ledger](https://github.com/holdout-labs/falsification-ledger) ——预注册与证伪账本
- [factor-qc](https://github.com/holdout-labs/factor-qc) ——默认不放行（fail-closed）的回测质量闸门
- [lesson-book](https://github.com/holdout-labs/lesson-book) ——交易者的学费记忆
- [lookahead-free](https://github.com/holdout-labs/lookahead-free) ——可验证的无前视（look-ahead）检查
- [ashare-data-immunity](https://github.com/holdout-labs/ashare-data-immunity) ——A 股日线数据免疫

姊妹组织：[Metabolism Tools](https://github.com/metabolism-tools) ——
[`workspace-metabolism`](https://github.com/metabolism-tools/workspace-metabolism)，
面向智能体工作区（agentic workspaces）的、由策略驱动的文件生命周期管理。

## 许可证

MIT
