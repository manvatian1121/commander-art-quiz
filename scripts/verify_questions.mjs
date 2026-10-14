// 交付校验：两极人设 Top3、轴覆盖、位置残留、题目清单。
//   node scripts/verify_questions.mjs
//
// 2026-10-13 第二版结构：题库是 26 道单选审美题 + 3 道形态多选题（b01/b02/b03）。
//   · 单选审美题每题 2 轴、4 选项；
//   · 多选题 6 个选项、每个只挂自己那一类 form_*，权重由 solve_form_weights.py 解出；
//     三道题的**选项文本与排列顺序都不同**（b02 左旋 1、b03 左旋 3），
//     勾选在三题上累加 → 总推力是单题 α 的 3 倍。
//   · 「固定位置残留」不再单看某一个位置（多选只有 1 项带某一类，抵消不掉），
//     改看「审美轴四个位置上的残留之和 = 0」这条恒等式；
//     形态轴的四列之和**结构上不为 0**（= 该形态在「前 4 位」出现的次数 × 其单题权重）。
// 2026-10-14：+ 9 道画风题（s01~s09）+ 5 道画法题（t01~t05）⟹ 43 题 = 40 单选 + 3 多选；
//   轴 25 → 31（+ 6 条 tech_*）。画风/画法轴与审美轴同口径（每题 2 正 2 负 → 四列之和 = 0）；
//   画法轴是 5 个顶点上的 5-环（5 题 × 2 轴 = 10 轴位 = 5 类 × 2 次）⟹ 五条全偶数、满偏全 2.4。
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DATA = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "questions.json"), "utf8"));
const Q = DATA.questions;
const SINGLE = Q.filter((q) => !q.multi);
const MULTI = Q.filter((q) => q.multi);
// 选项汉字数上限：唯一来源 scripts/check_limits.json（口径与 audit_questions.py 一致）
const MAX_HAN = JSON.parse(
  fs.readFileSync(path.join(ROOT, "scripts", "check_limits.json"), "utf8")).option_max_han;

const LEGACY = ["warm", "bright", "vivid", "rich", "detailed",
                "contrasty", "modern", "borderless", "starart"];
const FORM = ["form_纯人类", "form_人形异类", "form_凶猛巨兽",
              "form_扭曲异形", "form_可爱小兽", "form_机械构装", "form_写实动物"];
const STYLE = ["style_神秘", "style_史诗", "style_黑暗", "style_怪诞", "style_激烈",
               "style_温暖", "style_宁静", "style_可爱", "style_忧郁"];
// 2026-10-14：6 条 tech_* 画法轴（data/art_style.json 的 370 条画法标注；水彩淡彩不出题）
const TECH = ["tech_二次元日系", "tech_欧美厚涂", "tech_卡通绘本",
              "tech_线稿版画", "tech_写实数字绘", "tech_水彩淡彩"];
const FORMS = FORM.map((a) => a.slice(5));
const LIGHT = ["bright", "contrasty"];         // darkarea 2026-10-13 下线
const AXES = LEGACY.concat(FORM).concat(STYLE).concat(TECH);

