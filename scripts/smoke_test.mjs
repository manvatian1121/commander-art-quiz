// 美术审美测试 · 无头冒烟测试
//   不需要真浏览器：用最小 DOM 桩把 art_quiz.html 里那段真实的应用脚本跑起来，
//   走完整流程、验算打分、把推荐的插画文件拿去磁盘上核对。
// 用法： node scripts/smoke_test.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");                       // commander-art-quiz/
const HTML_PATH = path.join(ROOT, "art_quiz.html");
const LEGACY_AXES = ["warm", "bright", "vivid", "rich", "detailed",
                     "contrasty", "modern", "borderless", "starart"];
// 变异人形 → 人形异类；兽形拆成三类（可爱小兽 / 写实动物 / 凶猛巨兽）→ 7 个形态轴
const FORM_AXES = ["form_纯人类", "form_人形异类", "form_凶猛巨兽",
                   "form_扭曲异形", "form_可爱小兽", "form_机械构装", "form_写实动物"];
// 2026-10-13 新增：由 mood 标签做的 9 条「画风轴」（多标签中心化，SD 同样 0.2887）
const STYLE_AXES = ["style_神秘", "style_史诗", "style_黑暗", "style_怪诞", "style_激烈",
                    "style_温暖", "style_宁静", "style_可爱", "style_忧郁"];
const AXES = LEGACY_AXES.concat(FORM_AXES).concat(STYLE_AXES);
const FORMS = FORM_AXES.map((a) => a.replace("form_", ""));
// ⚠️ 题数 / 插画数一律从题库和 payload 推导，不写死 —— 上一轮写死 31、
//    题库一换成 27 全红。下面这几个常量只是「格式约定」，不随题库变动。
let N_Q, N_SINGLE, N_MULTI, N_ARTS, MQS, MQ, FORM_W, FORM_W_BY_Q, FORM_ORDERS,
    SINGLE_W, SINGLE_USES;
const N_EXCLUDED = 8;
const SINGLE_OPTS = 4;          // 单选审美题固定 2×2 叉乘 = 4 项
const LIGHT_W = 0.6;            // 光影两轴的单题权重
const HEAVY_W = 1.2;            // 其余七个审美轴（= 光影的 2 倍）
// 选项汉字数上限：**唯一来源 scripts/check_limits.json**，别处不许再写死数字
// （2026-10-13 统一：此前 audit_questions.py / verify_questions.mjs 用 12 汉字、
//   rewrite_bank_manual.py 用 len(文本) > 16（含标点），三处口径不一致）
const OPTION_MAX_HAN = JSON.parse(
  fs.readFileSync(path.join(HERE, "check_limits.json"), "utf8")).option_max_han;
const HAN_RE = /[\u4e00-\u9fff]/g;
const hanLen = (s) => (String(s).match(HAN_RE) || []).length;
// 被裁定剔除的 8 格：结果页永远不能推荐到它们
//   #88  + 扩池的 4 张（始霸埃泰力 ×2 金色龙纹圆章、谜样巨身兽欧威卡 ×2 画面碎片化）
//   + 2026-10-13 追加：#27（Animar 那幅主体是风景）、#263（下载到 placeholder 图）、
//     #375（夜色里的塔状构件，画面里没有活物）
const EXCLUDED_IDS = [
  "4351a7e0-078d-4bb8-b3d7-93b2126a3c13",   // #88  生机核欧那斯
  "2a96e266-775f-4c6f-a33c-0450227fa9d2",   // #278 始霸埃泰力（金色龙纹圆章）
  "b0739892-9047-4144-9acb-a586258befbc",   // #279 始霸埃泰力（同上，另一印刷版）
  "104f9065-c036-4674-a7b6-b97de9e293cd",   // #298 谜样巨身兽欧威卡（碎片化）
  "d722ff79-3a0c-4a50-89ff-7455b479f34f",   // #299 谜样巨身兽欧威卡（水印脏图）
  "145f58ea-1f36-4fda-b7a0-23c918c6472b",   // #27  元素之魂阿尼玛（画面主体是风景）
  "f5410963-0e71-46e7-bef9-99edb184c2fe",   // #263 残暴合体钨拉雷（placeholder 图）
  "667dd16e-ecd6-4301-8663-3c13a615e5b8",   // #375 实界晶片（夜景构件，无活物）
];
// 光影两轴：题量一样，但权重压到其它轴的一半（总权重 = 其余的 50%）
// darkarea 2026-10-13 下线（与 bright 实测 r = −0.830，是同一根轴的负向）
const LIGHT_AXES = ["bright", "contrasty"];
// 题库硬约束：单题权重区间（与 make_questions.py / solve_form_weights.py 一致）
const W_MIN = 0.5, W_MAX = 2.0;

/* ---------- 从题库推导出来的量（改题库就不该再红） ---------- */
/** 把题库扫一遍，算出所有「不该写死」的常量。放在 payload 解析之后调用。 */
function deriveFromBank() {
  N_Q = DATA.q.length;
  N_SINGLE = DATA.q.filter((q) => !q.multi).length;
  MQS = DATA.q.filter((q) => q.multi);                        // b01 / b02 / b03
  N_MULTI = MQS.length;
  N_ARTS = DATA.a.length;
  MQ = MQS[0] || null;                                        // 第一道（兼容旧断言）

  // 每道形态题自己的 6 元形态序列 —— b01/b02/b03 是三种不同排列。
  // payload 里**不**带 o.form（build_html.py 只内嵌 t/s），所以从「这一项挂的 form_* 轴」读。
  const formOfOpt = (o) => {
    const ks = Object.keys(o.s).filter((k) => k.startsWith("form_"));
    return ks.length === 1 ? ks[0].slice(5) : null;
  };
  FORM_ORDERS = MQS.map((q) => q.opts.map(formOfOpt));

  // 每道形态题的「单题权重表」，以及三题是否共用同一组值
  FORM_W_BY_Q = {};
  FORM_W = {};
  MQS.forEach((q) => {
    const row = {};
    q.opts.forEach((o) => {
      const f = formOfOpt(o);
      if (f && row[f] === undefined) row[f] = o.s["form_" + f];
    });
    FORM_W_BY_Q[q.id] = row;
  });
  if (MQS.length) Object.assign(FORM_W, FORM_W_BY_Q[MQS[0].id]);

  // 单选审美题：「单题权重」= 该轴在四个选项里的最大绝对值；以及每条轴用了几道题
  SINGLE_W = {};
  SINGLE_USES = {};
  DATA.q.filter((q) => !q.multi).forEach((q) => {
    const axes = new Set();
    q.opts.forEach((o) => Object.keys(o.s).forEach((k) => axes.add(k)));
    axes.forEach((k) => {
      SINGLE_W[k] = Math.max(SINGLE_W[k] || 0, ...q.opts.map((o) => Math.abs(o.s[k] || 0)));
      SINGLE_USES[k] = (SINGLE_USES[k] || 0) + 1;
    });
  });
}
/**
 * 「勾一类 → 连贯人设下 Top3 全是这一类」这个**更强**的判据需要多大的**总**推力。
 * 实测（scripts/solve_form_weights.py §④ + 304 组人设扫描）：总推力 T ≥ 3.0 时大类在
 * 4 个连贯人设下都稳定占满 Top3。题库硬约束「单题权重 ≤ 2.0」把单题 α 卡在
 * 2.0·min k ≈ 1.21/题 —— 单题时 T 只有 1.21、这条断言只能降级；**三题累加后
 * T ≈ 3.64 ≥ 3.0，这条现在真的在跑**（这正是「从 1 道扩到 3 道」的意义）。
 */
const TOP3_PURE_ALPHA = 3.0;
/**
 * 「随机噪声人设」（对 26 道题随机作答 = 没有连贯口味）下的纯度下限。
 * 这类人设的审美偏好方向随机、幅度可与总推力相比，实测最小纯度会掉到 0.00（最瘦的
 * 可爱小兽 / 机械构装 / 扭曲异形），所以随机人设只断言**平均**纯度、最小值只打印。
 * 把「全部人设 ≥ 2/3」当硬指标需要单题 α ≥ 1.81（权重上限 2.98），**必须破约束**，
 * 见 solve_form_weights.py §④ J3-a₃。
 */
const NOISE_MEAN_MIN = 0.8;

const problems = [];
let passCount = 0;
function check(label, fn) {
  try { fn(); passCount++; console.log(`  \u2713 ${label}`); }
  catch (error) { problems.push(`${label}: ${error.message}`); console.log(`  \u2717 ${label} \u2014 ${error.message}`); }
}
function section(title) { console.log(`\n${title}`); }
function assert(cond, msg) { if (!cond) throw new Error(msg); }
function sum(xs) { return xs.reduce((a, b) => a + b, 0); }

/* ------------------------------------------------------------------ *
 * 1. 取出 HTML 里内嵌的 payload（这就是"不能 fetch"的那份数据）
 * ------------------------------------------------------------------ */
if (!fs.existsSync(HTML_PATH)) {
  console.error(`找不到 ${HTML_PATH}，先跑 python scripts/build_html.py`);
  process.exit(1);
}
const html = fs.readFileSync(HTML_PATH, "utf8");

const payloadMatch = html.match(
  /<script id="payload" type="application\/json">([\s\S]*?)<\/script>/);
