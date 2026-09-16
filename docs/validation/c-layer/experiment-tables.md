# C 层逐实验与逐功能结果表

由 `tools/validation/summarize_c_layer.py` 根据 results.json 生成；结果对应 2026-09-07 快照。
每项检查保留原始预期、实际、误差及证据类型。表内一个实验可有多项检查；实验数不能解释为独立用户样本数。

## 逐实验结果

| 实验 | 场景 | 一致 / 尾差 / 差异检查数 | 结果 | 差异备注 |
|---|---|---|---|---|
| C-LP-01 | 普通双燃料 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-02 | 候选同能源更便宜 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-03 | 候选吨价高但同能源便宜 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-04 | 最大混兑上限 | 19 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-05 | 供应上限 | 17 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-06 | 增量预算上限 | 17 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-07 | 三个约束同时施加 | 17 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-08 | 零供应 | 19 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-09 | 零预算且成本增加 | 19 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-10 | 零预算且成本下降 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-11 | 双方均不达标 | 19 / 0 / 0 | MATCH | — |
| C-LP-12 | 虽改善但仍无数学解 | 19 / 0 / 0 | MATCH | — |
| C-LP-13 | B0已达标且候选更差更便宜 | 21 / 0 / 1 | DIFFERENCE | 达标成本最优点或建议未满足目标 |
| C-LP-14 | B0已达标且候选继续改善 | 22 / 0 / 0 | MATCH | — |
| C-LP-15 | 候选端点恰好达标 | 22 / 0 / 0 | MATCH | — |
| C-LP-16 | 目标恰好等于混兑上限 | 22 / 0 / 0 | MATCH | — |
| C-LP-17 | 目标高于混兑上限1e-20 | 16 / 2 / 2 | DIFFERENCE | SOLVER 精度不足；生产目标状态与精确参考一致 |
| C-LP-18 | 目标低于混兑上限1e-20 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-19 | RWD=2分式目标 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-20 | RWD回退后的普通分母 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-21 | 缺候选价格且有预算 | 16 / 0 / 0 | MATCH | — |
| C-LP-22 | 缺EUA价格且有预算 | 16 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-23 | 2024 FuelEU不适用 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-24 | 2025 CO2-only | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-25 | 2030目标 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-26 | 范围为零 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-LP-27 | 成本和GHGI均并列 | 19 / 0 / 0 | MATCH | — |
| C-LP-28 | 甲烷设备滑移与三气体 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-01 | 固定种子合成案例 | 20 / 1 / 1 | DIFFERENCE | 达标成本最优点或建议未满足目标 |
| C-RND-02 | 固定种子合成案例 | 17 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-03 | 固定种子合成案例 | 22 / 0 / 0 | MATCH | — |
| C-RND-04 | 固定种子合成案例 | 21 / 0 / 1 | DIFFERENCE | 达标成本最优点或建议未满足目标 |
| C-RND-05 | 固定种子合成案例 | 21 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-06 | 固定种子合成案例 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-07 | 固定种子合成案例 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-08 | 固定种子合成案例 | 21 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-09 | 固定种子合成案例 | 22 / 0 / 0 | MATCH | — |
| C-RND-10 | 固定种子合成案例 | 20 / 1 / 1 | DIFFERENCE | 达标成本最优点或建议未满足目标 |
| C-RND-11 | 固定种子合成案例 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-12 | 固定种子合成案例 | 19 / 0 / 0 | MATCH | — |
| C-RND-13 | 固定种子合成案例 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-14 | 固定种子合成案例 | 22 / 0 / 0 | MATCH | — |
| C-RND-15 | 固定种子合成案例 | 19 / 0 / 0 | MATCH | — |
| C-RND-16 | 固定种子合成案例 | 19 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-17 | 固定种子合成案例 | 20 / 1 / 1 | DIFFERENCE | 达标成本最优点或建议未满足目标 |
| C-RND-18 | 固定种子合成案例 | 19 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-19 | 固定种子合成案例 | 17 / 5 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-20 | 固定种子合成案例 | 20 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-21 | 固定种子合成案例 | 19 / 0 / 0 | MATCH | — |
| C-RND-22 | 固定种子合成案例 | 18 / 4 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-23 | 固定种子合成案例 | 19 / 0 / 0 | MATCH | — |
| C-RND-24 | 固定种子合成案例 | 19 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-25 | 固定种子合成案例 | 17 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-26 | 固定种子合成案例 | 22 / 0 / 0 | MATCH | — |
| C-RND-27 | 固定种子合成案例 | 19 / 0 / 0 | MATCH | — |
| C-RND-28 | 固定种子合成案例 | 19 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-29 | 固定种子合成案例 | 20 / 1 / 1 | DIFFERENCE | 达标成本最优点或建议未满足目标 |
| C-RND-30 | 固定种子合成案例 | 22 / 0 / 0 | MATCH | — |
| C-RND-31 | 固定种子合成案例 | 17 / 3 / 0 | MATCH_WITH_ROUNDING | — |
| C-RND-32 | 固定种子合成案例 | 22 / 0 / 0 | MATCH | — |
| C-EC-01 | 普通双燃料 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-02 | 候选同能源更便宜 | 11 / 0 / 0 | MATCH | — |
| C-EC-03 | 候选吨价高但同能源便宜 | 11 / 0 / 0 | MATCH | — |
| C-EC-04 | 最大混兑上限 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-05 | 供应上限 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-06 | 增量预算上限 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-07 | 三个约束同时施加 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-08 | 零供应 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-09 | 零预算且成本增加 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-10 | 零预算且成本下降 | 11 / 0 / 0 | MATCH | — |
| C-EC-11 | 双方均不达标 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-12 | 虽改善但仍无数学解 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-13 | B0已达标且候选更差更便宜 | 11 / 0 / 0 | MATCH | — |
| C-EC-14 | B0已达标且候选继续改善 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-15 | 候选端点恰好达标 | 11 / 0 / 0 | MATCH | — |
| C-EC-16 | 目标恰好等于混兑上限 | 14 / 0 / 0 | MATCH | — |
| C-EC-17 | 目标高于混兑上限1e-20 | 14 / 0 / 0 | MATCH | — |
| C-EC-18 | 目标低于混兑上限1e-20 | 14 / 0 / 0 | MATCH | — |
| C-EC-19 | RWD=2分式目标 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-20 | RWD回退后的普通分母 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-21 | 缺候选价格且有预算 | 1 / 0 / 0 | MATCH | — |
| C-EC-22 | 缺EUA价格且有预算 | 1 / 0 / 0 | MATCH | — |
| C-EC-23 | 2024 FuelEU不适用 | 14 / 0 / 0 | MATCH | — |
| C-EC-24 | 2025 CO2-only | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-25 | 2030目标 | 13 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-26 | 范围为零 | 9 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-EC-27 | 成本和GHGI均并列 | 11 / 0 / 0 | MATCH | — |
| C-EC-28 | 甲烷设备滑移与三气体 | 10 / 1 / 0 | MATCH_WITH_ROUNDING | — |
| C-ENV-01 | 单次切换与支配交点 | 6 / 0 / 0 | MATCH | — |
| C-ENV-02 | 两次有效切换 | 10 / 0 / 0 | MATCH | — |
| C-ENV-03 | 全平行 | 2 / 0 / 0 | MATCH | — |
| C-ENV-04 | 全重合 | 2 / 0 / 0 | MATCH | — |
| C-ENV-05 | 零价值交点 | 6 / 0 / 0 | MATCH | — |
| C-ENV-06 | 仅负交点 | 2 / 0 / 0 | MATCH | — |
| C-ENV-07 | 极近交点1e-31 | 2 / 0 / 4 | DIFFERENCE | 2个极近切换点合并为1个 |
| C-ENV-08 | 改善为负 | 6 / 0 / 0 | MATCH | — |
| C-CASE-01 | 普通双燃料 | 47 / 11 / 5 | DIFFERENCE | 约1e-49 t余额的严格符号差异；不按大额经济误差解释 |
| C-CASE-02 | 候选同能源更便宜 | 51 / 18 / 0 | MATCH_WITH_ROUNDING | — |
| C-CASE-03 | 三个约束同时施加 | 53 / 11 / 2 | DIFFERENCE | 约1e-49 t余额的严格符号差异；不按大额经济误差解释 |
| C-CASE-04 | B0已达标且候选更差更便宜 | 47 / 0 / 2 | DIFFERENCE | 达标成本最优点或建议未满足目标 |
| C-CASE-05 | 目标恰好等于混兑上限 | 55 / 0 / 0 | MATCH | — |
| C-CASE-06 | RWD=2分式目标 | 60 / 9 / 3 | DIFFERENCE | 约1e-49 t余额的严格符号差异；不按大额经济误差解释 |
| C-CASE-07 | 缺候选价格且有预算 | 44 / 0 / 0 | MATCH | — |
| C-CASE-08 | 成本和GHGI均并列 | 44 / 0 / 0 | MATCH | — |
| C-VALUE-01 | 合规参考价值不改变默认成本排序 | 3 / 2 / 0 | MATCH_WITH_ROUNDING | — |
| C-STATE-01 | 零基准和缺值变化 | 3 / 0 / 0 | MATCH | — |
| C-BUILTIN-01 | 内置UCO_FAME基准与便宜MGO候选 | 2 / 0 / 2 | DIFFERENCE | 达标成本最优点或建议未满足目标 |

