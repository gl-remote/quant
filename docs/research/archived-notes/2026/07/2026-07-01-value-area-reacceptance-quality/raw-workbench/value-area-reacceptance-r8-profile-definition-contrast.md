# value_area_reacceptance R8：POC / VA 定义对照诊断

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r7-key-sample-review.md](./value-area-reacceptance-r7-key-sample-review.md)

## 1. 实验问题

R7 已经确认：

```text
POC / VA 的价值不是提供更远目标，
而是旧 VA 边界被快速拒绝后，
entry 到 POC / POC band 仍有适中、可兑现的回归空间。
```

本轮继续实验线 C，但仍不调参、不新增回测，只对 R7 的 DCE.m2601 关键样本重算不同 POC / VA 定义，回答：

```text
1. close-profile 是否只是偶然有效；
2. range-profile 是否能给出更稳健的共识锚；
3. POC band 是否比单点 POC 更能解释可兑现目标；
4. 后续如果改定义，应优先改哪一层。
```

## 2. 对照方法

使用同一批 R7 样本：

```text
DCE.m2601 / 5m
backtest_id = 401 / 402
样本日期：2025-09-24、2025-09-29、2025-10-15、2025-10-22、2025-11-05、2025-11-12
```

对每个样本的前一交易日 session 重算：

```text
close-profile：每根 5m bar 的全部 volume 归到 close；
range-profile：每根 5m bar 的 volume 在 low~high 每个 tick 上均匀分布；
POC：profile volume 最大价格，平手时取更接近 session close 的价格；
VA：从 POC 向两侧按相邻 volume 贪心扩展到 70% volume；
POC band：观察 profile top volume 价格集合，而不是直接作为策略规则。
```

POC band 本轮只做诊断，不作为最终定义：

```text
band70 = volume >= top_volume * 70% 的价格集合；
band50 = volume >= top_volume * 50% 的价格集合。
```

重要限制：

```text
close-profile 的 top-volume 价格可能不连续，
因此不能简单把 band 的 min~max 当作真实连续目标区。
```

## 3. 定义对照表

| 日期 | outcome | mode | VAL | VAH | POC | width | poc_pct | target_to_va | band70 | band50 | 判断 |
|------|---------|------|-----|-----|-----|-------|---------|--------------|--------|--------|------|
| 2025-09-24 | loss | close | 2911 | 2936 | 2917 | 25 | 0.240 | 0.600 | 2917~2964 / 3点 | 2917~2964 / 5点 | top volume 多峰，min~max band 误导 |
| 2025-09-24 | loss | range | 2913 | 2937 | 2917 | 24 | 0.167 | 0.625 | 2916~2926 / 7点 | 2914~2928 / 15点 | 更集中在低位，能识别目标未兑现 |
| 2025-09-29 | win | close | 2930 | 2948 | 2935 | 18 | 0.278 | 0.611 | 2935 / 1点 | 2934~2951 / 5点 | 单点 POC 可兑现 |
| 2025-09-29 | win | range | 2929 | 2947 | 2934 | 18 | 0.278 | 0.667 | 2934~2936 / 3点 | 2932~2937 / 6点 | 与 close 接近，同样可兑现 |
| 2025-10-15 | loss | close | 2889 | 2913 | 2894 | 24 | 0.208 | 0.667 | 2889~2894 / 3点 | 2889~2920 / 8点 | POC 偏低，目标过远 |
| 2025-10-15 | loss | range | 2887 | 2914 | 2897 | 27 | 0.370 | 0.481 | 2890~2903 / 13点 | 2890~2915 / 20点 | POC 更居中但仍未兑现 |
| 2025-10-22 | win | close | 2860 | 2899 | 2880 | 39 | 0.513 | 0.436 | 2856~2907 / 7点 | 2856~2907 / 9点 | close POC 是可兑现目标 |
| 2025-10-22 | win | range | 2878 | 2909 | 2892 | 31 | 0.452 | 0.935 | 2889~2893 / 4点 | 2889~2896 / 8点 | range POC 过远，错过实际回归 |
| 2025-11-05 | loss | close | 3011 | 3029 | 3013 | 18 | 0.111 | 0.722 | 3013~3025 / 5点 | 3013~3046 / 7点 | POC 极靠边，目标未兑现 |
| 2025-11-05 | loss | range | 3010 | 3030 | 3013 | 20 | 0.150 | 0.650 | 3012~3029 / 6点 | 3010~3030 / 19点 | range band 太宽，容易误判 hit |
| 2025-11-12 | win_force_flat | close | 3044 | 3063 | 3052 | 19 | 0.421 | 0.474 | 3052 / 1点 | 3047~3052 / 2点 | close POC 可兑现，但样本非标准 TP |
| 2025-11-12 | win_force_flat | range | 3043 | 3062 | 3046 | 19 | 0.158 | 0.789 | 3045~3066 / 10点 | 3044~3067 / 20点 | band 过宽，目标定义失真 |

