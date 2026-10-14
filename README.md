# 万智牌 · 美术审美测试

回答 38 道生活化的小题，从 **370 张万智牌主将插画**里挑出 3 张最符合你口味的，并给出一份「审美画像」。

**在线玩**：https://manvatian1121.github.io/commander-art-quiz/

---

## 这是什么

一个测**美术偏好**的小玩具，不是测性格。

题目问的都是日常里能立刻回答的选择 —— 手机主题、外套、杯子、睡前一小时做什么 ——
但每一题的选项都对应着画面上的某个属性（明暗、冷暖、繁简、画风…）。
答完把这些属性累加成一条「口味向量」，再和每张插画的图像特征做点乘排序。

**没有正确答案，也没有更好或更差的审美。**

## 三层维度

| 层 | 数量 | 说明 |
|---|---|---|
| **像素轴** | 10 | 明暗、冷暖、浓淡、色彩多少、繁简、明暗反差、画法新旧、是否铺满、画师知名度 |
| **形态轴** | 7 | 纯人类 / 人形异类 / 凶猛巨兽 / 扭曲异形 / 可爱小兽 / 写实动物 / 机械构装 |
| **风格轴** | 9 | 可爱 / 黑暗 / 史诗 / 宁静 / 激烈 / 怪诞 / 神秘 / 温暖 / 忧郁 |

**像素轴**从插画像素直接算出来（亮度、饱和度、色相分布、梯度幅值…），可复现、可解释。
**形态与风格轴**来自逐张看图人工标注，标注口径写在 `data/questions_design_note.md`。

## 改动前请先读

`PITFALLS.md` 记录了本项目踩过的坑——尤其是几处**症状会误导排查方向**的问题（最典型的一个：手机上卡片整块空白，看着像图片加载失败，实际是移动端 flex 高度塌陷）。
改前端、改数据格式、加维度或加类别之前，建议先扫一遍。

## 目录

```
index.html              在线版（图走 Scryfall CDN，手机可直接玩）
art_quiz.html           本地版（图引用 data/cards/，体积小但需在同一目录下有图）
scripts/                全部脚本（采集 / 标注 / 出题 / 求解 / 构建 / 测试）
data/*.json             池子、标注、轴、题库
```

## 自己重建

```bash
python scripts/fetch_art_manifest.py   # 取主将与其插画的元数据（需联网）
python scripts/download_art.py         # 下载插画（约 120 MB）
python scripts/art_features.py         # 算像素审美特征
python scripts/build_axes.py           # 归一化成可比的轴
python scripts/merge_form_tables.py    # 合并形态标注
python scripts/run_all.py              # 出题 → 求解权重 → 构建 → 全套测试
```

`run_all.py` 会依次跑 12 步并报告每一步结果，全绿才算通过。
构建产物：`index.html`、`art_quiz.html`；另外 `build_mobile.py` / `build_standalone.py`
可以生成内嵌图片的离线版（体积大，未入库）。

## 数据来源

- **卡牌与插画**：[Scryfall](https://scryfall.com/)（API 与图片 CDN）
- **主将流行度**：[EDHREC](https://edhrec.com/)
- **卡名中文**：[mtgch.com](https://mtgch.com/)

万智牌及其卡牌插画的版权归 Wizards of the Coast 所有。
本项目是非商业的同人作品，仅用于学习与娱乐。

## 许可

代码以 MIT 许可发布（见 `LICENSE`）。
卡牌插画不在此许可范围内，版权归 Wizards of the Coast。
