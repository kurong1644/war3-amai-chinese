# 魔兽争霸3 · AMAI 中文智能 AI

> 让单机对战里的电脑像真人一样打 —— 会升级基地、会出英雄、会骚扰、会说中文、打不赢还会打 `gg` 认输。

适用于 **Warcraft III: The Frozen Throne 1.24 ~ 1.28**（1.26a 最佳）。
装一次，**所有对战地图的电脑全部升级**，不用逐张改装。

---

## 它做了什么

原版电脑的打法很呆：不升基地、不出二英雄、不用高级兵、兵线乱走。
这个项目把游戏本体的 AI 脚本换成了 [AMAI](https://github.com/SMUnlimited/AMAI)（Advanced Melee AI），
并在此之上做了大量定制：

| 特性 | 说明 |
|---|---|
| **会打主流战术** | 速升二本 → 二英雄 → 三本 → 高级兵，按种族走常规打法 |
| **英雄骚扰** | 剑圣疾风步骚扰、大法师压制、死骑带蜘蛛、恶魔猎手烧魔 |
| **会扩张** | 开分矿、造塔、按局势调整 |
| **中文聊天** | 开局、嘲讽、进攻、收割、缺钱、认输，全部中文 |
| **AI 人设** | 说话自带"模型/算力/梯度/训练集"的腔调，会嘴硬也会认怂 |
| **会投降** | 判断打不赢时发 `gg` 并主动退出，不拖着不打 |
| **选手昵称** | 电脑名字是 Sky / Moon / Grubby / TH000 / TeD / 120 这些知名选手，**且与种族对应** |

---

## 安装

### 需要什么

- Windows
- Warcraft III: TFT **1.24 ~ 1.28**（1.26a 最佳）
  - ⚠️ 1.20e / 1.21 / 1.22 / 1.23 **不支持**（AI 脚本编译不兼容，会导致游戏异常）
  - ⚠️ 1.29+ / Reforged **不支持**
- Python 3.6 或更高（[下载](https://www.python.org/downloads/)）—— 不需要装任何第三方库

### 步骤

```bash
# 1. 下载本项目，解压到任意位置

# 2. 安装（会自动查找游戏目录）
python install.py

# 如果没找到，手动指定：
python install.py --game "D:\Games\Warcraft III"
```

安装器会自动：
1. 校验目录里确实是魔兽争霸3（看有没有 `War3x.mpq`）
2. **备份** `War3Patch.mpq` 和 `War3x.mpq` 成 `.orig`（一次性，安全）
3. 把 5 个 AI 脚本写进两个 MPQ 归档
4. 回读校验（MD5 逐字节比对）

> 想先看看会改什么、不实际写入：加 `--dry-run`

### 怎么玩

单人游戏 → 自定义游戏 → **任意一张对战图** → 添加电脑

难度必须选 **普通** 或 **困难**：

> ⚠️ **不要选"简单"** —— 简单难度下暴雪会用自己的原版 AI 覆盖，本项目不生效。
> "发狂"有资源作弊，不太像真人，建议用"普通"。

---

## 你会看到什么

**开局时**，电脑会用中文报出打法：

```
Sky：我准备了一波流，大法师带水元素压上
Moon：我将使用吹风流
Grubby：剑圣首发配大G，中期狼骑出网
```

**对局中**，它会嘲讽、喊话、缺钱抱怨：

```
Sky：又一个碳基生物主动送上训练数据
Moon：你的操作在我的训练集里出现过，标签是「失败」
Grubby：梯度下降，朝你的主基地
```

**打不赢时**，它会认输并退出：

```
Sky：gg
Sky：我的模型这局欠拟合了
（随后该电脑离开对局）
```

---

## 卸载 / 还原

```bash
python install.py --uninstall
```

或手工把 `War3Patch.mpq.orig` / `War3x.mpq.orig` 改回原名覆盖。

---

## 常见问题

**Q：装完电脑完全不造兵、不造建筑？**
A：99% 是 `War3Patch.mpq` 没写成功。这个补丁包的优先级**高于** `War3x.mpq`，
如果只改了 `War3x.mpq`，游戏读到的会是「新的种族脚本 + 旧的公共库」，AI 会直接瘫痪。
本项目的安装器**两个包都会改**。如果手动安装，务必两个都改。

**Q：必须两个 MPQ 都改吗？**
A：是。`War3Patch.mpq` 里有原版 `Scripts\common.ai`(98KB)，它会遮蔽 `War3x.mpq` 里的版本。

**Q：能改 `Scripts\Blizzard.j` 吗？**
A：**绝对不能**。AMAI 自带的 `Blizzard.j` 是 Commander 组件，
在 1.24~1.28 上装了会让 AI 瘫痪（不造兵、只采矿）。本项目**不碰这个文件**。

**Q：地图里的电脑还是原版 AI？**
A：如果那张地图**自己内嵌了 AI 脚本**，地图内的优先级更高，全局安装对它无效。
换成普通对战图即可（或联系地图作者）。

**Q：安装后游戏打不开 / 报错？**
A：用 `python install.py --uninstall` 还原即可，备份一直保留着。

**Q：为什么难度不能选"简单"？**
A：暴雪在简单难度下会强制使用自己的原版 AI 逻辑，会覆盖本 AI。

---

## 技术说明

### 为什么不用改地图

TFT 的默认对战 AI 存在游戏本体的 MPQ 归档里：

```
War3Patch.mpq  Scripts\common.ai     98 KB（原版）  ← 优先级更高
War3x.mpq      Scripts\human.ai      Scripts\orc.ai
               Scripts\undead.ai     Scripts\elf.ai
               Scripts\common.ai
               Scripts\Blizzard.j    ← 本工具不碰
```

直接替换这几个脚本，任何 melee 地图上的电脑就都变成新 AI 了。

### 写入方式（为什么是安全的）

- 只**替换已存在的条目**，不新增/删除 → 哈希表完全不动
- 数据追加在归档**末尾**，原有数据一个字节都不改
- 只更新 block table 里对应条目的 `offset / csize / fsize`
- 压缩格式与暴雪原文件**完全一致**：
  ```
  [扇区表] (n+1) 个 uint32，首项 = 4*(n+1)，项为绝对偏移
  [扇区0][扇区1]...
      每个扇区 = 1 字节压缩类型(0x02 = zlib) + zlib 流
  ```
- 写入前后各做一次 **MD5 逐字节校验**，并检查对照组文件（如 `Blizzard.j`）未被改动
- 自动备份，随时可还原

`tools/mpqpatch.py` 是自包含的纯 Python 实现，带标准测试向量自检，
不依赖 `MPQEditor` 等外部工具。

> 顺带一提：常见的 `MPQEditor.exe` **读不了** `War3Patch.mpq`（会静默失败）；
> 暴雪自带的 `mpqadd.exe` 则报 `hash collision` 拒绝覆盖已有文件。所以才自己写了这个工具。

---

## 目录结构

```
war3-amai-chinese/
├── README.md
├── install.py              # 一键安装 / 卸载
├── LICENSE-AMAI.txt        # AMAI 原许可（必须保留）
├── scripts/                # 要写入的 AI 脚本
│   ├── common.ai
│   ├── human.ai
│   ├── orc.ai
│   ├── undead.ai
│   └── elf.ai
├── tools/
│   └── mpqpatch.py         # MPQ 补丁工具（自包含）
└── docs/
    └── ChatReply.txt       # 聊天关键词→回复表（可自行改写）
```

---

## 自定义

想改电脑说的话：编辑游戏目录下的 `Languages\Chinese\ChatReply.txt` 之类文件后重新打包，
或直接修改本项目的源码再编译（需要 AMAI 源码 + Perl）。

最简单的玩法：改 `docs/ChatReply.txt` 里的关键词回复，重新跑一次安装即可生效。

---

## 鸣谢与许可

**本项目的 AI 核心来自 [AMAI (Advanced Melee AI)](https://github.com/SMUnlimited/AMAI)**，
作者 **Strategy Master / Zalamander / AIAndy**，遵循其原始许可：

- 不可商用
- 必须署名原作者
- 允许再分发
- 必须保留相同许可条款

原始许可全文见 `LICENSE-AMAI.txt`。

魔兽争霸3 及其 AI 脚本格式归
[Blizzard Entertainment](https://www.blizzard.com/) 所有，
本项目仅以单机娱乐为目的修改本地游戏文件，不包含任何暴雪版权资源。
