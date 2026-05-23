# AI 行为规范约束

## 核心规则

### 规则 1: 执行 Python 命令前确保环境正确（强制执行）

**每次执行 Python 命令前，必须确保处于正确的 Conda 环境中：**

#### 方法1：使用脚本激活（推荐）

```bash
./activate_env.sh
```

#### 方法2：直接激活

```bash
source /usr/local/Caskroom/miniconda/base/bin/activate quant_trading
```

#### 激活后验证

确认使用的是正确的 Python 环境：

```bash
which python
python --version
```

确保显示的是 `quant_trading` 环境的 Python。

---

*本规范由 AI 自动生成*
