# AI 行为规范约束

## 核心规则

### 规则 1: 激活正确的 Conda 环境（强制执行）

**每次执行 Python 命令前，必须激活正确的 Conda 环境：**

```bash
./activate_env.sh
```

或者直接激活：

```bash
source /usr/local/Caskroom/miniconda/base/bin/activate quant_trading
```

### 规则 2: 验证环境

激活环境后，确认 Python 路径和版本：

```bash
which python
python --version
```

确保显示的是 `quant_trading` 环境的 Python。

---

*本规范由 AI 自动生成*
