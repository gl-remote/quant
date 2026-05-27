/**
 * data-ql-id → 行业规范名称 映射表
 *
 * 命名遵循：
 *   - 中文名称，准确描述板块功能/内容
 *   - data-ql-id 格式：MODULE-SECTION-ELEMENT（大写、短横线分隔）
 *   - 优先使用量化/金融行业通用术语
 */

export const qlIdNameMap: Record<string, string> = {
  // ─── LAY 布局模块 ───
  "LAY-HDR-CONTAINER": "全局导航栏",
  "LAY-HDR-LOGO": "系统Logo",
  "LAY-HDR-VERSION": "版本标识",
  "LAY-HDR-BREADCRUMB": "面包屑导航",
  "LAY-MAIN-AREA": "主内容区",
  "LAY-FTR-CONTAINER": "页脚信息栏",

  // ─── NAV 回测导航页 ───
  "NAV-PG-CONTAINER": "回测导航页",
  "NAV-PG-HERO": "导航页概览区",
  "NAV-PG-STATS": "回测统计摘要",
  "NAV-PG-CARDLIST": "回测记录列表",

  // ─── RUN 回测详情页 ───
  "RUN-PG-CONTAINER": "回测详情页",
  "RUN-PG-LOADING": "页面加载状态",
  "RUN-PG-HEADER": "回测概要头部",
  "RUN-PG-TABS": "回测/优化切换栏",
  "RUN-PG-TAB-BACKTEST": "回测结果标签",
  "RUN-PG-TAB-OPTUNA": "参数优化标签",
  "RUN-PG-CONTENT": "回测内容区",

  // ─── MET 指标卡片 ───
  "RUN-MET-CONTAINER": "核心指标卡片组",
  "RUN-MET-ITEM-SYMBOLS": "品种总数指标",
  "RUN-MET-ITEM-RETURN": "平均收益率指标",
  "RUN-MET-ITEM-TRADES": "总交易笔数指标",
  "RUN-MET-ITEM-SHARPE": "平均夏普比率指标",

  // ─── KLINE K线图 ───
  "RUN-KLINE-CONTAINER": "K线图表区",
  "RUN-KLINE-LOADING": "K线加载状态",
  "RUN-KLINE-EMPTY": "K线空数据提示",
  "RUN-KLINE-TOOLBAR": "K线工具栏",
  "RUN-KLINE-BTN-DAILY": "日线周期切换",
  "RUN-KLINE-BTN-MINUTE": "分钟线周期切换",
  "RUN-KLINE-BTN-SMA": "均线叠加开关",
  "RUN-KLINE-CHART": "K线蜡烛图",

  // ─── EQ 权益曲线 ───
  "RUN-EQ-CONTAINER": "权益曲线图表区",
  "RUN-EQ-EMPTY": "权益曲线空数据",
  "RUN-EQ-METRICS": "权益关键指标",
  "RUN-EQ-MET-TOTALRET": "累计收益率指标",
  "RUN-EQ-MET-MAXDD": "最大回撤率指标",
  "RUN-EQ-MET-ENDEQ": "期末权益指标",
  "RUN-EQ-CHART": "权益回撤双轴图",

  // ─── TBL 品种汇总表 ───
  "RUN-TBL-CONTAINER": "品种汇总表区",
  "RUN-TBL-EMPTY": "品种表空数据",
  "RUN-TBL-HEADER": "品种表头部",
  "RUN-TBL-TABLE": "品种数据表格",

  // ─── BT 回测明细 ───
  "RUN-BT-CONTAINER": "回测明细区",
  "RUN-BT-EMPTY": "回测明细空数据",
  "RUN-BT-HEADER": "回测明细标题",
  "RUN-BT-METRICS": "回测指标明细",
  "RUN-BT-PARAMS": "策略参数列表",

  // ─── OPT 参数优化 ───
  "RUN-OPT-CONTAINER": "参数优化图表区",
  "RUN-OPT-EMPTY": "优化数据空状态",
  "RUN-OPT-HEADER": "优化研究概览",
  "RUN-OPT-STUDYNAME": "优化研究名称",
  "RUN-OPT-BESTVALUE": "最优目标值",
  "RUN-OPT-BESTPARAMS": "最优参数组",
  "RUN-OPT-PARAMLIST": "最优参数明细",
  "RUN-OPT-CHARTS": "优化图表集合",
  "RUN-OPT-HISTORY": "优化历史面板",
  "RUN-OPT-HISTORY-CHART": "优化历史图",
  "RUN-OPT-IMPORTANCE": "参数重要性面板",
  "RUN-OPT-IMPORTANCE-CHART": "参数重要性图",
  "RUN-OPT-PARALLEL": "平行坐标面板",
  "RUN-OPT-PARALLEL-CHART": "平行坐标图",
  "RUN-OPT-CONTOUR": "等高线面板",
  "RUN-OPT-CONTOUR-CHART": "等高线图",
};