if (!payloadMatch) throw new Error("HTML 里找不到内嵌 payload");
const payloadText = payloadMatch[1].replace(/<\\\//g, "</");
let DATA;
try { DATA = JSON.parse(payloadText); }
catch (error) { throw new Error(`内嵌 payload 不是合法 JSON：${error.message}`); }
deriveFromBank();

/**
 * α 的实测上限 = W_MAX · min_f k_f，其中 k_f = sd(vec_f)/√(p_f(1−p_f))（形态轴的自然标度）。
 * 一律从 payload 现算（所以必须放在 payload 解析之后），池子一变就跟着变 —— 写死必然失配。
 * ⚠️ 这是**单题** α；形态题有 N_MULTI 道、每道给同一组权重，实际推力是 N_MULTI 倍。
 */
const K_OF = {};
FORMS.forEach((f) => {
  const vals = DATA.a.map((a) => a.vec["form_" + f]);
  const mean = sum(vals) / vals.length;
  const sd = Math.sqrt(sum(vals.map((v) => (v - mean) ** 2)) / vals.length);
  const p = DATA.a.filter((a) => a.form === f).length / DATA.a.length;
  K_OF[f] = sd / Math.sqrt(p * (1 - p));
});
const ALPHA_MAX = W_MAX * Math.min(...FORMS.map((f) => K_OF[f]));
const ALPHA_TOTAL = ALPHA_MAX * N_MULTI;      // N 道累加后的总推力
/**
 * 勾选集合选中的类之间「平均分差」的容差。
 * 从第一性原理算：权重只存 2 位小数 → 单题 r_c 的舍入残差 ≤ 0.005·k_c；
 * 看的是类间**极差**（2 倍），N_MULTI 道题累加 → 2·0.005·max k·N_MULTI。
 * 单题时这个式子给 0.0111（比旧的固定 0.03 还紧）；三题时给 0.0334（实测 0.0207）。
 */
const ALPHA_TOL = Math.max(0.03,
  2 * 0.005 * Math.max(...FORMS.map((f) => K_OF[f])) * N_MULTI);

/* ------------------------------------------------------------------ *
 * 2. 最小 DOM 桩
 * ------------------------------------------------------------------ */
class Node {
  constructor(tag) {
    this.tag = tag; this.className = ""; this.textContent = ""; this.hidden = false;
    this.children = []; this.parentNode = null;
    this.attrs = {}; this.dataset = {}; this.style = { width: "", setProperty() {} };
    this._html = "";
  }
  set innerHTML(v) { this._html = String(v); this.children = []; }
  get innerHTML() { return this._html + this.children.map((c) => c.innerHTML).join(""); }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  removeChild(child) {
    const i = this.children.indexOf(child);
    if (i >= 0) this.children.splice(i, 1);
    return child;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  addEventListener() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
}

const byId = {};
const document = {
  body: new Node("body"),
  createElement: (tag) => new Node(tag),
  getElementById(id) {
    if (id === "payload") return { textContent: payloadText };
    if (!byId[id]) byId[id] = new Node(`div#${id}`);
    return byId[id];
  },
  addEventListener(type, fn) { document.__clickListener = (type === "click") ? fn : document.__clickListener; },
};
globalThis.document = document;
globalThis.window = { scrollTo() {} };

/* ------------------------------------------------------------------ *
 * 3. 执行 HTML 里的应用脚本（最后一个 <script> 块）
 * ------------------------------------------------------------------ */
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if (!scripts.length) throw new Error("HTML 里没有可执行的 <script> 块");
(0, eval)(scripts[scripts.length - 1][1]);

// 应用脚本把接口挂在 window 上；测试里 window 是桩对象，不是 globalThis，
// 所以两边都找一下（真浏览器里两者是同一个对象）。
const app = globalThis.__artQuiz || globalThis.window.__artQuiz;
if (!app) throw new Error("__artQuiz 没有暴露，应用脚本可能提前抛错了");
const imgErrorHandler = globalThis.__artQuizImgError || globalThis.window.__artQuizImgError;

const rendered = () => document.getElementById("app").innerHTML;
const onResult = () => rendered().includes("你的审美画像");

/** 造一个假 click 事件，沿 parentNode 冒泡到 document 的委托监听器 */
function dispatch({ attrs = {}, parent = null }) {
  const el = new Node("button");
  Object.assign(el.attrs, attrs);
  if (parent) el.parentNode = parent;
  const listener = document.__clickListener;
  if (typeof listener !== "function") throw new Error("document 上没有 click 委托监听器");
  listener({ target: el });
  return el;
}

/**
 * 走一遍完整流程。
 *   picker(q, step) -> 单选：要选的下标；多选：要勾的下标数组/Set（空数组 = 一个都不勾）
 *   viaClick        -> true 时走 DOM 事件委托（验 UI 接线），false 直接调引擎
 *   formSet         -> 多选题要勾的形态名（给定时忽略 picker 对多选题的返回值）
 */
function walk(picker, viaClick = false, limit = 400, formSet = null) {
  const mp = formSet ? formMultiPicker(formSet) : null;
  app.start();
  const visited = [];
  for (let step = 0; step < limit; step++) {
    if (onResult()) return { visited, steps: step, finished: true };
    const q = app.Q[app.getState().index];
    if (!q) return { visited, steps: step, finished: false };
    const raw = (q.multi && mp) ? mp(q) : picker(q, step);
    const list = Array.isArray(raw) || raw instanceof Set ? [...raw] : [raw];
    const picks = list.map((v) => ((v % q.opts.length) + q.opts.length) % q.opts.length);
    visited.push(q.id);
    if (q.multi) {
      if (viaClick) {
        picks.forEach((p) => dispatch({ attrs: { "data-act": "toggle", "data-multi": "1", "data-i": String(p) } }));
        // 一个都不勾时「下一题」是 disabled，走 UI 就不该再往前
        if (!app.canAdvance()) return { visited, steps: step, finished: false };
        dispatch({ attrs: { "data-act": "next" } });
      } else {
        picks.forEach((p) => app.toggle(p));
        if (!app.canAdvance()) return { visited, steps: step, finished: false };
        app.advance();
      }
    } else {
      const picked = picks[0];
      if (viaClick) dispatch({ attrs: { "data-act": "choose", "data-i": String(picked) } });
      else app.choose(picked);
    }
  }
  return { visited, steps: limit, finished: false };
}

/** 单选策略：一律返回单个下标。多选题由 picksFor 的 multiPicker 单独决定 */
const PICK = {
  first: () => 0,
  second: () => 1,
  third: () => 2,
  last: () => 3,
  alternate: (q, s) => (s % 2 ? q.opts.length - 1 : 0),
  cycle: (q, s) => s % 3,
};

/** 多选题的勾选策略（picksFor 用）—— 覆盖「勾 1 个 / 勾 3 个 / 全勾 / 一个都不勾」 */
const MULTI_PICK = {
  firstOption: () => [0],
  all: (q) => q.opts.map((_, i) => i),
  none: () => [],
  /** 勾前 k 个 */
  upTo: (k) => (q) => q.opts.map((_, i) => i).filter((i) => i < k),
};

/** 只算数据、不碰 DOM：给某个策略算出推荐。多选题按 multiPicker 返回的数组累加 */
function picksFor(picker, multiPicker) {
  const answers = {};
  app.Q.forEach((q, i) => {
    if (q.multi) {
      const raw = multiPicker ? multiPicker(q, i) : MULTI_PICK.firstOption(q, i);
      answers[q.id] = [...raw].sort((a, b) => a - b);
    } else {
      answers[q.id] = picker(q, i);
    }
  });
  const pref = app.prefVector(answers);
  return { pref, answers, picks: app.recommend(pref, 3) };
}

/** 多选题的勾选策略：勾 formSet 里的类（找不到对应选项就跳过） */
function formMultiPicker(formSet) {
  const want = new Set([...formSet].map((f) => (f.startsWith("form_") ? f.slice(5) : f)));
  return (q) => {
    const out = [];
    q.opts.forEach((o, i) => {
      const ks = Object.keys(o.s).filter((k) => k.startsWith("form_"));
      if (ks.length === 1 && want.has(ks[0].slice(5))) out.push(i);
    });
    return out;
  };
}

/** 审美题固定「一路选第 1 项」，只改多选题的勾选 —— 隔离出形态那一道题的作用 */
function picksForForm(formSet) {
  const mp = formMultiPicker(formSet);
  const answers = {};
  app.Q.forEach((q) => {
    if (q.multi) answers[q.id] = mp(q);
    else answers[q.id] = 0;
  });
  const pref = app.prefVector(answers);
  return { pref, answers, picks: app.recommend(pref, 3) };
}

/** 把 payload 里的 img 解析成磁盘真实路径 */
function resolveImg(img) {
  const direct = path.join(ROOT, DATA.base || "", img);
  if (fs.existsSync(direct)) return direct;
  const underData = path.join(ROOT, "data", img);   // local_art_crop 原本相对 data/
  if (fs.existsSync(underData)) return underData;
  return null;
}

console.log("=".repeat(70));
console.log("美术审美测试 · 冒烟测试");
console.log(`HTML ${path.relative(ROOT, HTML_PATH)}  ${fs.statSync(HTML_PATH).size.toLocaleString()} 字节`);
console.log("=".repeat(70));

/* ================================================================== *
 * 场景 0：内嵌数据自洽
 * ================================================================== */
section("[场景 0] 内嵌数据");

check(`payload 完整：${N_Q} 题（${N_SINGLE} 单选 × ${SINGLE_OPTS} 选项 + ${N_MULTI} 多选）/ ${N_ARTS} 张插画`, () => {
  assert(DATA.q.length === N_Q, `题目 ${DATA.q.length} 道，应为 ${N_Q}`);
  DATA.q.forEach((q) => {
    if (q.multi) {
      assert(q.opts.length >= 3, `${q.id} 是多选题但只有 ${q.opts.length} 个选项`);
    } else {
      assert(q.opts.length === SINGLE_OPTS, `${q.id} 选项 ${q.opts.length} 个，应为 ${SINGLE_OPTS}`);
      assert(!q.multi, `${q.id} 不该带 multi 标记`);
    }
  });
  assert(DATA.a.length === N_ARTS, `插画 ${DATA.a.length} 张，应为 ${N_ARTS}`);
  const ids = new Set(DATA.a.map((a) => a.art_id));
  assert(ids.size === N_ARTS, "payload 里有重复的 art_id");
});

check(`新题确实被加载：${N_SINGLE} 道审美题在前、${N_MULTI} 道形态题在末尾，顺序正确`, () => {
  const ids = DATA.q.map((q) => q.id);
  // 审美题 = aNN（图像/元数据轴）+ sNN（2026-10-13 新增的画风题）
  assert(ids.slice(0, N_SINGLE).every((id) => /^[as]\d{2}$/.test(id)),
    `审美题应全是 aNN / sNN，实际 ` + ids.slice(0, N_SINGLE).join(","));
  assert(ids.slice(N_SINGLE).join(",") === MQS.map((q) => q.id).join(","),
    `末尾应为 ${MQS.map((q) => q.id).join(",")}，实际 ${ids.slice(N_SINGLE).join(",")}`);
  assert(N_MULTI === 3, `形态多选题应当是 3 道（b01/b02/b03），实际 ${N_MULTI} 道`);
});

check("内嵌题目与 data/questions.json 逐字一致（构建没改内容）", () => {
  const src = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "questions.json"), "utf8"));
  assert(src.questions.length === N_Q,
    `questions.json 里有 ${src.questions.length} 题，应为 ${N_Q}`);
  src.questions.forEach((q, i) => {
    const p = DATA.q[i];
    assert(p.id === q.id, `第 ${i + 1} 题的 id 不一致：${p.id} vs ${q.id}`);
    assert(p.q === q.q, `${q.id} 的题干被改过`);
    assert(!!p.multi === !!q.multi, `${q.id} 的多选标记被改过`);
    q.opts.forEach((o, j) => {
      assert(p.opts[j].t === o.t, `${q.id} 第 ${j + 1} 项的文本被改过`);
      const want = Object.entries(o.s).filter(([, v]) => Math.abs(v) > 1e-12);
      const got = Object.entries(p.opts[j].s);
      assert(want.length === got.length, `${q.id} 第 ${j + 1} 项的轴数被改过`);
      want.forEach(([k, v]) => assert(Math.abs((p.opts[j].s[k] || 0) - v) < 1e-12,
        `${q.id} 第 ${j + 1} 项的 ${k} 权重被改过：${p.opts[j].s[k]} vs ${v}`));
    });
  });
  // 单选审美题只用 9 个审美轴 + 9 个画风轴（形态只出现在那三道多选题里）
  DATA.q.filter((q) => !q.multi).forEach((q) => {
    q.opts.forEach((o) => Object.keys(o.s).forEach((k) =>
      assert(LEGACY_AXES.includes(k) || STYLE_AXES.includes(k),
        `${q.id} 里出现了非原有轴 ${k}`)));
  });
  // 多选题只用 7 个形态轴，且每个选项标的 form 与它挂的轴一致（payload 不带 o.form，
  // 所以这条要对着题库源文件查）
  assert(MQS.length > 0, "题库里没有多选题");
  MQS.forEach((m) => m.opts.forEach((o) => Object.keys(o.s).forEach((k) =>
    assert(FORM_AXES.includes(k), `${m.id} 混进了非形态轴 ${k}`))));
  {
    const srcMulti = fs.readFileSync(path.join(ROOT, "data", "questions.json"), "utf8");
    JSON.parse(srcMulti).questions.filter((q) => q.multi).forEach((q) => {
      q.opts.forEach((o, i) => {
        const ks = Object.keys(o.s).filter((k) => k.startsWith("form_"));
        assert(ks.length === 1, `${q.id} 第 ${i + 1} 项挂了 ${ks.length} 个形态轴`);
        assert(o.form === ks[0].slice(5),
          `${q.id} 第 ${i + 1} 项标了 form=${o.form} 却挂着 ${ks[0]}`);
      });
    });
  }
  // darkarea 已经下线：题目里不能有任何一道还挂着它
  DATA.q.forEach((q) => q.opts.forEach((o) =>
    assert(!("darkarea" in o.s), `${q.id} 还挂着已下线的 darkarea`)));
  assert(!DATA.axes.includes("darkarea"), "payload.axes 里还留着已下线的 darkarea");
});

