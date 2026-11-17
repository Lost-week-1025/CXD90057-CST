# 01 · 容器结构

## 外层：UFU / DAT

```
0x00  89 55 46 55 0D 0A 1A 0A          8 B 魔数（仿 PNG，可检出文本模式传输损坏）
      记录链：[u32be size][4 B ASCII type][size B data]

0x08  DATV   数据版本 = 01 00 00 00
0x14  PROV   provisioning = 01 00 00 00
0x20  UDID   机型/更新标识   ← 长度随机型变化
...   FDAT   固件主体（密文）
N-12  DEND   [u32be 4]["DEND"][u32be CRC32]
```

## 逐机型实测

| 机型 | SoC | UDID size | FDAT 记录@ | 载荷@ | 文件总长 |
|---|---|---:|---:|---:|---:|
| ZV-1F | CXD90045 | 0x54 = 84 | 0x7C | 0x84 | 443,505,056 |
| ZV-E10 v2.03 | CXD90045 | 0xBC = 188 | 0xE4 | 0xEC | 372,454,920 |
| **A6700 v2.00** | **CXD90057** | **0x6C = 108** | **0x94** | **0x9C** | **1,024,017,848** |
| A7R V v4.00 | CXD90057 | 20（文献） | — | — | 754,525,608 |

> **UDID 长度在 20/84/108/188 之间跳动**，写死 FDAT 偏移的脚本只能解一台机。
> 通用做法：扫 `DATV`/`PROV` 锚点顺链走，或直接搜 `FDAT` 字节。

## FDAT 载荷 = 帧区 + trailer

```
载荷长度 = frames × 1024 + 272
A6700: 1,000,017 × 1024 + 272 = 1,024,017,680  ✅
```

## 内层（解密后）

```
[0, 512)                     FdatHeader
[512, 512+fs.size)           updater.img (SquashFS 4.0)
[firmwareOffset, ...)        tar (POSIX)
```

A6700 实测：`fs.size = 1,253,376`、`firmwareOffset = 1,253,888`、
`firmwareSize = 1,018,763,264`、`numFileSystems = 2`、`FS[0]=U`、`FS[1]=P`。

闭合校验：`512 + 1,253,376 + 1,018,763,264 = 1,020,017,152` ✅

## FdatHeader 关键字段（A6700）

| 偏移 | 字段 | 值 |
|---:|---|---|
| 0x00 | magic | `UDTRFIRM` |
| 0x08 | header CRC32 | `0x5D0B3237`（算 `[12,512)`） |
| 0x0C | version | `0100` |
| 0x10 | modeType | `U`（User） |
| 0x14 | luwFlag | `N` |
| 0x21 | versionMajor | `0x02` → **v2.00** |
| 0x24 | model | `0x20030001` |
| 0x30 | firmwareOffset | 1,253,888 |
| 0x38 | numFileSystems | 2 |