## 4. 持仓路径触达对照

| 日期 | outcome | 持仓路径 high/low | close POC hit | close band70 hit | range POC hit | range band70 hit |
|------|---------|-------------------|---------------|------------------|---------------|------------------|
| 2025-09-24 | loss | 2929~2937 | 否 | 是 | 否 | 否 |
| 2025-09-29 | win | 2932~2947 | 是 | 是 | 是 | 是 |
| 2025-10-15 | loss | 2906~2919 | 否 | 否 | 否 | 否 |
| 2025-10-22 | win | 2862~2885 | 是 | 是 | 否 | 否 |
| 2025-11-05 | loss | 3023~3032 | 否 | 是 | 否 | 是 |
| 2025-11-12 | win_force_flat | 3048~3063 | 是 | 是 | 否 | 是 |

这个表说明：

```text
1. 单点 close POC 对 R7 的关键盈利样本解释力更强；
2. range POC 并没有整体改善，甚至会把 2025-10-22 的理想目标推得过远；
3. naive POC band hit 容易产生假阳性，尤其当 band 是不连续 top-volume 价格的 min~max；
4. POC band 必须定义为“POC 附近的连续局部接受带”，不能定义为全局高成交价格集合的 min~max。
```

## 5. 关键诊断

### 5.1 range-profile 不能直接替代 close-profile

R8 最重要的反直觉结果是：

```text
range-profile 更平滑，但不一定更适合作为短持仓 POC 目标。
```

典型例子是 2025-10-22：

```text
close POC = 2880，持仓路径触达；
range POC = 2892，持仓路径未触达；
range target_to_va = 0.935，目标变得过远。
```

这说明 range-profile 可能把较大波动 bar 的 volume 均匀摊开后，形成一个“几何重叠中心”，但该中心未必是短期可兑现的回归锚。

因此：

```text
range-profile 可以作为诊断对照，
但不能直接替代当前 close-profile。
```

### 5.2 close-profile 单点 POC 有用，但风险在多峰和失效

close-profile 在两个关键盈利样本中表现更好：

```text
2025-09-29：close POC 2935 被触达；
2025-10-22：close POC 2880 被触达；
2025-11-12：close POC 3052 被触达，但该样本是 force_flat。
```

但亏损样本也暴露了两个问题：

```text
1. POC 靠边时，单点目标容易是不可兑现的历史锚；
2. top-volume 价格可能多峰，单点 POC 不能代表完整接受结构。
```

2025-09-24 是典型多峰：

```text
close top volume 同时出现在 2917、2920、2964 等相距较远的位置。
```

如果把这些高成交价格的 min~max 直接当 band，就会错误认为持仓路径 hit band，实际上价格并没有回到 POC 附近。

### 5.3 POC band 有意义，但必须是局部连续 band

本轮排除了一个错误方向：

```text
不能把全局 top-volume 价格集合的 min~max 当作 POC band。
```

更合理的 POC band 应该满足：

```text
1. 以 POC 为中心；
2. 只向相邻价格扩展；
3. 扩展条件来自局部 volume 连续性；
4. band 宽度不能过大，否则会把“目标兑现”变成容易命中的宽区间；
5. 如果 profile 多峰，应记录多峰，而不是合并成一个大 band。
```

也就是说，后续如果实现 POC band，它应该是：

```text
POC local band / acceptance node，
不是 global high-volume band。
```

### 5.4 当前更重要的是“POC 有效性标签”

R8 之后，更清晰的方向不是马上改 target，而是先给 POC 打质量标签：

```text
POC 是否靠边；
POC 附近是否有连续成交支持；
profile 是否多峰；
close POC 与 range POC 是否严重背离；
entry 到 POC 是否适中；
当前日是否已形成背离旧 POC 的新接受区。
```

其中，`close POC 与 range POC 背离` 不能简单视为坏信号。2025-10-22 就是反例：

```text
close POC 与 range POC 背离较大，
但 close POC 更接近实际可兑现目标。
```

所以它更适合作为“需要图形解释的警示标签”，不是硬过滤。

## 6. 阶段结论

R8 的结论是：

```text
当前 close-profile POC 不是完全错误，
它在 DCE.m2601 的关键盈利样本上反而比 range-profile 更贴近短期可兑现目标。
```

但当前定义仍不够严格：

```text
close-profile 单点 POC 无法处理多峰；
range-profile 可能过度平滑并推远目标；
naive POC band 容易产生假阳性；
真正需要的是“局部、连续、可兑现”的 POC acceptance node。
```

因此，下一步不应直接切换 profile_mode，也不应把 POC band 作为宽目标区立即上线。

更合理的下一步是：

```text
定义 POC 质量标签：
1. POC edge distance；
2. POC local band width；
3. local band continuity；
4. multi-modal profile flag；
5. close-vs-range POC divergence；
6. current-day acceptance migration。
```

这些标签应先用于解释和分桶，再决定是否进入代码实现或策略过滤。