check(`7 个形态轴 + 9 个画风轴进了 payload，且每张图「自己那一类」是最高的（${N_ARTS}/${N_ARTS}）`, () => {
  assert(Array.isArray(DATA.axes) && DATA.axes.length === AXES.length,
    `payload.axes 有 ${DATA.axes && DATA.axes.length} 个轴，应为 ${AXES.length}`);
  AXES.forEach((k) => assert(DATA.axes.includes(k), `payload.axes 里缺 ${k}`));
  assert(Array.isArray(DATA.forms) && DATA.forms.join(",") === FORMS.join(","),
    `payload.forms 应为 ${FORMS.join(",")}，实际 ${DATA.forms}`);
  DATA.a.forEach((a) => {
    assert(FORMS.includes(a.form), `${a.art_id} 的 form=${a.form} 不在 7 类里`);
    const vals = {};
    FORM_AXES.forEach((k) => { vals[k] = a.vec[k]; });
    const top = Object.keys(vals).reduce((x, y) => (vals[y] > vals[x] ? y : x));
    assert(top === "form_" + a.form,
      `${a.art_id}（${a.form}）的形态轴最高项是 ${top}`);
  });
});

check(`每张插画都有 ${AXES.length} 个轴且数值有限（9 个审美轴仍在 ±1 内）`, () => {
  DATA.a.forEach((a) => {
    AXES.forEach((k) => {
      const v = a.vec[k];
      assert(typeof v === "number" && Number.isFinite(v), `${a.art_id} 的 ${k} 不是有限数`);
    });
    // 旧轴是百分位映射，取值必然在 ±1 内；形态轴是中心化 one-hot，SD 同样 0.2887，
    // 但稀有形态的单点值会超过 1（可爱小兽 p=1.6% → 最高 +2.2485）
    LEGACY_AXES.forEach((k) => {
      assert(Math.abs(a.vec[k]) <= 1.0001, `${a.art_id} 的 ${k}=${a.vec[k]} 超出 ±1`);
    });
    FORM_AXES.forEach((k) => {
      assert(Math.abs(a.vec[k]) <= 2.4, `${a.art_id} 的 ${k}=${a.vec[k]} 超出 ±2.4`);
    });
    // 画风轴同样是中心化指示变量：越瘦的轴单点值越大（忧郁 p=1.1% → 最高 +2.76）
    STYLE_AXES.forEach((k) => {
      assert(Math.abs(a.vec[k]) <= 3.0, `${a.art_id} 的 ${k}=${a.vec[k]} 超出 ±3.0`);
    });
  });
});

check("剔除的 8 张图完全不在 payload 里（结果页推荐不到）", () => {
  const ids = new Set(DATA.a.map((a) => a.art_id));
  EXCLUDED_IDS.forEach((id) => assert(!ids.has(id), `被剔除的 ${id} 还在 payload 里`));
  // 图文件仍在磁盘上（只是不参与）
  EXCLUDED_IDS.forEach((id) => {
    const fp = path.join(ROOT, "data", "cards", "art_crop", `${id}.jpg`);
    assert(fs.existsSync(fp), `被剔除的图文件不该删除：${fp}`);
  });
});

check("题目权重有正有负，且每道单选题每轴正负各半（求和为 0）", () => {
  DATA.q.filter((q) => !q.multi).forEach((q) => {
    const axes = new Set();
    q.opts.forEach((o) => Object.keys(o.s).forEach((k) => axes.add(k)));
    axes.forEach((k) => {
      const vals = q.opts.map((o) => o.s[k] || 0);
      assert(Math.abs(vals.reduce((x, y) => x + y, 0)) < 1e-9, `${q.id} 的 ${k} 没有居中`);
      assert(vals.filter((v) => v > 0).length === 2 && vals.filter((v) => v < 0).length === 2,
        `${q.id} 的 ${k} 不是 2 正 2 负：${vals}`);
    });
  });
});

check(`形态多选题：${N_MULTI} 道都在、都带 multi、各 6 个选项、每项只挂自己那一类`, () => {
  assert(N_MULTI === 3, `形态多选题应当 3 道，实际 ${N_MULTI} 道`);
  MQS.forEach((q) => {
    assert(!!q.multi, `${q.id} 没有 multi 标记`);
    assert(q.opts.length === FORMS.length,
      `${q.id} 有 ${q.opts.length} 个选项，应为 ${FORMS.length}`);
  });
  MQS.forEach((q) => {
    const seen = new Set();
    q.opts.forEach((o, i) => {
      const ks = Object.keys(o.s);
      assert(ks.length === 1, `${q.id} 第 ${i + 1} 项挂了 ${ks.length} 个轴，应当 1 个`);
      const k = ks[0];
      assert(k.startsWith("form_"), `${q.id} 第 ${i + 1} 项挂的不是形态轴：${k}`);
      assert(!seen.has(k), `${q.id} 的 ${k} 被挂在多个选项上，勾一次会加两份`);
      seen.add(k);
      const v = o.s[k];
      assert(v > 0, `${q.id} 的 ${k} 权重 ${v} 不是正的（多选题没有负项）`);
      assert(v >= W_MIN - 1e-9 && v <= W_MAX + 1e-9,
        `${q.id} 的 ${k} 权重 ${v} 越出题库硬约束 ${W_MIN}~${W_MAX}`);
    });
    assert(seen.size === FORMS.length, `${q.id} 只覆盖了 ${seen.size} 类形态`);
  });
});

check("三道形态题的选项顺序两两不同，且 6 个形态在「前 4 位」里各至少出现一次", () => {
  assert(FORM_ORDERS.length === N_MULTI, "形态序列没取全");
  FORM_ORDERS.forEach((o, i) => assert(o.length === FORMS.length && o.every(Boolean),
    `${MQS[i].id} 的形态序列不完整：${o}`));
  // ① 两两不同 —— 这是「位置偏置被摊平」的前提
  const keys = FORM_ORDERS.map((o) => o.join("/"));
  assert(new Set(keys).size === keys.length,
    `有形态序列完全相同的两道题（位置偏置会集中）：${keys.join("  |  ")}`);
  FORM_ORDERS.forEach((o, i) => {
    assert(new Set(o).size === FORMS.length, `${MQS[i].id} 的形态序列有重复：${o}`);
  });
  // ② 逐位置：每个位置上应是 N_MULTI 个**不同**形态（没有任何一类垄断某个位置）
  for (let pos = 0; pos < 4; pos++) {
    const col = FORM_ORDERS.map((o) => o[pos]);
    assert(new Set(col).size === col.length,
      `第 ${pos + 1} 位被同一形态占了多次：${col.join(" / ")}`);
  }
  // ③ 「只勾前四项」的人也得能扫到全部 7 类
  const cover = {};
  FORM_ORDERS.forEach((o) => o.slice(0, 4).forEach((f) => { cover[f] = (cover[f] || 0) + 1; }));
  const missing = FORMS.filter((f) => !cover[f]);
  assert(!missing.length,
    `这些形态在「前 4 位」里一次都不出现：${missing.join("、")}（只勾前四项的人永远扫不到）`);
  console.log("    形态序列：");
  MQS.forEach((q, i) => console.log(`      ${q.id}  ` + FORM_ORDERS[i].join(" / ")));
  console.log("    逐位置：" + [0, 1, 2, 3].map((p) =>
    `第${p + 1}位[${FORM_ORDERS.map((o) => o[p]).join("/")}]`).join("  "));
  console.log("    「前 4 位」覆盖次数：" +
    FORMS.map((f) => `${f} ${cover[f] || 0}`).join("  "));
});

check("三道形态题的权重表完全一致（都等于闭式解 w = α/k）", () => {
  const ref = FORM_W_BY_Q[MQS[0].id];
  MQS.forEach((q) => {
    FORMS.forEach((f) => {
      const v = FORM_W_BY_Q[q.id][f];
      assert(typeof v === "number", `${q.id} 的 ${f} 没有权重`);
      assert(Math.abs(v - ref[f]) < 1e-12,
        `${q.id} 的 ${f} 权重 ${v} 与 ${MQS[0].id} 的 ${ref[f]} 不一致`);
    });
  });
  // 权重与解析式 w = α/k 对齐（α 取约束允许的最大值 → 最重的那类应当正好顶到 2.0）
  const alpha = ALPHA_MAX;
  const worst = Math.max(...FORMS.map((f) => Math.abs(FORM_W[f] - alpha / K_OF[f])));
  assert(worst < 0.006, `权重与闭式解 α/k 的最大偏差 ${worst.toFixed(4)} 太大`);
  assert(Math.abs(Math.max(...FORMS.map((f) => FORM_W[f])) - W_MAX) < 0.006,
    "最重的那类没有顶到单题权重上限 —— α 没取到约束允许的最大值");
});

