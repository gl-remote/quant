# direction-strength-combo · 研究现状

> 类型：Research / 主题现状
> 状态：**待启动**（2026-07-17 立题 · 实验计划已确定 · 尚未执行）
> 最近更新：2026-07-17

## 1. 一句话结论

```text
待执行实验验证。

核心问题：既然单独识别方向（通道 A）和单独识别强度（通道 B）都面临挑战，
能否找到一种同时编码方向和强度信息的结构性特征，实现两者的配合？

三种配合模式：
1. 结构性特征隐含编码（如 A3_skew 大小）
2. 强度做粗粒度过滤（如 ATR 极低时段排除）
3. 联合分布建模（条件期望 E[gross|direction_known ∧ strength_condition]）
```

## 2. 边界

```text
1. 本主题研究方向+强度的配合效应，不单独研究方向或强度；

2. 强度条件采用粗粒度分档（3 档），不追求精确预测 |ν|/σ（KF-B6 已证明不可行）；

3. 塑形容器 (K_S, K_T, τ) 由上游 KF-27 反解，本主题不重新定义塑形规则；

4. 方向信号优先使用 va-asymmetry 分类器（已证明有方向 edge）；

5. 任何配合效应必须经过时间半分验证（Gate 3），避免过拟合。
```

## 3. 下一步

```text
1. 实现 workbench 脚本（特征构造 + Gate 检验）；
2. 执行第一阶段实验（C1-C3）；
3. 根据结果决定是否进入第二阶段；
4. 更新 KF 清单。
```

## 4. 关键发现清单

暂无。待实验执行后追加。

## 5. 数据管道说明

待确认。

## 6. 上游依赖

| 依赖 | 类型 | 说明 |
|------|------|------|
| kf:structural-shaping-alpha#KF-26 | 数学基础 | 双通道 alpha 框架 · E_gross^mix 公式 |
| kf:structural-shaping-alpha#KF-27 | 工程接口 | 分布输入闭式解 · 参数优化器 |
| kf:structural-shaping-alpha#KF-19 | 实证基础 | 通道 A（方向 alpha）已实证 |
| kf:strength-factor-screening#KF-B6 | 边界约束 | |ν|/σ 无法从价量数据精确预测 |
| theme:va-asymmetry-composite | 分类器 | A3_skew + ATR + trend 的 tier 分类器 |