## 逐功能汇总

按该功能的检查汇总，不把同一实验中其他功能的失败传播过来。SOLVER 数值精度差异保留，但不记为生产失败。`部分独立交叉`仅表示所列样例，未穷尽该功能的全部输入和分支。

| 功能ID | 功能 | 全部实验及结果（同结果连续编号压缩） | 证据类型 | 结论 |
|---|---|---|---|---|
| M07-F01 | 最大混兑比例约束 | C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01、C-RND-03～04、C-RND-07、C-RND-09～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-02、C-RND-05～06、C-RND-08、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M07-F02 | 候选供应量约束 | C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01、C-RND-03～04、C-RND-07、C-RND-09～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-02、C-RND-05～06、C-RND-08、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M07-F03 | 增量预算约束 | C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01、C-RND-03～04、C-RND-07、C-RND-09～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-02、C-RND-05～06、C-RND-08、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M07-F04 | 最低达标混兑比例 | C-LP-17=DIFFERENCE；C-LP-11～16、C-LP-18、C-LP-21、C-LP-27、C-RND-01～06、C-RND-08～10、C-RND-12、C-RND-14～15、C-RND-17、C-RND-21～23、C-RND-26～27、C-RND-29～30、C-RND-32=MATCH；C-LP-01～10、C-LP-19～20、C-LP-22～26、C-LP-28、C-RND-07、C-RND-11、C-RND-13、C-RND-16、C-RND-18～20、C-RND-24～25、C-RND-28、C-RND-31=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉；浮点极近边界以精确参考复核 |
| M07-F05 | 无数学解的目标状态 | C-LP-11～18、C-LP-21、C-LP-27、C-RND-01～06、C-RND-08～10、C-RND-12、C-RND-14～15、C-RND-17、C-RND-21～23、C-RND-26～27、C-RND-29～30、C-RND-32=MATCH；C-LP-01～10、C-LP-19～20、C-LP-22～26、C-LP-28、C-RND-07、C-RND-11、C-RND-13、C-RND-16、C-RND-18～20、C-RND-24～25、C-RND-28、C-RND-31=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M07-F06 | 约束下目标不可达 | C-LP-17=DIFFERENCE；C-LP-04～09、C-LP-11～16、C-LP-18、C-LP-21、C-LP-27、C-RND-01～06、C-RND-08～10、C-RND-12、C-RND-14～17、C-RND-21～32=MATCH；C-LP-01～03、C-LP-10、C-LP-19～20、C-LP-22～26、C-LP-28、C-RND-07、C-RND-11、C-RND-13、C-RND-18～20=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉；浮点极近边界以精确参考复核 |
| M07-F07 | 约束下最大合规改善 | C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01～05、C-RND-07～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-06、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M07-F08 | 价格缺失时预算不可评估 | C-LP-01～28、C-RND-01～32=MATCH | CONTRACT / INDEPENDENT_EXACT | 部分独立交叉 |
| M07-F09 | 约束边界状态和固定报告点 | C-CASE-01、C-CASE-04=DIFFERENCE；C-CASE-02～03、C-CASE-05～08、C-LP-01～28、C-RND-01～32=MATCH | INDEPENDENT_EXACT | 存在差异 |
| M08-F01 | 当前模型燃料加 EUA 成本 | C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT | 部分独立交叉 |
| M08-F02 | 候选燃料相对 B0 临界吨价 | C-EC-02～03、C-EC-10、C-EC-13、C-EC-15～18、C-EC-23～24、C-EC-27=MATCH；C-EC-01、C-EC-04～09、C-EC-11～12、C-EC-14、C-EC-19～20、C-EC-25～26、C-EC-28=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M08-F03 | EUA 临界价 | C-EC-01～20、C-EC-23、C-EC-25～28=MATCH；C-EC-24=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M08-F04 | FuelEU 合规改善参考价值 | C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06、C-VALUE-01=MATCH_WITH_ROUNDING | CONTRACT / INDEPENDENT_EXACT | 部分独立交叉 |
| M08-F05 | 两方案成本切换点 | C-ENV-07=DIFFERENCE；C-ENV-01～06、C-ENV-08=MATCH | INDEPENDENT_EXACT | 存在差异 |
| M08-F06 | 全局下包络和支配交点剔除 | C-ENV-07=DIFFERENCE；C-ENV-01～06、C-ENV-08=MATCH | INDEPENDENT_EXACT | 存在差异 |
| M08-F07 | 价格缺失时不输出临界价 | C-CASE-01～08、C-EC-21～22=MATCH | CONTRACT | 契约补充验收 |
| M08-F08 | 经济排序 | C-CASE-01～08、C-VALUE-01=MATCH | CONTRACT / INDEPENDENT_EXACT | 部分独立交叉 |
| M09-F01 | 所有候选共享同一 B0 | C-CASE-01～08=MATCH | CONTRACT | 契约补充验收 |
| M09-F02 | 多候选独立计算 | C-BUILTIN-01、C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | CONTRACT / INDEPENDENT_EXACT | 部分独立交叉 |
| M09-F03 | 候选级局部阻断 | C-CASE-01～08=MATCH | CONTRACT | 契约补充验收 |
| M09-F04 | B0 参与当前模型成本排名 | C-CASE-01～08=MATCH | INDEPENDENT_EXACT | 部分独立交叉 |
| M09-F05 | 跨候选成本、达标和改善排名 | C-CASE-01、C-CASE-03=DIFFERENCE；C-CASE-02、C-CASE-04～08=MATCH | CONTRACT / INDEPENDENT_EXACT | 存在差异 |
| M09-F06 | 达标方案最低成本选择 | C-BUILTIN-01、C-CASE-01、C-CASE-03～04、C-CASE-06、C-LP-13、C-LP-17、C-RND-01、C-RND-04、C-RND-10、C-RND-17、C-RND-29=DIFFERENCE；C-CASE-02、C-CASE-05、C-CASE-07～08、C-LP-02～12、C-LP-14～16、C-LP-18、C-LP-21～22、C-LP-27～28、C-RND-02～03、C-RND-05～09、C-RND-11～12、C-RND-14～16、C-RND-20～21、C-RND-23～28、C-RND-30～32=MATCH；C-LP-01、C-LP-19～20、C-LP-23～26、C-RND-13、C-RND-18～19、C-RND-22=MATCH_WITH_ROUNDING | CONTRACT / INDEPENDENT_EXACT / SOLVER | 存在差异；浮点极近边界以精确参考复核 |
| M09-F07 | 约束下最大改善候选选择 | C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | CONTRACT / INDEPENDENT_EXACT | 部分独立交叉 |
| M11-F01 | 相对 B0 绝对变化 | C-CASE-04～05、C-CASE-07～08、C-STATE-01=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | CONTRACT / INDEPENDENT_EXACT | 部分独立交叉 |
| M11-F02 | 相对 B0 百分比变化 | C-CASE-04～05、C-CASE-07～08、C-STATE-01=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | CONTRACT / INDEPENDENT_EXACT | 部分独立交叉 |
| M11-F03 | 当前模型成本最低方案 | C-CASE-01～08、C-LP-01～28、C-RND-01、C-RND-03～21、C-RND-23～32、C-VALUE-01=MATCH；C-RND-02、C-RND-22=MATCH_WITH_ROUNDING | CONTRACT / INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M11-F04 | 达标方案最低成本比例 | C-BUILTIN-01、C-CASE-01、C-CASE-03～04、C-CASE-06、C-LP-13、C-LP-17、C-RND-01、C-RND-04、C-RND-10、C-RND-17、C-RND-29=DIFFERENCE；C-CASE-02、C-CASE-05、C-CASE-07～08、C-LP-02～12、C-LP-14～16、C-LP-18、C-LP-21～22、C-LP-27～28、C-RND-02～03、C-RND-05～09、C-RND-11～12、C-RND-14～16、C-RND-20～21、C-RND-23～28、C-RND-30～32=MATCH；C-LP-01、C-LP-19～20、C-LP-23～26、C-RND-13、C-RND-18～19、C-RND-22=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 存在差异；浮点极近边界以精确参考复核 |
| M11-F05 | 最大合规改善比例和候选 | C-CASE-04～05、C-CASE-07～08、C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01～05、C-RND-07～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-CASE-01～03、C-CASE-06、C-LP-05～07、C-LP-17～18、C-RND-06、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | INDEPENDENT_EXACT / SOLVER | 部分独立交叉 |
| M11-F06 | 条件式建议 | C-BUILTIN-01、C-CASE-01、C-CASE-04=DIFFERENCE；C-CASE-02～03、C-CASE-05～08=MATCH | CONTRACT / INDEPENDENT_EXACT | 存在差异 |
| M11-F07 | 不输出“综合最优”结论 | C-CASE-01～08=MATCH | CONTRACT | 契约补充验收 |