check("单选题：每题 2 个轴、4 个选项，2 正 2 负、和 = 0，权重落在 0.5~2.0", () => {
  const total = {};
  DATA.q.filter((q) => !q.multi).forEach((q) => {
    const axes = new Set();
    q.opts.forEach((o) => Object.keys(o.s).forEach((k) => axes.add(k)));
    assert(axes.size === 2, `${q.id} 挂了 ${axes.size} 个轴，应为 2`);
    assert(q.opts.length === SINGLE_OPTS, `${q.id} 选项数 ${q.opts.length}`);
    axes.forEach((k) => {
      const vals = q.opts.map((o) => o.s[k] || 0);
      assert(vals.filter((v) => v > 0).length === 2 && vals.filter((v) => v < 0).length === 2,
        `${q.id} 的 ${k} 不是 2 正 2 负：${vals}`);
      assert(Math.abs(sum(vals)) < 1e-9, `${q.id} 的 ${k} 没居中`);
      const w = Math.max(...vals.map(Math.abs));      // 本题该轴的单题权重
      assert(w >= W_MIN - 1e-9 && w <= W_MAX + 1e-9,
        `${q.id} 的 ${k} 单题权重 ${w} 越出题库硬约束 ${W_MIN}~${W_MAX}`);
      assert(vals.every((v) => Math.abs(Math.abs(v) - w) < 1e-9),
        `${q.id} 的 ${k} 四个选项不是等强：${vals}`);
      total[k] = (total[k] || 0) + w;
    });
  });
  // 单选审美题每轴的单题权重只允许 0.6 / 1.2 两档（题库设计口径），且都落在硬约束内
  const rawW = {};
  DATA.q.filter((q) => !q.multi).forEach((q) => {
    const axes = new Set();
    q.opts.forEach((o) => Object.keys(o.s).forEach((k) => axes.add(k)));
    axes.forEach((k) => {
      const w = Math.max(...q.opts.map((o) => Math.abs(o.s[k] || 0)));
      assert(Math.abs(w - LIGHT_W) < 1e-9 || Math.abs(w - HEAVY_W) < 1e-9,
        `${q.id} 的 ${k} 单题权重 ${w} 不是 ${LIGHT_W}/${HEAVY_W} 两档之一`);
      (rawW[k] = rawW[k] || []).push([q.id, w]);
    });
  });
  console.log("    轴覆盖与单题权重：" + LEGACY_AXES.map((k) => {
    const heavy = rawW[k].filter(([, w]) => w === HEAVY_W).length;
    return `${k} ${SINGLE_USES[k]}题(${heavy}题×${HEAVY_W}/` +
      `${SINGLE_USES[k] - heavy}题×${LIGHT_W})=${total[k].toFixed(2)}`;
  }).join("  "));
  const heavyAxes = LEGACY_AXES.filter((x) => !LIGHT_AXES.includes(x));
  const lightSum = LIGHT_AXES.reduce((s, k) => s + total[k], 0);
  const heavySum = heavyAxes.reduce((s, k) => s + total[k], 0);
  console.log(`    光影两轴总权重 ${lightSum.toFixed(2)} / 其余七轴 ${heavySum.toFixed(2)}`
    + `（逐轴比 ${(lightSum / 2 / (heavySum / 7)).toFixed(2)}×）`);
  // ⚠️ 实测：题库现在的光影两轴并不完全对称 —— bright 只在 4 道题里出现（≠ 6），
  //    contrasty 有 6 道、全用轻档 0.6。这不影响打分口径（都是线性权重），
  //    但会让「位置残留 0」这条旧性质变形（9 个审美轴的四列之和仍精确为 0，
  //    因为 4 和 6 都是偶数）。这里只把偏差记下来，不在测试里改题库内容。
  const offTier = LIGHT_AXES.flatMap((k) => rawW[k].filter(([, w]) => w !== LIGHT_W)
    .map(([qid, w]) => `${qid} 的 ${k}=${w}`));
  const modeUses = SINGLE_USES[LEGACY_AXES.find((k) => k !== LIGHT_AXES[0])];
  const offCount = LEGACY_AXES.filter((k) => SINGLE_USES[k] !== modeUses)
    .map((k) => `${k} ${SINGLE_USES[k]}题（其余是 ${modeUses} 题）`);
  if (offTier.length) console.log("    ⚠ 光影轴里用了重档的题：" + offTier.join("、"));
  if (offCount.length) console.log("    ⚠ 题数与众数不同的轴：" + offCount.join("、"));
});

check("图省事：art_axes 的 vec 已中心化（不是全正的原始像素值）", () => {
  AXES.forEach((k) => {
    const vals = DATA.a.map((a) => a.vec[k]);
    const mn = Math.min(...vals), mx = Math.max(...vals);
    assert(mn < -0.02 && mx > 0.02, `${k} 的取值区间 [${mn.toFixed(3)}, ${mx.toFixed(3)}] 看着没中心化`);
  });
});

check("7 个形态轴 + 9 个画风轴在参与池里都是零均值、SD≈0.2887（与 9 个审美轴同标度）", () => {
  FORM_AXES.concat(STYLE_AXES).concat(LEGACY_AXES).forEach((k) => {
    const vals = DATA.a.map((a) => a.vec[k]);
    const mean = vals.reduce((x, y) => x + y, 0) / vals.length;
    const sd = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length);
    assert(Math.abs(mean) < 0.01, `${k} 的均值 ${mean.toFixed(4)} 不是 0`);
    assert(Math.abs(sd - 0.2887) < 0.01, `${k} 的 SD ${sd.toFixed(4)} 不是 0.2887`);
  });
});

/* ================================================================== *
 * 场景 1：走完全部题能出结果
 * ================================================================== */
section(`[场景 1] 走完 ${N_Q} 题出结果`);

let run = null;
check("引擎路径：一路选 A 能走到结果页", () => {
  run = walk(PICK.first);
  assert(run.finished, `走了 ${run.steps} 步仍未出结果`);
});
check(`确实答满了 ${N_Q} 题且不重复`, () => {
  assert(run.visited.length === N_Q, `只答了 ${run.visited.length} 题`);
  assert(new Set(run.visited).size === N_Q, "有题目被重复作答");
});
check("结果页渲染出三张卡图（含标题、画师、系列）", () => {
  const out = rendered();
  assert(out.includes(`从 ${N_ARTS} 张插画里`), "缺结果页标题");
  const imgs = [...out.matchAll(/data-img-key="([^"]+)"/g)].map((m) => m[1]);
  assert(imgs.length === 3, `结果页有 ${imgs.length} 张图，应为 3`);
  assert((out.match(/<span class="lb">画师<\/span>/g) || []).length === 3, "画师没有三份");
  assert((out.match(/<span class="lb">出自<\/span>/g) || []).length === 3, "系列没有三份");
});
check("DOM 事件委托：点选项也能推进（UI 真的接着线）", () => {
  app.restart();
  assert(rendered().includes("开始"), "开场页没有开始按钮");
  dispatch({ attrs: { "data-act": "start" } });
  assert(app.getState().screen === "quiz", "点开始没有进入答题");
  const before = app.getState().index;
  const optNode = new Node("button");
  dispatch({ attrs: { "data-act": "choose", "data-i": "0" }, parent: optNode });
  assert(app.getState().index === before + 1, "点选项没有自动进下一题");
});
check("回上一题能改答案，且改完确实生效", () => {
  app.start();
  app.choose(0);
  const second = app.getState().index;
  assert(second === 1, "选完第一题没有前进");
  dispatch({ attrs: { "data-act": "back" } });
  assert(app.getState().index === 0, "回退没有回到上一题");
  app.choose(3);
  assert(app.getState().answers[app.Q[0].id] === 3, "改答案没有生效");
  assert(app.getState().index === 1, "改完答案没有继续往下走");
});

/* ================================================================== *
 * 场景 2：三张推荐的插画文件真实存在
 * ================================================================== */
section("[场景 2] 推荐的插画文件真实存在");

const RESULT = picksFor(PICK.first);

check("三张推荐的 local_art_crop 在磁盘上都能找到", () => {
  RESULT.picks.forEach((p, i) => {
    const fp = resolveImg(p.art.img);
    assert(fp, `第 ${i + 1} 张的插画找不到：${p.art.img}`);
    const size = fs.statSync(fp).size;
    assert(size > 1024, `第 ${i + 1} 张的文件只有 ${size} 字节，可能是空文件`);
  });
});

