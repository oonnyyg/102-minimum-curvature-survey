# minimum-curvature-survey

根据钻孔测斜记录，用最小曲率法重建三维孔迹（仅 Python 标准库）。

## 用法

```sh
python -m borehole_survey 输入.json --out 输出目录
```

- 输入格式、坐标与角度约定见 `docs/coordinates.md`，示例见 `examples/survey.json`。
- 输出：每孔 `<id>_stations.csv`（逐站）与 `<id>.json`（孔底位置、最大狗腿度、逐站数据）。
- 任何非法输入整批失败（退出码 1），不生成报告。

## 测试

```sh
python -m unittest discover -s tests
```
