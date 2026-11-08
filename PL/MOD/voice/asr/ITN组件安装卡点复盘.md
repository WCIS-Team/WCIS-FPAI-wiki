# ITN 组件安装卡点复盘（FunASR 安装全集唯一卡住的部分）

- 日期：2026-10-20
- 范围：83 个模型早已装完并验证，唯一卡住的是 ITN（反向文本正则化）组件

---

## 为什么卡住

1. **直接原因**：安装脚本里 `git clone https://github.com/modelscope/fun-text-processing.git` 从 10-20 凌晨 3:33 起挂起 14 小时。实测无任何到 GitHub 的 TCP 连接、CPU 几乎不动，是校园网访问 GitHub 被卡后 git 不退出、死等重试。脚本没有超时保护，后面逻辑永远走不到。
2. **深层原因（即使网络正常也装不上）**：
   - `fun_text_processing` 在 PyPI 上根本不存在，pip 装不了，只能用它源码
   - ITN 核心依赖 `pynini` 在 Windows 上没有官方 wheel，pip 源码构建需要 Cython + OpenFst，基本不可行

## 最后怎么通过的

1. 杀掉卡死的 git 进程组，删除 clone 残留的空壳目录
2. 装 miniconda（清华镜像），用 `.bat` 直接调安装器（MSYS2 bash 直调会破坏 `/S` 静默参数导致 GUI 挂起）
3. `conda create -n itn python=3.11 pynini=2.1.7`，pynini 走 **conda-forge 的 win-64 预编译包**，这是 Windows 唯一可靠来源
4. 补装依赖：regex、num2words、inflect、joblib、tqdm、editdistance
5. 直接用 FunASR 源码内嵌的 `fun_text_processing` 模块（`sys.path` 指向 `D:\yzd\llm\funasr\FunASR`），不从 GitHub 拉
6. 修正调用签名：`inverse_normalize(text, verbose=False)` 的 `verbose` 是必填参数（无默认值）
7. 验证通过：12 语言（en/ru/ja/ko/id/vi/tl/es/pt/fr/de/zh）全部加载成功，真实转换正常
   - en `one thousand two hundred and thirty four dollars` → `$1234`
   - zh `三千二百` → `3200`、`一三八 零零一三八零零零` → `138 00138000`（中文输入需空格分词）

## 结论

卡点本质是 **pynini 在 Windows 的安装来源问题**，不是 FunASR 本身的问题。解决路径 = 杀僵尸进程 + conda-forge 预编译 pynini + 源码内嵌模块，全程不需要碰 GitHub。