check("结果页里的 <img src> 与磁盘路径对得上", () => {
  walk(PICK.first);
  const srcs = [...rendered().matchAll(/<img[^>]*src="([^"]+)"/g)].map((m) => m[1]);
  assert(srcs.length === 3, `渲染出 ${srcs.length} 个 img，应为 3`);
  srcs.forEach((src) => {
    assert(!/^(https?:)?\/\//.test(src), `src 指向了外网：${src}`);
    // src 是相对 HTML 的相对路径：<HTML 所在目录>/<DATA.base>/<img>
    const fp = path.resolve(path.dirname(HTML_PATH), src);
    assert(fs.existsSync(fp), `src 在磁盘上不存在：${src} → ${fp}`);
  });
});

check("图片加载失败有兜底：onerror 会换成占位块", () => {  walk(PICK.first);
  const out = rendered();
  assert((out.match(/onerror="window\.__artQuizImgError/g) || []).length === 3, "img 上没有挂 onerror");
  const keys = [...out.matchAll(/data-img-key="([^"]+)"/g)].map((m) => m[1]);
  const handler = app.imgHandlers[keys[0]];
  assert(typeof handler === "function", `没有为 ${keys[0]} 注册兜底回调`);
  const imgEl = new Node("img");
  imgEl.setAttribute("data-img-key", keys[0]);
  const shot = new Node("div");       // 模拟 .shot 容器
  shot.appendChild(imgEl);
  assert(typeof imgErrorHandler === "function", "window.__artQuizImgError 没有暴露");
  imgErrorHandler(imgEl);
  assert(shot.innerHTML.includes("插画加载失败"), "触发 onerror 后没有出现占位提示");
});

check("单文件版（build_standalone.py 的产物）与 art_quiz.html 的应用脚本一致", () => {
  const standalone = path.join(ROOT, "art_quiz_standalone.html");
  if (!fs.existsSync(standalone)) {
    throw new Error("art_quiz_standalone.html 不存在，先跑 python scripts/build_standalone.py");
  }
  const st = fs.statSync(standalone);
  assert(st.size > 1024 * 1024, `单文件版只有 ${st.size} 字节，不像是内嵌了图片`);
  const sHtml = fs.readFileSync(standalone, "utf8");
  // 应用脚本（最后一段 <script>）必须与 art_quiz.html 逐字相同 —— 否则手机版跑的是旧逻辑
  // （比较前把 CRLF 归一成 LF：Windows 上换行风格不该算「脚本不一致」）
  const appScript = (h) => {
    const blocks = [...h.matchAll(/<script>([\s\S]*?)<\/script>/g)];
    return blocks[blocks.length - 1][1].replace(/\r\n/g, "\n");
  };
  assert(appScript(sHtml) === appScript(html), "单文件版的应用脚本与 art_quiz.html 不一致，需要重新生成");
  // 图片必须已经内嵌成 base64，且不再有相对路径
  const left = [...sHtml.matchAll(/"img":"(?!data:)[^"]+"/g)].length;
  assert(left === 0, `单文件版里还有 ${left} 处相对路径引用（发给别人会图全裂）`);
  const b64 = [...sHtml.matchAll(/"img":"data:image\/jpeg;base64,/g)].length;
  assert(b64 === N_ARTS, `单文件版内嵌了 ${b64} 张图，应为 ${N_ARTS}`);
  assert(!/(?:src|href)="https?:\/\//.test(sHtml), "单文件版里出现了外链，不满足「不联网」");
});

/* ================================================================== *
 * 场景 3：三位主将不重复
 * ================================================================== */
section("[场景 3] 三位主将不重复");

check("多种作答策略下，推荐的三位主将都不重复", () => {
  Object.entries(PICK).forEach(([name, picker]) => {
    const { picks } = picksFor(picker);
    assert(picks.length === 3, `策略「${name}」只给出 ${picks.length} 张`);
    const names = picks.map((p) => p.art.cmdr_en);
    assert(new Set(names).size === 3, `策略「${name}」的主将重复了：${names.join(" / ")}`);
  });
});

check("去重逻辑：同一主将的多个版本只会留分最高的那张", () => {
  const { picks } = picksFor(PICK.first);
  picks.forEach((p) => {
    const sameCmdr = DATA.a.filter((a) => a.cmdr_en === p.art.cmdr_en);
    const { pref } = RESULT;
    const best = Math.max(...sameCmdr.map((a) => app.scoreArt(pref, a.vec)));
    assert(Math.abs(best - p.score) < 1e-9,
      `${p.art.cmdr_en} 留的不是最高分版本（留了 ${p.score.toFixed(4)}，最高 ${best.toFixed(4)}）`);
  });
});

check("只按分值降序排（分数单调不增）", () => {
  const { picks } = picksFor(PICK.cycle);
  for (let i = 1; i < picks.length; i++) {
    assert(picks[i - 1].score >= picks[i].score, "推荐顺序不是降序");
  }
});

/* ================================================================== *
 * 场景 4：两极人设结果必须不同
 * ================================================================== */
section("[场景 4] 两极人设结果不同");

check("「全选第 1 项」与「全选第 2 项」的推荐结果不同", () => {
  const a = picksFor(PICK.first), b = picksFor(PICK.second);
  const diff = AXES.filter((k) => Math.abs(a.pref[k] - b.pref[k]) > 1e-9);
  assert(diff.length > 0, "两组答案算出了完全相同的偏好向量，打分器很可能没接上");
  const an = a.picks.map((p) => p.art.cmdr_en).join("|");
  const bn = b.picks.map((p) => p.art.cmdr_en).join("|");
  assert(an !== bn, `两极人设的 Top3 一模一样：${an}`);
});

check("语义相反的两组答案，Top3 完全不同", () => {
  const pairs = [["first", "second"], ["first", "third"], ["last", "second"]];
  pairs.forEach(([x, y]) => {
    const a = picksFor(PICK[x]), b = picksFor(PICK[y]);
    const diff = AXES.filter((k) => Math.abs(a.pref[k] - b.pref[k]) > 1e-9);
    assert(diff.length > 0, `「${x}」与「${y}」算出了完全相同的偏好向量`);
    const nx = a.picks.map((p) => p.art.cmdr_en).join("|");
    const ny = b.picks.map((p) => p.art.cmdr_en).join("|");
    assert(nx !== ny, `「${x}」与「${y}」的 Top3 相同：${nx}`);
  });
});

check("偏好向量互为反向时，整个池子的排名精确倒序", () => {
  // 打分器不能夹带任何偏置项：把任意一个偏好向量取反，每张图的得分必须精确取反。
  // （这里手工取反，不再依赖「全选第 1 项 / 全选第 2 项」在数据上恰好互为反向。）
  const a = picksFor(PICK.first).pref;
  const b = {};
  AXES.forEach((k) => { b[k] = (a[k] || 0) === 0 ? 0 : -(a[k] || 0); });
  AXES.forEach((k) => assert(Math.abs(a[k] + b[k]) < 1e-12, `轴 ${k} 不是互为反向`));
  const scores = (pref) => DATA.a.map((art) => ({ id: art.art_id, s: app.scoreArt(pref, art.vec) }));
  const fa = scores(a), fb = scores(b);
  fb.forEach((r, i) => assert(Math.abs(r.s + fa[i].s) < 1e-9,
    `第 ${i} 张的得分不是相反数：${fa[i].s} vs ${r.s}`));
  // 同分并列时两次排序的 tie-break 方向不同，所以按 art_id 归一后再比
  const order = (rows) => rows.slice().sort((x, y) => {
    if (y.s !== x.s) return y.s - x.s;
    return String(x.id).localeCompare(String(y.id));
  }).map((r) => r.id).sort();
  const idsA = order(fa), idsB = order(fb);
  assert(idsA.length === idsB.length, "两次排名的条目数不一致");
  const mismatched = idsA.findIndex((id, i) => id !== idsB[i]);
  assert(mismatched < 0,
    `第 ${mismatched + 1} 个不同：${idsA[mismatched]} vs ${idsB[mismatched]}`);
});

check("位置偏置：审美轴四列之和精确为 0；形态轴的残留 = 各题落在该位置的形态权重", () => {
  // 这一版题库：26 道单选审美题、每题恰好 2 轴、9 个轴各出现整 6 次（偶数）。
  // 6 是偶数 → 每个轴的 4 个位置可以排成 #正 = #负，所以「一路只选同一位置」在
  // 9 个审美轴上的**四个位置残留之和**必须精确为 0。
  // ⚠️ 注意：单看某一个位置不一定为 0！残留在位置之间会整体平移
  //    （实测 warm 四个位置分别是 +2.4/0/+1.2/−3.6，和为 0）——
  //    这是「正负在位置之间轮转」的直接后果，不是排错了。
  // ⚠️ 结构变化（2026-10-13，形态题 1 道 → 3 道）：「形态轴在位置上的拉丁方平衡」不存在 ——
  //    每题只有 1 个选项带某一类，所以「一路只勾第 k 项」时形态轴的残留 = 把该位置上的
  //    那几类各自加上自己的单题权重，结构上抵消不掉。三题按 0/1/3 左旋排开之后，
  //    四个前列位置各由 3 个**不同**形态占据，七个形态都能被「只勾前四项」的人扫到。
  // 「一路只选位置 k」在形态题上也要跟着走 —— picksFor 默认把多选固定成第 1 项，
  // 那样四列会拿到同一个值，看不出位置差异。这里显式给 multiPicker。
  const v = [0, 1, 2, 3].map((k) => picksFor((q) => k, (q) => [k]).pref);
  // 期望残留：直接按「一路选位置 k 时，每道题该轴贡献多少」算出来，再和引擎结果对
  const expect = [0, 1, 2, 3].map((pos) => {
    const acc = {};
    DATA.q.filter((q) => !q.multi).forEach((q) => {
      const o = q.opts[pos];
      if (!o) return;
      Object.keys(o.s).forEach((k) => { acc[k] = (acc[k] || 0) + o.s[k]; });
    });
    return acc;
  });
  LEGACY_AXES.forEach((k) => {
    const s = v.reduce((a, p) => a + p[k], 0);
    assert(Math.abs(s) < 1e-9, `${k} 在 4 个位置上的残留和 ${s} 不是 0`);
    v.forEach((p, i) => assert(Math.abs(p[k] - (expect[i][k] || 0)) < 1e-9,
      `${k} 在第 ${i + 1} 个位置的残留 ${p[k]} 与逐题累加的值 ${expect[i][k] || 0} 不符`));
  });
  // 形态轴：走「单选策略」时每道多选题默认只勾第 1 项，位置 k 的残留 = 各题第 k 项
  // 所挂形态的权重之和（三题位置顺序不同 → 一个位置上最多 3 类各出现一次）
  const formAt = [0, 1, 2, 3].map((pos) => {
    const acc = {};
    MQS.forEach((q) => {
      const o = q.opts[pos];
      if (!o) return;
      const k = Object.keys(o.s).find((x) => x.startsWith("form_"));
      if (!k) return;
      acc[k] = (acc[k] || 0) + o.s[k];
    });
    return acc;
  });
  FORMS.forEach((f) => {
    const k = "form_" + f;
    v.forEach((p, i) => assert(Math.abs(p[k] - (formAt[i][k] || 0)) < 1e-9,
      `${k} 在第 ${i + 1} 个位置残留 ${p[k]}，应为 ${formAt[i][k] || 0}`));
  });
  // 「四列之和」= 该形态在「前 4 位」里出现的次数 × 它的单题权重。
  // 与审美轴不同，形态轴的这一列**结构上不为 0**（一道多选里一个类只占一个位置）；
  // 但重排之后七个形态的前四位覆盖次数都 ≥ 1 → 七类都拿得到非零残留，
  // 不再出现「可爱小兽 / 机械构装 四列全 0」那种死角。
  console.log("    位置残留（每列 = 一路只选该位置；末列 = 四列之和）：");
  LEGACY_AXES.forEach((k) => {
    const t = v.reduce((a, p) => a + p[k], 0);
    console.log(`      ${k.padEnd(11)}` +
      v.map((p) => (p[k] >= 0 ? "+" : "") + p[k].toFixed(1)).join("  ") +
      `   Σ=${t.toFixed(1)}`);
  });
  FORMS.forEach((f) => {
    const k = "form_" + f;
    const t = v.reduce((a, p) => a + p[k], 0);
    assert(t > 1e-9, `${k} 四列之和为 0 —— 这个形态在前 4 位里一次都没出现`);
    console.log(`      ${f.padEnd(6)}` +
      v.map((p) => (p[k] >= 0 ? "+" : "") + p[k].toFixed(2)).join("  ") +
      `   Σ=${t.toFixed(2)}`);
  });
});

check("Top3 严格优于池子里其它任何一张（同主将去重的那版必须分数不更低）", () => {
  // ⚠️ 2026-10-13 修正：原来只断言「分数高于第三名 ⇒ 必须在 picks 里」。
  //   结果页会按主将去重（同一主将只留分最高的那一版），所以**同一个主将的另一版**
  //   完全可能分数高于第三名却被合法丢掉。正确口径分两种情况：
  //     · 主将没进 picks → 它必须在 picks 里（否则就是漏选）；
  //     · 主将已进 picks → 留在 picks 里的那一版分数必须 ≥ 它（否则去重去反了）。
  const { pref, picks } = picksFor(PICK.cycle);
  const floor = picks[2].score;
  const byCmdr = {};
  picks.forEach((p) => { byCmdr[p.art.cmdr_en] = p; });
  DATA.a.forEach((a) => {
    const s = app.scoreArt(pref, a.vec);
    if (s <= floor + 1e-9) return;
    if (picks.some((p) => p.art.art_id === a.art_id)) return;
    const kept = byCmdr[a.cmdr_en];
    assert(kept, `${a.art_id} 得分 ${s.toFixed(4)} 高于第三名 ${floor.toFixed(4)} 却没被选中`);
    assert(kept.score >= s - 1e-9,
      `同一主将 ${a.cmdr_en} 留的版本 ${kept.score.toFixed(4)} 低于被丢掉的 ${s.toFixed(4)}`);
  });
});

/* ================================================================== *
 * 场景 5：审美画像不出现负数
 * ================================================================== */
section("[场景 5] 审美画像不出现负数");

check("画像只列 5 个轴，且条形宽度都在 0~100% 之间", () => {
  walk(PICK.first);
  const out = rendered();
  const start = out.indexOf("你的审美画像");
  assert(start >= 0, "结果页没有审美画像");
  const sect = out.slice(start);
  const bars = [...sect.matchAll(/<i class="[^"]*" style="width:([\d.]+)%"/g)];
  assert(bars.length === 5, `画像里有 ${bars.length} 条，应为 5 条`);
  bars.forEach((m) => {
    const w = parseFloat(m[1]);
    assert(Number.isFinite(w), "条形宽度不是数字");
    assert(w >= 0, `条形宽度为负：${w}`);
    assert(w <= 100, `条形宽度超过 100%：${w}`);
  });
  assert(Math.max(...bars.map((m) => parseFloat(m[1]))) === 100, "最强的那个轴应当是最长的条");
});

check("多种作答策略下，画像里都不出现负数", () => {
  Object.entries(PICK).forEach(([name, picker]) => {
    walk(picker);
    const out = rendered();
    const sect = out.slice(out.indexOf("你的审美画像"));
    assert(sect.length > 0, "找不到画像区块");
    const badPct = sect.match(/-\s*\d+(\.\d+)?%/g);
    assert(!badPct, `策略「${name}」出现负数百分比：${badPct && badPct.join("、")}`);
    const widths = [...sect.matchAll(/width:\s*(-?[\d.]+)%/g)].map((m) => parseFloat(m[1]));
    assert(widths.length === 5, `策略「${name}」的条数不对：${widths.length}`);
    assert(!widths.some((w) => w < 0), `策略「${name}」条形宽度为负：${widths.join("、")}`);
    assert(!widths.some((w) => w > 100), `策略「${name}」条形宽度超过 100%：${widths.join("、")}`);
    const strengths = [...sect.matchAll(/强度 (-?[\d.]+)/g)].map((m) => parseFloat(m[1]));
    assert(strengths.length === 5, `策略「${name}」缺强度数值`);
    assert(!strengths.some((v) => v < 0), `策略「${name}」出现负强度：${strengths.join("、")}`);
  });
});

check("画像带方向词：正值显示正极，负值显示负极", () => {
  DATA.a.forEach(() => {});
  // 手工造两个极端 pref，直接验 profile()
  const posPref = Object.fromEntries(AXES.map((k) => [k, 0]));
  posPref.warm = 5.6; posPref.detailed = -3.2;
  const rows = app.profile(posPref, 5);
  assert(rows[0].axis === "warm" && rows[0].value > 0, "最大轴应当是 warm（正）");
  assert(rows[0].pole === app.AXIS_INFO.warm.pos, `warm 正值的方向词应是「${app.AXIS_INFO.warm.pos}」`);
  const det = rows.find((r) => r.axis === "detailed");
  assert(det && det.pole === app.AXIS_INFO.detailed.neg,
    `detailed 负值的方向词应是「${app.AXIS_INFO.detailed.neg}」，实际「${det && det.pole}」`);
  assert(rows.every((r) => r.info && r.info.zh && r.info.pos && r.info.neg), "轴缺中文标签或两极名");
  assert(rows.every((r) => r.pct >= 0 && r.pct <= 100), "pct 越界");
});

check("开场页的题数/张数是算出来的，不是写死的", () => {
  app.restart();
  const out = rendered();
  assert(out.includes(`${N_Q} 道小题`), `开场页没写对题数（应为 ${N_Q}）`);
  assert(out.includes(`前 ${N_SINGLE} 道每题 4 个选项`),
    `开场页没写对单选题数（应为 ${N_SINGLE}）`);
  assert(out.includes(`最后是 ${N_MULTI} 道`),
    `开场页没写对多选题数（应为 ${N_MULTI}）`);
  assert(out.includes(`${N_ARTS} 张万智牌插画`), `开场页没写对插画数（应为 ${N_ARTS}）`);
  // 「一道多选题」这种旧说法（写死单数）不许再出现
  assert(!out.includes("最后是一道"), "开场页还在用「最后是一道多选题」的旧说法");
  // 老池子的张数（268/272/273）一个都不该再出现在页面上
  ["268 张", "272 张", "273 张"].forEach((stale) =>
    assert(!out.includes(stale), `页面里还留着写死的 ${stale}`));
});

check("审美画像不出现负数（勾了形态之后也一样）", () => {
  FORMS.forEach((form) => {
    walk(PICK.first, false, 400, [form]);
    const out = rendered();
    const sect = out.slice(out.indexOf("你的审美画像"));
    assert(sect.length > 0, `「想看${form}」找不到画像区块`);
    const widths = [...sect.matchAll(/width:\s*(-?[\d.]+)%/g)].map((m) => parseFloat(m[1]));
    assert(widths.length === 5, `「想看${form}」的条数不对：${widths.length}`);
    assert(!widths.some((w) => w < 0 || w > 100), `「想看${form}」条形宽度越界：${widths.join("、")}`);
    const strengths = [...sect.matchAll(/强度 (-?[\d.]+)/g)].map((m) => parseFloat(m[1]));
    assert(strengths.length === 5, `「想看${form}」缺强度数值`);
    assert(!strengths.some((v) => v < 0), `「想看${form}」出现负强度：${strengths.join("、")}`);
    assert(sect.includes("本次满分"), `「想看${form}」的满分说明丢了`);
  });
  // 形态轴确实能出现在画像里（说明 AXIS_INFO 有中文标签）
  const pref = {};
  AXES.forEach((k) => { pref[k] = 0; });
  pref["form_机械构装"] = 0.7; pref.warm = 0.5;
  const rows = app.profile(pref, 5);
  assert(rows[0].axis === "form_机械构装", `最强的应为形态轴，实际 ${rows[0].axis}`);
  assert(rows[0].pole === app.AXIS_INFO["form_机械构装"].pos,
    `形态轴的方向词不对：${rows[0].pole}`);
  assert(rows[0].info.zh === "画面形态", `形态轴的中文标签不对：${rows[0].info.zh}`);
});

check("重新测一次：清空全部状态并回到开场页", () => {
  walk(PICK.first);
  assert(Object.keys(app.getState().answers).length === N_Q,
    `重测前应当是 ${N_Q} 题答满`);
  dispatch({ attrs: { "data-act": "restart" } });
  const st = app.getState();
  assert(st.screen === "intro", `重测后应在开场页，实际 ${st.screen}`);
  assert(Object.keys(st.answers).length === 0, "重测没有清空答案");
  assert(!onResult(), "重测后结果页还留着");
  assert(rendered().includes("开始"), "开场页没渲染出来");
});

/* ================================================================== *
 * 场景 6：结果页没有 undefined / NaN
 * ================================================================== */
section("[场景 6] 结果页不留 undefined / NaN");

check("六种作答策略下，结果页都不出现 undefined / NaN", () => {
  Object.entries(PICK).forEach(([name, picker]) => {
    walk(picker);
    const out = rendered();
    ["undefined", "NaN", "null"].forEach((bad) => {
      const i = out.indexOf(bad);
      assert(i < 0, `策略「${name}」出现 ${bad}：…${out.slice(Math.max(0, i - 60), i + 40)}…`);
    });
  });
});

check(`${N_Q} 题按「勾满 7 类存在」走完全程也不报错`, () => {
  FORMS.forEach((form) => {
    walk(PICK.first, false, 400, [form]);
    assert(onResult(), `「想看${form}」没有走到结果页`);
    const out = rendered();
    ["undefined", "NaN", "null"].forEach((bad) => {
      const i = out.indexOf(bad);
      assert(i < 0, `「想看${form}」出现 ${bad}：…${out.slice(Math.max(0, i - 60), i + 40)}…`);
    });
  });
});

/* ================================================================== *
 * 场景 7：多选题真的接进了推荐（勾 1 个 / 勾 3 个 / 全勾 / 一个都别想跳）
 * ================================================================== */
section("[场景 7] 多选题接进推荐");

/** 形态部分得分：只算 6 个 form_* 轴（可以把审美那部分约掉） */
function formScore(pref, art) {
  return FORM_AXES.reduce((s, k) => s + (pref[k] || 0) * art.vec[k], 0);
}
/** 每一类图的「形态部分平均分」 */
function classMeans(pref) {
  const out = {};
  FORMS.forEach((f) => {
    const rows = DATA.a.filter((a) => a.form === f);
    out[f] = rows.reduce((s, a) => s + formScore(pref, a), 0) / rows.length;
  });
  return out;
}
function meanOf(xs) { return xs.reduce((a, b) => a + b, 0) / xs.length; }
function fmtPicks(picks) {
  return picks.map((p) => `${p.art.cmdr_zh}(${p.art.form})`).join(" / ");
}

check(`题库里那 6 个形态的权重都已写入全部 ${N_MULTI} 道形态题（缺一个都算没接上）`, () => {
  assert(MQS.length > 0, "题库里没有多选题");
  MQS.forEach((q) => {
    assert(q.opts.length === FORMS.length, `${q.id} 有 ${q.opts.length} 个选项，应为 ${FORMS.length}`);
    FORMS.forEach((f) => {
      const v = FORM_W_BY_Q[q.id][f];
      assert(typeof v === "number", `${q.id} 的 ${f} 没有从题库里读出权重`);
      assert(v > 0, `${q.id} 的 ${f} 权重 ${v} 不是正的`);
    });
  });
  console.log(`    ${N_MULTI} 道形态题的权重（三者应当相同）：`);
  MQS.forEach((q) => console.log(`      ${q.id}  ` +
    FORMS.map((f) => `${f} ${FORM_W_BY_Q[q.id][f]}`).join("  ")));
  console.log(`    单题 α（= w·k）= ${ALPHA_MAX.toFixed(4)}；`
    + `${N_MULTI} 题累加总推力 T = ${ALPHA_TOTAL.toFixed(4)}`);
});

/**
 * 三题一起勾时的 Top3 形态纯度。
 *   personas：一串「审美人设」= 26 道单选审美题各自的作答下标数组
 *   返回 {rows:[{name, pur, forms}], min, mean}
 * 判据用的是**连贯人设**（一路只选第 k 项 = 口味一致的真实用户）；
 * 随机作答的人设没有连贯口味，实测最小纯度会掉到 0，所以只断言平均。
 */
function puritySweep(formSet, personaList) {
  const rows = personaList.map(({ name, picks }) => {
    const answers = {};
    app.Q.forEach((q, i) => {
      answers[q.id] = q.multi
        ? (formMultiPicker(formSet)(q))
        : Math.min(picks[i], q.opts.length - 1);
    });
    const pref = app.prefVector(answers);
    const top = app.recommend(pref, 3).map((p) => p.art.form);
    const want = new Set([...formSet].map((f) => (f.startsWith("form_") ? f.slice(5) : f)));
    return { name, pur: top.filter((f) => want.has(f)).length / 3, forms: top };
  });
  const ps = rows.map((r) => r.pur);
  return { rows, min: Math.min(...ps), mean: sum(ps) / ps.length, max: Math.max(...ps) };
}
/** 4 个连贯人设：一路只选第 k 项 */
const FIXED_PERSONAS = [0, 1, 2, 3].map((k) => ({
  name: `固定第${k + 1}项`,
  picks: Array(N_SINGLE).fill(k),
}));
/** mulberry32：可复现的伪随机，用来造「随机作答 = 没有连贯口味」的噪声人设 */
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const NOISE_PERSONAS = (() => {
  const rnd = mulberry32(20261013);
  return Array.from({ length: 120 }, (_, n) => ({
    name: `随机${n + 1}`,
    picks: DATA.q.filter((q) => !q.multi).map((q) => Math.floor(rnd() * q.opts.length)),
  }));
})();

/**
 * 形态纯度判据（2026-10-13 重写：6 类 → 7 类、并新增 9 道画风题之后）。
 *   池子把兽形拆成三类之后，最瘦的两类只剩 **6 张**（可爱小兽）与 **9 张**（写实动物）
 *   —— 它们连「Top3 全是自己」都做不到（池子里凑不出 3 位不重复的主将），
 *   拿「Top3 纯度 ≥ 2/3」去卡它们没有意义（实测：把 9 道画风题整组删掉，这两类
 *   的最小纯度照样是 0.00 / 0.33，见 scripts/_tB_purity_experiment.py 的实验 ④）。
 *   所以判据按**该类在池子里的占比**分档：
 *     占比 ≥ 10%      → 连贯人设最小纯度 ≥ 2/3，随机人设平均纯度 ≥ 0.8
 *     5% ≤ 占比 < 10% → ≥ 1/3，随机人设平均 ≥ 0.6
 *     占比 < 5%       → 不设阈值，只打印实测值（并在设计说明里登记）
 *   完整数值见 data/questions_design_note.md §5.5。
 */
const FORM_SHARE = {};
FORMS.forEach((f) => { FORM_SHARE[f] = DATA.a.filter((a) => a.form === f).length / N_ARTS; });
const fixedNeed = (f) => (FORM_SHARE[f] >= 0.10 ? 2 / 3 : (FORM_SHARE[f] >= 0.05 ? 1 / 3 : 0));
const noiseNeed = (f) => (FORM_SHARE[f] >= 0.10 ? NOISE_MEAN_MIN : (FORM_SHARE[f] >= 0.05 ? 0.6 : 0));

check(`三题一起勾「可爱小兽」：形态推力方向正确 + 噪声人设平均纯度（池子占 ${(FORM_SHARE["可爱小兽"] * 100).toFixed(1)}%，不卡 Top3 纯度）`, () => {
  const sw = puritySweep(["可爱小兽"], FIXED_PERSONAS);
  sw.rows.forEach((r) => console.log(
    `    ${r.name} → ${r.forms.join(" / ")}　纯度 ${r.pur.toFixed(2)}`));
  console.log(`    连贯人设：最小 ${sw.min.toFixed(2)} / 平均 ${sw.mean.toFixed(2)}`
    + `（该类的池子占比只有 ${(FORM_SHARE["可爱小兽"] * 100).toFixed(1)}%，判据不设阈值）`);
  const noise = puritySweep(["可爱小兽"], NOISE_PERSONAS);
  console.log(`    随机噪声人设：最小 ${noise.min.toFixed(2)} / 平均 ${noise.mean.toFixed(2)}`
    + `（${NOISE_PERSONAS.length} 组；最小值为 0 是「口味随机」的人设，不是打分器的问题）`);
  // 硬判据（由 solve_form_weights.py 保证）：只在某一类上加了权重时，该类图的
  // 形态平均分必然高于其它类，且抬升量 = T（与哪一类无关）。
  const { pref } = picksForForm(["可爱小兽"]);
  const means = classMeans(pref);
  const others = FORMS.filter((f) => f !== "可爱小兽");
  const lift = means["可爱小兽"] - Math.max(...others.map((f) => means[f]));
  assert(lift > 0, `可爱小兽的形态平均分没有高于其它类：${lift.toFixed(4)}`);
});

check("七类各自的纯度：按池子占比分档达标（最瘦的可爱小兽 / 写实动物只打印）", () => {
  console.log(`    ${"勾".padEnd(8)}${"占比".padStart(7)}${"最小".padStart(7)}${"应≥".padStart(7)}`
    + `${"平均".padStart(7)}${"噪声最小".padStart(10)}${"噪声平均".padStart(10)}${"应≥".padStart(6)}`);
  const mins = {};
  FORMS.forEach((f) => {
    const sw = puritySweep([f], FIXED_PERSONAS);
    const noise = puritySweep([f], NOISE_PERSONAS);
    mins[f] = sw.min;
    const needF = fixedNeed(f), needN = noiseNeed(f);
    console.log(`    ${f.padEnd(8)}${(FORM_SHARE[f] * 100).toFixed(1).padStart(6)}%`
      + `${sw.min.toFixed(2).padStart(7)}${(needF ? needF.toFixed(2) : "—").padStart(7)}`
      + `${sw.mean.toFixed(2).padStart(7)}${noise.min.toFixed(2).padStart(10)}`
      + `${noise.mean.toFixed(2).padStart(10)}${(needN ? needN.toFixed(2) : "—").padStart(6)}`);
    assert(sw.min >= needF - 1e-9,
      `连贯人设下「勾${f}」的最小纯度 ${sw.min.toFixed(2)} 没到 ${needF.toFixed(2)}`);
    assert(noise.mean >= needN - 1e-9,
      `随机人设下「勾${f}」的平均纯度 ${noise.mean.toFixed(2)} 低于 ${needN.toFixed(2)}`);
  });
  console.log(`    → 有阈值的那几类，最小纯度全部达标；`
    + `可爱小兽 / 写实动物 池子太小（${(FORM_SHARE["可爱小兽"] * 100).toFixed(1)}% / `
    + `${(FORM_SHARE["写实动物"] * 100).toFixed(1)}%），只登记实测值`);
});

check("勾「纯人类」：Top3 全是纯人类", () => {
  const { picks, pref } = picksForForm(["纯人类"]);
  const forms = picks.map((p) => p.art.form);
  const pur = forms.filter((f) => f === "纯人类").length / 3;
  console.log(`    勾纯人类 → ${fmtPicks(picks)}　纯度 ${pur.toFixed(2)}`);
  assert(forms.length === 3, `只给出 ${forms.length} 张`);
  const means = classMeans(pref);
  const others = FORMS.filter((f) => f !== "纯人类");
  const lift = means["纯人类"] - Math.max(...others.map((f) => means[f]));
  assert(lift > 0, `纯人类的形态平均分没有高于其它类：${lift.toFixed(4)}`);
  if (ALPHA_TOTAL >= TOP3_PURE_ALPHA) {
    assert(pur === 1, `Top3 应全是纯人类，实际 ${fmtPicks(picks)}`);
  } else {
    assert(pur >= 1 / 3, `勾纯人类后 Top3 里一个纯人类都没有：${fmtPicks(picks)}`);
  }
});

check("勾 3 个（纯人类 + 机械构装 + 凶猛巨兽）：Top3 只从这 3 类里出", () => {
  const combo = ["纯人类", "机械构装", "凶猛巨兽"];
  const { picks, pref } = picksForForm(combo);
  console.log(`    勾 ${combo.join("+")} → ${fmtPicks(picks)}`);
  assert(picks.length === 3, `只给出 ${picks.length} 张`);
  picks.forEach((p) => assert(combo.includes(p.art.form),
    `Top3 里混进了没勾的形态：${fmtPicks(picks)}`));
  // 勾中的三类之间没有系统性偏心：三类平均分极差 ~ 0（只剩题库权重的舍入残差）
  const means = classMeans(pref);
  const sel = combo.map((f) => means[f]);
  const spread = Math.max(...sel) - Math.min(...sel);
  console.log("    勾中三类的形态平均分：" + combo.map((f) => `${f} ${means[f].toFixed(4)}`).join("  ")
    + `　极差 ${spread.toFixed(6)}`);
  assert(spread < ALPHA_TOL, `勾中三类之间的平均分极差 ${spread.toFixed(4)} 太大，有系统性偏心`);
  // 未勾的三类都要低于勾中的最低那类
  const floor = Math.min(...sel);
  FORMS.filter((f) => !combo.includes(f)).forEach((f) =>
    assert(means[f] < floor, `未勾的 ${f}（${means[f].toFixed(4)}）没有低于勾中类（最低 ${floor.toFixed(4)}）`));
});

check("勾 1 个 / 勾 3 个 / 全勾，三种情况的 Top3 各不相同", () => {
  const cases = { "勾1个": ["可爱小兽"], "勾3个": ["纯人类", "机械构装", "凶猛巨兽"], "全勾7个": FORMS.slice() };
  const out = {};
  Object.entries(cases).forEach(([name, set]) => {
    const { picks, pref } = picksForForm(set);
    assert(picks.length === 3, `「${name}」只给出 ${picks.length} 张`);
    out[name] = picks;
    console.log(`    ${name.padEnd(6)} ${fmtPicks(picks)}`);
    // 每种情况都必须真的改动了推荐（形态偏好向量不同）
    assert(FORMS.some((f) => Math.abs(pref["form_" + f]) > 1e-9), `「${name}」的形态偏好全是 0`);
  });
  const key = (picks) => picks.map((p) => p.art.art_id).join("|");
  const k1 = key(out["勾1个"]), k3 = key(out["勾3个"]), k6 = key(out["全勾7个"]);
  assert(k1 !== k3, `勾 1 个与勾 3 个的 Top3 一样：${k1}`);
  assert(k3 !== k6, `勾 3 个与全勾的 Top3 一样：${k3}`);
  assert(k1 !== k6, `勾 1 个与全勾的 Top3 一样：${k1}`);
});

check("全勾（=「我都行」）把形态维度抹成常数：七类平均分极差 ≈ 0", () => {
  const { pref, picks } = picksForForm(FORMS.slice());
  const means = classMeans(pref);
  console.log("    全勾后的形态分：" + FORMS.map((f) => `${f} ${means[f].toFixed(4)}`).join("  "));
  const spread = Math.max(...Object.values(means)) - Math.min(...Object.values(means));
  console.log(`    七类极差 ${spread.toFixed(6)}`);
  assert(spread < ALPHA_TOL, `各类形态分的极差 ${spread.toFixed(4)} 太大，等于把「都行」读成了偏好`);
  // 「全勾」等价于形态维度完全不参与：逐张图只是同一个常数，排序应与「形态权重全相等」一致
  const flat = {};
  AXES.forEach((k) => { flat[k] = k.startsWith("form_") ? 0 : (pref[k] || 0); });
  const alt = app.recommend(flat, 3).map((p) => p.art.art_id).join("|");
  assert(alt === picks.map((p) => p.art.art_id).join("|"),
    `全勾的 Top3 应当等价于「形态不参与排序」：${alt} vs ${fmtPicks(picks)}`);
});

check(`勾中类 vs 未勾类的平均分差 = 同一个总推力 T = ${N_MULTI}·α（七类之间没有系统性偏心）`, () => {
  const lifts = FORMS.map((f) => {
    const { pref } = picksForForm([f]);
    const means = classMeans(pref);
    const others = FORMS.filter((x) => x !== f);
    return { form: f, lift: means[f] - meanOf(others.map((x) => means[x])) };
  });
  console.log("    只勾一类时的抬升量：" +
    lifts.map((r) => `${r.form} ${r.lift.toFixed(4)}`).join("  "));
  const vs = lifts.map((r) => r.lift);
  const spread = Math.max(...vs) - Math.min(...vs);
  assert(spread < ALPHA_TOL, `七类抬升量的极差 ${spread.toFixed(4)} 太大，说明有类别被优待`);
  assert(Math.min(...vs) > 0.5, `抬升量最小 ${Math.min(...vs).toFixed(3)} 太小，勾了等于没勾`);
  // 抬升量必须等于**总**推力 T = N_MULTI · (w_f · k_f)，且 ≤ 硬约束撑得住的上限
  console.log(`    单题 α 的实测上限 = ${W_MAX}·min k = ${ALPHA_MAX.toFixed(4)}；`
    + `${N_MULTI} 题累加 T = ${ALPHA_TOTAL.toFixed(4)}；抬升量极差 ${spread.toFixed(6)}`
    + `（容差 ${ALPHA_TOL.toFixed(4)}）`);
  vs.forEach((x, i) => assert(Math.abs(x - ALPHA_TOTAL) < ALPHA_TOL,
    `${FORMS[i]} 的抬升量 ${x.toFixed(4)} 偏离 T=${ALPHA_TOTAL.toFixed(4)} 太多`));
});

check("多选题的 UI 接线：可多选、可取消、0 个勾选时「下一题」不可点", () => {
  app.restart();
  dispatch({ attrs: { "data-act": "start" } });
  assert(app.getState().screen === "quiz", "点开始没有进入答题");
  // 单选题的标题与选项结构（多选版不能把单选的渲染一起改坏）
  {
    const out = rendered();
    assert(/class="opt(?! multi)/.test(out), "单选题的选项样式变了（不该带 multi）");
    assert(!out.includes('class="box"'), "单选题里混进了多选的方框");
    assert(!out.includes('data-act="toggle"'), "单选题不该出现 toggle 事件");
    assert((out.match(/data-act="choose"/g) || []).length === SINGLE_OPTS,
      "单选题应该渲染 4 个 choose 按钮");
    assert(/第 1 题 \/ 共 \d+ 题/.test(out), "单选的题号计数文案不对：" + out.slice(0, 200));
  }
  // 一路点选项走到多选题
  let guard = 0;
  while (!app.isMulti(app.Q[app.getState().index]) && guard++ < N_Q + 2) {
    dispatch({ attrs: { "data-act": "choose", "data-i": "0" } });
  }
  const q = app.Q[app.getState().index];
  assert(app.isMulti(q), `走了 ${guard} 步也没到多选题（当前 ${app.Q[app.getState().index].id}）`);
  assert(app.canAdvance() === false, "多选题在 0 个勾选时不该允许推进");
  const out0 = rendered();
  assert(out0.includes('data-act="toggle"'), "多选题没有渲染成可勾选的按钮");
  assert((out0.match(/class="opt multi/g) || []).length === q.opts.length,
    `多选题的 .opt.multi 数量不对：${(out0.match(/class="opt multi/g) || []).length}`);
  assert((out0.match(/<span class="box" aria-hidden="true"><\/span>/g) || []).length === q.opts.length,
    "多选题的每个选项都该带一个勾选框");
  assert((out0.match(/<span class="txt">/g) || []).length === q.opts.length,
    "多选题的选项文本没有包在 .txt 里（flex 布局会错位）");
  assert(/已勾 <span class="pick-count">0<\/span> \/ \d+ 项/.test(out0),
    "多选题没有显示「已勾 N / 共 M 项」");
  assert(/data-act="next"[^>]*disabled/.test(out0), "0 个勾选时「下一题」没有 disabled");
  assert(!/data-act="back"/.test(out0) === (guard === 0), "第一题的上一题按钮显示不对");
  // 勾第 1 个
  dispatch({ attrs: { "data-act": "toggle", "data-multi": "1", "data-i": "0" } });
  assert(app.getState().answers[q.id].join(",") === "0", `勾选没有记下：${app.getState().answers[q.id]}`);
  assert(app.canAdvance(), "勾了 1 个之后仍然不让推进");
  assert(/class="opt multi on"/.test(rendered()), "选中的选项没有视觉反馈（缺 .on）");
  assert(!/data-act="next"[^>]*disabled/.test(rendered()), "勾了 1 个之后「下一题」还是灰的");
  // 再勾两个 → 累计 3 个
  dispatch({ attrs: { "data-act": "toggle", "data-multi": "1", "data-i": "2" } });
  dispatch({ attrs: { "data-act": "toggle", "data-multi": "1", "data-i": "4" } });
  assert(app.getState().answers[q.id].join(",") === "0,2,4",
    `多选没有累加：${app.getState().answers[q.id]}`);
  assert((rendered().match(/class="opt multi on"/g) || []).length === 3, "高亮的选项数不对");
  // 取消中间那个
  dispatch({ attrs: { "data-act": "toggle", "data-multi": "1", "data-i": "2" } });
  assert(app.getState().answers[q.id].join(",") === "0,4",
    `取消勾选没生效：${app.getState().answers[q.id]}`);
  // ⚠️ 形态题有 N_MULTI 道：点「下一题」只是走到下一道形态题，最后一道才出结果
  assert(!onResult(), `还有 ${N_MULTI - 1} 道形态题没答，不该已经出结果`);
  const pickedPerQ = [app.getState().answers[q.id].length];
  for (let n = 1; n < N_MULTI; n++) {
    dispatch({ attrs: { "data-act": "next" } });
    const cur = app.Q[app.getState().index];
    assert(app.isMulti(cur), `第 ${n + 1} 道形态题不是多选：${cur.id}`);
    assert(app.canAdvance() === false, `${cur.id} 在 0 个勾选时不该允许推进`);
    assert(/已勾 <span class="pick-count">0<\/span> \/ \d+ 项/.test(rendered()),
      `${cur.id} 的「已勾 N / 共 M 项」计数不对`);
    dispatch({ attrs: { "data-act": "toggle", "data-multi": "1", "data-i": String(n) } });
    dispatch({ attrs: { "data-act": "toggle", "data-multi": "1", "data-i": "5" } });
    pickedPerQ.push(2);
  }
  dispatch({ attrs: { "data-act": "next" } });
  assert(onResult(), `答完 ${N_MULTI} 道形态题后点「下一题」没有走到结果页`);
  const out = rendered();
  assert(out.includes("你选的伙伴"), "结果页没有列出勾选的形态");
  // 结果页要把**每一道**形态题的勾选都列出来：N_MULTI 道 × 6 个 chip
  assert((out.match(/<span class="chip/g) || []).length === N_MULTI * FORMS.length,
    `结果页的形态 chip 数量不对：${(out.match(/<span class="chip/g) || []).length}`
    + `，应为 ${N_MULTI * FORMS.length}`);
  assert((out.match(/class="chip"/g) || []).length === sum(pickedPerQ),
    `结果页高亮的 chip 数不对：${(out.match(/class="chip"/g) || []).length}，应为 ${sum(pickedPerQ)}`);
  assert((out.match(/class="fs-q"/g) || []).length === N_MULTI,
    `结果页应当分 ${N_MULTI} 块列出形态题，实际 ${(out.match(/class="fs-q"/g) || []).length} 块`);
  const totalPicked = sum(pickedPerQ);
  assert(out.includes(`一共勾了 <span class="kw">${totalPicked} / ${N_MULTI * FORMS.length}</span>`),
    `结果页没报出总勾选数 ${totalPicked} / ${N_MULTI * FORMS.length}`);
  console.log("    结果页 chip（逐题）：");
  out.split('<div class="fs-q">').slice(1).forEach((blk, i) => {
    const chips = [...blk.matchAll(/<span class="chip(?: dim)?">([^<]*)<\/span>/g)].map((m) => m[1]);
    console.log(`      ${i + 1}. ` + chips.join(" | "));
  });
});

check("多选题走 DOM 全流程（勾满 6 个）也不留 undefined / NaN", () => {
  const r = walk(PICK.first, true, 400, FORMS.slice());
  assert(r.finished, `勾满 7 类走了 ${r.steps} 步仍未出结果`);
  assert(r.visited.length === N_Q, `只答了 ${r.visited.length} 题`);
  const out = rendered();
  ["undefined", "NaN", "null"].forEach((bad) => {
    const i = out.indexOf(bad);
    assert(i < 0, `出现 ${bad}：…${out.slice(Math.max(0, i - 60), i + 40)}…`);
  });
  assert(out.includes("我都行"), "勾满 7 类时结果页没有说明这一维已中立");
});

check("多选题「靠回车/直接调引擎」也走同一条路：toggle + advance 与 DOM 结果一致", () => {
  const viaApi = picksForForm(["纯人类", "可爱小兽"]);
  const viaWalk = (() => {
    const r = walk(PICK.first, false, 400, ["纯人类", "可爱小兽"]);
    assert(r.finished, "没走到结果页");
    return app.recommend(app.prefVector(app.getState().answers), 3).map((p) => p.art.art_id).join("|");
  })();
  assert(viaWalk === viaApi.picks.map((p) => p.art.art_id).join("|"),
    "两条路径给出的 Top3 不一致");
});

check(`任何作答策略都不会推荐到被剔除的 8 张`, () => {  const strategies = Object.assign({}, PICK,
    { all0: () => 0, all1: () => 1, all2: () => 2, all3: () => 3 });
  const hits = new Set();
  Object.entries(strategies).forEach(([name, picker]) => {
    const { pref, picks } = picksFor(picker);
    app.recommend(pref, 10).forEach((p) => {
      assert(!EXCLUDED_IDS.includes(p.art.art_id),
        `策略「${name}」推荐到了被剔除的 ${p.art.art_id}`);
      hits.add(p.art.art_id);
    });
    assert(picks.length === 3, `策略「${name}」的推荐数不对`);
  });
  FORMS.forEach((form) => {
    picksForForm("form_" + form).picks.forEach((p) => {
      assert(!EXCLUDED_IDS.includes(p.art.art_id), `「想看${form}」推荐到了被剔除的图`);
    });
  });
  // 反过来也要成立：payload 里的图一张都不属于剔除名单
  DATA.a.forEach((a) => assert(!EXCLUDED_IDS.includes(a.art_id),
    `${a.art_id} 不该出现在 payload 里`));
  assert(hits.size > 10, `策略覆盖的图只有 ${hits.size} 张，这条测试没起到作用`);
});

/* ------------------------------------------------------------------ */
console.log("\n" + "=".repeat(70));
if (problems.length) {
  console.log(`\u2717 冒烟测试 ${problems.length} 项未通过（通过 ${passCount} 项）：`);
  problems.forEach((p) => console.log("   - " + p));
  process.exit(1);
}
console.log(`\u2713 冒烟测试全部通过（${passCount} 项）`);
