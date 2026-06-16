# 策略架构改进计划

## 本周期可覆盖

### 1. ~~data_requirements 空壳问题~~ ✅ 已完成
**现状**：装饰器已自动注册数据需求，但 `data_requirements()` 还需返回空 `DataRequirements()`
**目标**：框架自动合并装饰器注册的需求，策略无需实现 `data_requirements` 或返回 None 即可
**方案**：`Strategy.data_requirements` 基类默认返回空 `DataRequirements`，装饰器在此基础上 merge；策略无需覆写

### 2. 分级止盈装饰器
**现状**：只有固定比例止盈（`with_stop_take_profit`）和 ATR 止盈（`with_atr_stop_take_profit`），缺少"持仓越久止盈越宽松"的能力
**目标**：新增 `with_tiered_take_profit` 拦截型装饰器
**方案**：
```python
@with_tiered_take_profit({0: 0.08, 30: 0.04, 60: 0.02, 120: 0.01})
# 持仓 0 分钟盈利 8% 止盈，30 分钟后降到 4%，以此类推
```

### 3. 装饰器分组可读性
**现状**：10+ 个装饰器堆叠在类上方，视觉密集
**目标**：支持列表式声明，减少堆叠层数
**方案**：
```python
# 方案 A：列表式声明（建议型）
long_conditions = [
    trend_long_when_compare(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "15m")),
    confirm_long_when(at(MACD, "1m"), ">", 0),
    confirm_long_when(at(MACD, "5m"), ">", 0),
    confirm_long_when(at(KDJ, "1m"), "<", "kdj_oversold"),
    confirm_long_when(at(KDJ, "5m"), "<", "kdj_oversold"),
]
```
需要改造装饰器注册机制，支持非 `@` 语法也能注册 `__direction_keys__`

---

## 后续周期

### 4. 参数优化空间声明（Hyperopt 集成）
**现状**：`MACrossParams` 的参数是固定默认值，无法声明优化范围
**目标**：支持 `IntParameter` / `DecimalParameter` 声明参数搜索空间
**方案**：
```python
@dataclass
class MACrossParams:
    sma_short: int = IntParameter(5, 30, default=10)
    stop_loss_ratio: float = DecimalParameter(0.01, 0.10, default=0.03)
```
需要对接 Optuna / Freqtrade Hyperopt 等优化引擎

### 5. IDE 友好性提升
**现状**：`__direction_keys__` 动态注册，IDE 无法跳转和补全
**目标**：提升开发体验
**方案**：
- 生成 `__init__.pyi` 类型存根
- 或在装饰器内用 `__class_getitem__` 提供类型提示
- 声明式 DSL 的通病，优先级低

### 6. 策略模板 / 脚手架
**现状**：新建策略需手动复制装饰器组合
**目标**：CLI 一键生成策略骨架
**方案**：`quant create-strategy --name rsi --indicators RSI,MACD --stops atr_stop,take_profit`
