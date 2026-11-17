# 外部来源引用

**本目录不包含任何第三方代码。** 仅记录来源、版本与许可证状态，便于复现与追溯。

| 项目 | 用途 | 许可证 | 是否可再分发 |
|---|---|---|---|
| [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | FDAT 格式与 crypter 实现基线 | 见上游 | 按上游 |
| [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) | CXD90057 `k0`/`k8` 密钥、`signature.py` 签名规范 | 见上游 | 按上游 |
| [ivica00/sony-a6400-research](https://github.com/ivica00/sony-a6400-research) | CXD90045 平台证据 | **MIT** | 可（保留声明） |
| [PCIEARIA/A6400-Extra-Menu](https://github.com/PCIEARIA/A6400-Extra-Menu) | A6400 注入方式对比 | PolyForm Noncommercial 1.0.0 | 非商业，保留声明 |
| [DevCrashDay/a6400](https://github.com/DevCrashDay/a6400) | A6400 开机 hook 实现 | 见上游 | 见上游 |



## 复现外部材料的建议

需要本地比对时，自行获取并放在仓库之外的目录，例如：

```
../_ref/
  sony-a6400-research/      # MIT，可自由参考
  A6400-Extra-Menu/         # 非商业，阅读参考
  a6400-devc-rash-day/      # 无授权，仅本地研究，切勿传播
```

## 引用到的公开密钥

`key_cxd90057_k0` / `key_cxd90057_k8` 来自 `Hearts-Ace` 项目的
`firmware/r5/build_support/lib/fwtool/sony/constants.py`，用于格式研究与校验复现。
若上游后续调整许可，请以彼时条款为准。