const payload = JSON.parse(
  fs.readFileSync(path.join(ROOT, "art_quiz.html"), "utf8")
    .match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)[1]
    .replace(/<\\\//g, "</"));
const ARTS = payload.a;

/** 把答案归一化成下标数组（单选 = [i]，多选 = [i,...]，未答 = []） */
function answersOf(q, answers) {
  const v = answers[q.id];
  if (v === undefined || v === null) return [];
  const list = Array.isArray(v) ? v : [v];
  return list.filter((i) => Number.isInteger(i) && i >= 0 && i < q.opts.length);
}
function prefOf(answers) {
  const pref = {};
  AXES.forEach((a) => { pref[a] = 0; });
  Q.forEach((q) => answersOf(q, answers).forEach((i) => {
    const s = q.opts[i].s;
    for (const k of Object.keys(s)) pref[k] += s[k];
  }));
  return pref;
}
const scoreArt = (pref, vec) => AXES.reduce((s, a) => s + (pref[a] || 0) * vec[a], 0);
function recommend(pref, n = 3) {
  const rows = ARTS.map((a) => ({ a, s: scoreArt(pref, a.vec) }))
    .sort((x, y) => y.s - x.s || String(x.a.art_id).localeCompare(String(y.a.art_id)));
  const out = [], seen = new Set();
  for (const r of rows) {
    const key = r.a.cmdr_en || r.a.cmdr_zh;
    if (seen.has(key)) continue;
    seen.add(key); out.push(r);
    if (out.length === n) break;
  }
  return out;
}

console.log("=".repeat(74));
console.log(`题库：${Q.length} 题 = ${SINGLE.length} 单选 + ${MULTI.length} 多选`
  + `（${MULTI.map((q) => q.id).join("、") || "无"}）；插画 ${ARTS.length} 张`);
console.log("=".repeat(74));

/* ① 单轴极值作答：每题挑对该轴最有利的选项（多选另给一档） */
function extremePicker(axis, sign) {
  return (q) => {
    let best = 0, bestV = -Infinity;
    q.opts.forEach((o, i) => {
      const v = sign * ((o.s && o.s[axis]) || 0);
      if (v > bestV) { bestV = v; best = i; }
    });
    return best;
  };
}
const answersFor = (picker) => {
  const a = {};
  Q.forEach((q) => { a[q.id] = q.multi ? [0] : picker(q); });
  return a;
};

console.log("\n" + "=".repeat(74));
console.log("① 单轴两个极端：Top3（先看两极是否完全不同）");
console.log("=".repeat(74));
let clash = 0;
for (const axis of LEGACY) {
  const pos = recommend(prefOf(answersFor(extremePicker(axis, +1))));
  const neg = recommend(prefOf(answersFor(extremePicker(axis, -1))));
  const np = pos.map((p) => p.a.cmdr_zh).join(" / ");
  const nn = neg.map((p) => p.a.cmdr_zh).join(" / ");
  const same = pos.map((p) => p.a.art_id).join() === neg.map((p) => p.a.art_id).join();
  if (same) clash++;
  console.log(`  ${axis.padEnd(11)} 正极→ ${np}`);
  console.log(`  ${"".padEnd(11)} 负极→ ${nn}   ${same ? "⚠ 相同" : ""}`);
}
console.log(`  两极相同的轴：${clash} 个`);

/* ①b 形态多选题：只勾一类时 Top3 的形态纯度 */
console.log("\n" + "=".repeat(74));
console.log(`①b 多选题（${MULTI.map((q) => q.id).join("/")}，勾选在三题上累加）：
             只勾某一类时 Top3 的形态纯度（审美题固定选第 1 项）`);
console.log("=".repeat(74));
const MQS = MULTI;
const MQ = MQS[0];
const W = {};
MQ.opts.forEach((o) => {
  const k = Object.keys(o.s).find((x) => x.startsWith("form_"));
  W[k.slice(5)] = o.s[k];
});
// 三道题的权重必须一致 —— 否则「勾同一类在三题上拿到同样推力」就不成立
{
  const mismatch = [];
  MQS.forEach((q) => q.opts.forEach((o) => {
    const k = Object.keys(o.s).find((x) => x.startsWith("form_"));
    if (Math.abs(o.s[k] - W[k.slice(5)]) > 1e-12) mismatch.push(`${q.id} 的 ${k}`);
  }));
  console.log(`  三题权重表一致：${mismatch.length ? "✗ " + mismatch.join("、") : "✓"}`);
}
function picksForForms(want) {
  const answers = {};
  Q.forEach((q) => {
    if (q.multi) {
      answers[q.id] = q.opts.map((o, i) => {
        const k = Object.keys(o.s).find((x) => x.startsWith("form_"));
        return want.includes(k.slice(5)) ? i : -1;
      }).filter((i) => i >= 0);
    } else answers[q.id] = 0;
  });
  return recommend(prefOf(answers));
}
const allFormIds = [];
FORMS.forEach((f) => {
  const r = picksForForms([f]);
  const pur = r.filter((p) => p.a.form === f).length / 3;
  allFormIds.push(...r.map((p) => p.a.art_id));
  console.log(`  勾 ${f.padEnd(6)} → 纯度 ${pur.toFixed(2)}   ` +
    r.map((p) => `${p.a.cmdr_zh}(${p.a.form})`).join(" / "));
});
{
  const r = picksForForms(FORMS);
  console.log(`  全勾 7 类   → ${r.map((p) => `${p.a.cmdr_zh}(${p.a.form})`).join(" / ")}`
    + "（形态维度应完全中立）");
}
{
  const r = picksForForms(["纯人类", "机械构装", "凶猛巨兽"]);
  console.log(`  勾 3 类     → ${r.map((p) => `${p.a.cmdr_zh}(${p.a.form})`).join(" / ")}`);
}

/* ② 语义相反的两组人设 */
console.log("\n" + "=".repeat(74));
console.log("② 两极人设（语义相反）Top3");
console.log("=".repeat(74));
const PERSONA = {
  "暖·亮·浓·多彩·繁复": { warm: 1, bright: 1, vivid: 1, rich: 1, detailed: 1, contrasty: 1, modern: 1 },
  "冷·暗·淡·单色·简洁": { warm: -1, bright: -1, vivid: -1, rich: -1, detailed: -1, contrasty: -1, modern: -1 },
  "铺满·熟面孔·新画法": { borderless: 1, starart: 1, modern: 1 },
  "留边·新面孔·老画法": { borderless: -1, starart: -1, modern: -1 },
};
function personaPicker(want) {
  return (q) => {
    let best = 0, bestScore = -Infinity;
    q.opts.forEach((o, i) => {
      let sc = 0, hit = 0;
      for (const [k, v] of Object.entries(want)) {
        if (o.s[k] !== undefined) { sc += v * o.s[k]; hit++; }
      }
      if (hit === 0) sc = -1e9;                   // 没表达的题随便选（统一第 0 项）
      if (sc > bestScore) { bestScore = sc; best = i; }
    });
    return best;
  };
}
const picks = {};
for (const [name, want] of Object.entries(PERSONA)) {
  const r = recommend(prefOf(answersFor(personaPicker(want))));
  picks[name] = r.map((p) => p.a.art_id).join("|");
  console.log(`  ${name}`);
  console.log(`     ${r.map((p) => `${p.a.cmdr_zh}(${p.a.form})`).join(" / ")}`);
}
const names = Object.keys(PERSONA);
const overlap = (x, y) => {
  const a = picks[x].split("|"), b = new Set(picks[y].split("|"));
  return a.filter((i) => b.has(i)).length;
};
console.log(`  暖冷两组重合：${overlap(names[0], names[1])} / 3`);
console.log(`  边框/熟识两组重合：${overlap(names[2], names[3])} / 3`);

/* ③ 轴覆盖 + 位置偏置 */
console.log("\n" + "=".repeat(74));
console.log("③ 轴覆盖与位置残留");
console.log("=".repeat(74));
const cov = {};
LEGACY.concat(STYLE).concat(TECH).forEach((k) => { cov[k] = { n: 0, w: 0, tiers: {} }; });
SINGLE.forEach((q) => {
  const axes = new Set();
  q.opts.forEach((o) => Object.keys(o.s).forEach((k) => axes.add(k)));
  axes.forEach((k) => {
    const w = Math.max(...q.opts.map((o) => Math.abs(o.s[k] || 0)));
    cov[k].n++; cov[k].w += w;
    cov[k].tiers[w] = (cov[k].tiers[w] || 0) + 1;
  });
});
console.log(`  ${"审美轴".padEnd(12)}${"题数".padStart(5)}${"总权重".padStart(9)}   权重档`);
LEGACY.forEach((a) => {
  const t = Object.entries(cov[a].tiers).map(([w, n]) => `${w}×${n}`).join(" ");
  console.log(`  ${a.padEnd(12)}${String(cov[a].n).padStart(5)}${cov[a].w.toFixed(2).padStart(9)}   ${t}`
    + (LIGHT.includes(a) ? "   光影轴" : ""));
});
const lightW = LIGHT.reduce((s, a) => s + cov[a].w, 0);
const heavyW = LEGACY.filter((a) => !LIGHT.includes(a)).reduce((s, a) => s + cov[a].w, 0);
console.log(`  光影两轴总权重 ${lightW.toFixed(2)} / 其余七轴 ${heavyW.toFixed(2)}`
  + `  →  逐轴比 = ${(lightW / 2 / (heavyW / 7)).toFixed(2)}×`);
// 实测（不再是旧文档里写死的那句）：bright 只在 4 道题里出现（≠6），contrasty 是 6 题 × 0.6。
// 两句都从 cov 现算，题库一变就跟着变。
console.log(`  口径登记（现算）：想达到「光影各 6 题 × 0.6 = 3.60」还差 `
  + `bright ${6 - cov.bright.n} 题（实测 ${cov.bright.n} 题 × 0.6 = ${cov.bright.w.toFixed(2)}）；`
  + `contrasty 实测 ${cov.contrasty.n} 题 / 权重档 `
  + Object.entries(cov.contrasty.tiers).map(([w, n]) => `${w}×${n}`).join(" ")
  + ` = ${cov.contrasty.w.toFixed(2)}`);
const offTier = LIGHT.flatMap((k) => Object.entries(cov[k].tiers)
  .filter(([w]) => Math.abs(Number(w) - 0.6) > 1e-9)
  .map(([w, n]) => `${k} 有 ${n} 题用了 ${w}`));
console.log(`  光影轴里用了非 0.6 档的：${offTier.length ? "⚠ " + offTier.join("、") : "0 处 ✓"}`);

console.log(`\n  ${"画风轴".padEnd(12)}${"题数".padStart(5)}${"总权重".padStart(9)}   权重档`);
STYLE.forEach((a) => {
  const t = Object.entries(cov[a].tiers).map(([w, n]) => `${w}×${n}`).join(" ");
  console.log(`  ${a.padEnd(12)}${String(cov[a].n).padStart(5)}${cov[a].w.toFixed(2).padStart(9)}   ${t}`);
});
{ // 9 条画风轴：每条恰好 2 题（偶数 ⇒ 四列之和可归零），瘦轴用 0.6 档
  const odd = STYLE.filter((k) => cov[k].n % 2 !== 0);
  const zero = STYLE.filter((k) => cov[k].n === 0);
  console.log(`  9 条画风轴「题数为偶数」：${odd.length ? "✗ " + odd.join("、") : "✓"}`
    + `；没被覆盖的：${zero.length ? "✗ " + zero.join("、") : "0 条 ✓"}`
    + `；低档（0.6）的轴：` + STYLE.filter((k) => cov[k].tiers["0.6"]).join("、"));
}

console.log(`\n  ${"画法轴".padEnd(16)}${"题数".padStart(5)}${"总权重".padStart(9)}   权重档`);
TECH.forEach((a) => {
  const t = Object.entries(cov[a].tiers).map(([w, n]) => `${w}×${n}`).join(" ");
  console.log(`  ${a.padEnd(16)}${String(cov[a].n).padStart(5)}${cov[a].w.toFixed(2).padStart(9)}   ${t}`);
});
{ // 5 道画法题 × 每题 2 轴 = 10 个轴位 = 5 类 × 2 次（5-环）⟹ 每条轴恰好 2 题、
  //   满偏一律 2.4、逐列残留同形。水彩淡彩按口径不出题（6 张），算 0 次 = 偶数。
  const odd = TECH.filter((k) => cov[k].n % 2 !== 0);
  const zero = TECH.filter((k) => cov[k].n === 0);
  console.log(`  6 条画法轴「题数为偶数」：${odd.length ? "✗ " + odd.join("、") : "✓"}`
    + `；没出题的：${zero.length ? zero.join("、") : "0 条"}（按口径不出题，不是漏）`);
  const off = TECH.filter((k) => cov[k].n && Math.abs(cov[k].w - 2.4) > 1e-9);
  console.log(`  出题的五条满偏全为 2.4：${off.length ? "✗ " + off.join("、") : "✓"}`);
}

console.log(`\n  形态轴（多选题 ${MQS.map((q) => q.id).join("/")}，每个选项只挂自己那一类）：`);
FORM.forEach((k) => {
  console.log(`    ${k.padEnd(13)} w = ${W[k.slice(5)].toFixed(2)}（每题；`
    + `${MQS.length} 题累加总推力 ${(W[k.slice(5)] * MQS.length).toFixed(2)}）`);
});
// 三道题的形态排列（必须两两不同 + 六类都能进前四位）
console.log("\n  形态题选项顺序（0/1/3 左旋）：");
MQS.forEach((q) => console.log(`    ${q.id}  ` +
  q.opts.map((o) => o.form).join(" / ")));
{
  const keys = MQS.map((q) => q.opts.map((o) => o.form).join("/"));
  const cover = {};
  MQS.forEach((q) => q.opts.slice(0, 4).forEach((o) => {
    cover[o.form] = (cover[o.form] || 0) + 1;
  }));
  const miss = FORMS.filter((f) => !cover[f]);
  console.log(`    两两不同 ${new Set(keys).size === keys.length ? "✓" : "✗"}；`
    + `「前 4 位」覆盖 ` + FORMS.map((f) => `${f}×${cover[f] || 0}`).join("  ")
    + `；七类都能被扫到 ${miss.length ? "✗ " + miss.join("、") : "✓"}`);
}

// 「一路只选位置 k」在形态题上也要跟着走（否则四列会拿到同一个值）
const res = [0, 1, 2, 3].map((pos) => {
  const a = {};
  SINGLE.forEach((q) => {
    const s = q.opts[pos].s;
    for (const key of Object.keys(s)) a[key] = (a[key] || 0) + s[key];
  });
  MQS.forEach((q) => {
    const o = q.opts[pos];
    if (!o) return;
    for (const key of Object.keys(o.s)) a[key] = (a[key] || 0) + o.s[key];
  });
  return a;
});
console.log(`\n  ${"轴".padEnd(13)}  第1项   第2项   第3项   第4项      四列之和`);
AXES.forEach((ax) => {
  const vals = res.map((v) => v[ax] || 0);
  const s = vals.reduce((x, y) => x + y, 0);
  // 审美轴：四列之和必须为 0（每轴出现偶数次、正负在位置间轮转）。
  // 形态轴：每题只有 1 个选项带某一类，四列之和 = 该形态在「前 4 位」出现的次数 × 其
  //         单题权重 —— 结构上不为 0（这不是错，是「一道多选换四道单选」的直接后果）。
  //         0/1/3 左旋之后七类都能拿到非零值，不再有「某类四列全 0」的死角。
  // 画风轴：和审美轴同一口径（每题 2 正 2 负 → 四列之和必须为 0）。
  const tag = ax.startsWith("form_") ? (s > 1e-9 ? "  （结构使然）" : "  ⚠ 全 0")
    : (Math.abs(s) < 1e-9 ? "  ✓" : "  ⚠ 不为 0");
  console.log(`  ${ax.padEnd(13)}` + vals.map((v) => v.toFixed(2).padStart(8)).join("")
    + s.toFixed(2).padStart(12) + tag);
});
const worstLegacy = Math.max(...LEGACY.concat(STYLE).concat(TECH).flatMap((k) => {
  const s = res.reduce((x, v) => x + (v[k] || 0), 0);
  return [Math.abs(s)];
}));
console.log(`  9 个审美轴 + 9 条画风轴 + 6 条画法轴的「四列之和」最大 |值| = ${worstLegacy.toFixed(6)}（应为 0）`);
const deadForm = FORM.filter((k) => res.reduce((x, v) => x + (v[k] || 0), 0) <= 1e-9);
console.log(`  7 个形态轴里「四列全 0」（永远扫不到）的：`
  + `${deadForm.length ? "✗ " + deadForm.join("、") : "0 个 ✓"}`);

/* ④ 选项字数 */
console.log("\n" + "=".repeat(74));
console.log(`④ 选项长度（汉字数，口径上限 ${MAX_HAN}，来自 scripts/check_limits.json）`);
console.log("=".repeat(74));
let maxHan = 0, maxOpt = "", longCount = 0;
Q.forEach((q) => q.opts.forEach((o) => {
  const n = (o.t.match(/[\u4e00-\u9fff]/g) || []).length;
  if (n > maxHan) { maxHan = n; maxOpt = `${q.id} ${o.t}`; }
  if (n > MAX_HAN) longCount++;
}));
const lens = Q.flatMap((q) => q.opts.map((o) => (o.t.match(/[\u4e00-\u9fff]/g) || []).length));
console.log(`  最长 ${maxHan} 字（${maxOpt}）；超 ${MAX_HAN} 字的选项 ${longCount} 个`);
console.log(`  平均 ${(lens.reduce((a, b) => a + b, 0) / lens.length).toFixed(1)} 字`);
