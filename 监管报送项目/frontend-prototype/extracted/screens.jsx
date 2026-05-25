// screens.jsx — all main screens + mock data
// Components attached to window so app.jsx can use them.

const { useState, useEffect, useMemo, useRef } = React;

// =====================================================================
//                           ICON HELPER
// =====================================================================
function Icon({ name, size = 16, ...rest }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && window.lucide) {
      ref.current.innerHTML = "";
      const el = document.createElement("i");
      el.setAttribute("data-lucide", name);
      el.style.width = size + "px";
      el.style.height = size + "px";
      ref.current.appendChild(el);
      window.lucide.createIcons({ attrs: { width: size, height: size, "stroke-width": 1.8 } });
    }
  }, [name, size]);
  return <span ref={ref} style={{ display: "inline-flex", lineHeight: 0, verticalAlign: "middle" }} {...rest} />;
}
window.Icon = Icon;

// =====================================================================
//                              MOCK DATA
// =====================================================================
const DOC = {
  id: "REG-2025-0103-002",
  title: "关于做好 2025 年银行业非现场监管报表填报工作的通知（市局转发件）",
  docNum: "金发〔2024〕39 号 · 盐金转〔2025〕1 号",
  issuer: "国家金融监督管理总局 · 盐城监管分局",
  category: "正式通知 · 年度填报工作",
  publishedAt: "2025-01-03",
  effectiveFrom: "2025-01-01",
  pages: 12,
  attachments: 5,
  system: "1104 非现场监管报表",
  version: "2025 年 251 版",
  scope: "一组 / 二组法人机构 · 资金同业相关报表",
  confidence: 88,
  // For portrait body
  summary:
    "本通知转发国家金融监督管理总局《关于做好 2025 年银行业非现场监管报表填报工作的通知》，明确 2025 年银行业非现场监管报表的制度落地、报表新增与修订、机构范围、报送频度与时限等要求。其中涉及本行的核心变化集中在资金同业相关报表，包含 G24 同业融入余额口径调整、G21 期限缺口划分细化以及 G25 LCR/NSFR 流动性资产范围更新；并要求各机构于 2025 年 4 月底前完成内部报送制度修订备案。",
  highlights: [
    {
      loc: "正文 第 3 条 · 第 4 页",
      text: "做好 2025 年银行业非现场监管报表填报工作，机构应于 2025 年 4 月底前完成内部监管数据报送制度的修订备案。",
      tagText: "时限要求",
    },
    {
      loc: "附件 4 · G24 填报说明 · 第 2 页",
      text: "G24「最大百家金融机构同业融入情况表」中，同业融入余额口径调整为按法人金融机构合并计算，并新增按产品分类的列项。",
      tagText: "口径调整",
    },
    {
      loc: "附件 4 · G25 填报说明 · 第 6 页",
      text: "G25 表中合格优质流动性资产的范围更新，纳入新型政策性金融工具，剔除部分受限资产；NSFR 部分稳定资金口径细化为三档。",
      tagText: "口径调整",
    },
    {
      loc: "附件 1-1 · 频度时限 · 第 12 行",
      text: "G24 报表上报时限由月报 13 天调整为 6 天；并表口径维持境内汇总。",
      tagText: "频度调整",
    },
  ],
  actions: [
    { icon: "file-plus-2", lbl: "材料类型", val: "正式通知", hint: "含 5 个配套附件" },
    { icon: "git-pull-request-arrow", lbl: "变更性质", val: "口径调整 · 频度调整", hint: "3 类变更同时存在" },
    { icon: "boxes",      lbl: "涉及报表", val: "G21 · G24 · G25", hint: "+ G27 / G31 候选" },
    { icon: "building-2", lbl: "适用范围", val: "一组 / 二组法人", hint: "本行属于一组" },
    { icon: "calendar-clock", lbl: "生效日期", val: "2025-01-01", hint: "Q1 报送批次起" },
    { icon: "clock-alert", lbl: "处理时限", val: "2025-04-30", hint: "内部制度备案截止" },
    { icon: "list-checks", lbl: "AI 候选指标", val: "12 项", hint: "命中 8 / 候选 4" },
    { icon: "alert-octagon", lbl: "风险等级", val: "高", hint: "影响 LCR / NSFR 上报" },
  ],
  reports: [
    {
      code: "G24",
      name: "最大百家金融机构同业融入情况表",
      desc: "同业融入余额、交易对手、产品分类、到期日。本次新增产品分类列、口径调整为法人合并。",
      hot: true,
      tag: "高影响",
      tagTone: "red",
      conf: 96,
    },
    {
      code: "G21",
      name: "流动性期限缺口统计表",
      desc: "期限分档、现金流入流出、同业头寸缺口。期限分档细化为 9 档，影响汇总公式。",
      hot: true,
      tag: "中影响",
      tagTone: "amber",
      conf: 91,
    },
    {
      code: "G25",
      name: "流动性覆盖率和净稳定融资比例情况表",
      desc: "HQLA 范围、现金净流出、可用稳定资金口径调整。NSFR 部分稳定资金分三档。",
      hot: true,
      tag: "高影响",
      tagTone: "red",
      conf: 89,
    },
    {
      code: "G27",
      name: "主要负债项目明细表",
      desc: "同业存放、主要负债结构。需与 G24 同业融入口径联动校验。",
      hot: false,
      tag: "候选",
      tagTone: "blue",
      conf: 72,
    },
    {
      code: "G31",
      name: "投资业务情况表 · 底层资产",
      desc: "债券投资、底层资产穿透。仅涉及与 G25 HQLA 范围的边界校验。",
      hot: false,
      tag: "候选",
      tagTone: "blue",
      conf: 58,
    },
    {
      code: "G01",
      name: "资产负债项目统计表",
      desc: "AI 召回，但本次通知未直接调整 G01 行列。可暂归档。",
      hot: false,
      tag: "仅参考",
      tagTone: "outline",
      conf: 41,
    },
  ],
  metrics: [
    { code: "G24.R03.C04", name: "最大百家金融机构同业融入余额", sub: "本币 + 外币 · 法人合并口径（调整后）", tag: "口径调整", tagTone: "amber" },
    { code: "G24.R03.C06", name: "按产品分类的同业融入余额", sub: "新增列：拆借 / 卖出回购 / 同业存放 / 其他", tag: "新增", tagTone: "green" },
    { code: "G21.R01-R09", name: "期限缺口分档", sub: "由 7 档细化为 9 档（新增 1 月内、1 周内）", tag: "结构调整", tagTone: "violet" },
    { code: "G25.R02.C01", name: "合格优质流动性资产（HQLA）", sub: "纳入新型政策性金融工具，剔除部分受限资产", tag: "口径调整", tagTone: "amber" },
    { code: "G25.NSFR.R04", name: "可用稳定资金 · 部分稳定资金", sub: "细化为三档：50% / 70% / 90%", tag: "口径调整", tagTone: "amber" },
    { code: "G24.R03", name: "上报时限", sub: "月报 13 天 → 月报 6 天", tag: "频度调整", tagTone: "blue" },
  ],
  questions: [
    "G24 法人合并口径下，是否包含本行境外分行的同业融入头寸？需业务确认。",
    "G24 新增产品分类列与本行现有产品代码映射是否完备？是否存在「其他」兜底无法归类的情况？",
    "G25 中纳入的「新型政策性金融工具」具体范围以哪份监管解读为准？是否需向监管局发函确认？",
    "G21 新增的「1 周内」分档对应现金流模型是否需要重新切分？",
    "上报时限缩短 7 天，本行 ETL 调度窗口是否能在 T+5 完成数据准备？",
  ],
  history: [
    { id: "REG-2024-0118-007", title: "2024 年度非现场监管报表填报工作通知", date: "2024-01-18", match: 86 },
    { id: "REG-2024-0405-003", title: "G24 同业融入余额口径专题答疑", date: "2024-04-05", match: 74 },
    { id: "REG-2023-1209-011", title: "流动性风险监管指标体系修订", date: "2023-12-09", match: 61 },
  ],
};

// =====================================================================
//                          DASHBOARD SCREEN
// =====================================================================
function DashboardScreen({ onGo }) {
  return (
    <div>
      <div className="h-eyebrow">工作台</div>
      <h1 className="h-title">监管报送变更影响分析与工单助手</h1>
      <p className="h-sub">围绕 监管发文 → 报表字段定位 → 影响分析 → 工单草稿 的全流程治理。当前样板域：一表通 1104 资金同业相关报表（G21 / G24 / G25）。</p>

      <div className="impact-summary mt-24">
        <div className="impact-stat hot">
          <div className="lbl">待处理发文</div>
          <div className="val">3</div>
          <div className="delta">较昨日 +1 · 1 项高影响</div>
        </div>
        <div className="impact-stat">
          <div className="lbl">影响分析中</div>
          <div className="val">7</div>
          <div className="delta">G24 / G21 / G25 共 5 项</div>
        </div>
        <div className="impact-stat">
          <div className="lbl">待复核工单</div>
          <div className="val">12</div>
          <div className="delta">业务 4 / 开发 5 / 治理 3</div>
        </div>
        <div className="impact-stat">
          <div className="lbl">本月已归档</div>
          <div className="val">18</div>
          <div className="delta">22 条经验沉淀</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 20, marginTop: 20 }}>
        <div className="card">
          <div className="card-head">
            <div>
              <h3>正在进行的发文任务</h3>
              <div className="sub">按风险等级和处理截止排序</div>
            </div>
            <button className="btn secondary sm" onClick={() => onGo("upload")}><Icon name="plus" size={12} />新建</button>
          </div>
          <table className="tbl">
            <thead>
              <tr><th>发文</th><th>当前阶段</th><th>风险</th><th>负责人</th><th>截止</th></tr>
            </thead>
            <tbody>
              <tr className="selected" onClick={() => onGo("portrait")}>
                <td>
                  <div style={{ fontWeight: 600, color: "var(--ink-900)" }}>2025 年非现场监管报表填报通知</div>
                  <div className="mono" style={{ color: "var(--ink-400)", marginTop: 2 }}>REG-2025-0103-002</div>
                </td>
                <td><span className="tag orange">文档画像</span></td>
                <td><span className="tag red"><span className="dot" />高</span></td>
                <td>江秋萍</td>
                <td className="mono">04-30</td>
              </tr>
              <tr>
                <td>
                  <div style={{ fontWeight: 600 }}>G24 同业融入口径专题答疑</div>
                  <div className="mono" style={{ color: "var(--ink-400)", marginTop: 2 }}>REG-2025-0228-004</div>
                </td>
                <td><span className="tag blue">字段定位</span></td>
                <td><span className="tag amber"><span className="dot" />中</span></td>
                <td>金融市场部</td>
                <td className="mono">05-15</td>
              </tr>
              <tr>
                <td>
                  <div style={{ fontWeight: 600 }}>2025 年区域特色报表备案补充</div>
                  <div className="mono" style={{ color: "var(--ink-400)", marginTop: 2 }}>REG-2025-0312-009</div>
                </td>
                <td><span className="tag violet">影响分析</span></td>
                <td><span className="tag amber"><span className="dot" />中</span></td>
                <td>数据治理</td>
                <td className="mono">05-20</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <h3>新增发文 · AI 推荐处理</h3>
              <div className="sub">基于历史经验和报送日历</div>
            </div>
          </div>
          <div className="tip-list">
            <div className="tip">
              <Icon name="sparkles" size={14} />
              <div>
                <b>建议优先：</b>2025 年度非现场监管报表填报通知。AI 识别命中 G24 / G21 / G25 三张资金同业报表，且包含口径调整与频度调整两类变更。
              </div>
            </div>
            <div className="tip">
              <Icon name="history" size={14} />
              <div>
                <b>历史经验复用：</b>2024 年同期处理流程可复用，预计可减少 60% 人工沟通。
              </div>
            </div>
          </div>
          <button className="btn primary mt-16" onClick={() => onGo("upload")} style={{ width: "100%", justifyContent: "center" }}>
            <Icon name="upload-cloud" size={14} /> 上传新发文，开始处理
          </button>
        </div>
      </div>
    </div>
  );
}

// =====================================================================
//                           UPLOAD SCREEN
// =====================================================================
function UploadScreen({ onContinue }) {
  const [over, setOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const startUpload = () => {
    setUploading(true);
    setProgress(0);
    const tick = () => {
      setProgress((p) => {
        if (p >= 100) { setTimeout(onContinue, 350); return 100; }
        const inc = p < 60 ? 8 + Math.random() * 6 : 3 + Math.random() * 4;
        return Math.min(100, p + inc);
      });
    };
    const iv = setInterval(() => {
      tick();
    }, 220);
    setTimeout(() => clearInterval(iv), 4000);
  };

  return (
    <div>
      <div className="h-eyebrow">第 1 步</div>
      <h1 className="h-title">上传监管发文</h1>
      <p className="h-sub">支持 PDF、Word、Excel、HTML 等格式。上传后系统会调用大模型完成文档解析、画像生成与报送对象候选定位。</p>

      <div className="upload-grid mt-24">
        <div>
          <div
            className={`dropzone ${over ? "over" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setOver(true); }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); startUpload(); }}
          >
            {!uploading ? (
              <>
                <div className="glyph"><Icon name="upload-cloud" size={26} /></div>
                <h3>将监管发文拖至此处</h3>
                <p>或者 <button className="btn ghost" style={{ color: "var(--orange-600)", padding: "0 4px", textDecoration: "underline" }} onClick={startUpload}>选择本地文件</button> 上传</p>
                <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
                  <span className="chip"><Icon name="file-text" size={12} />&nbsp;正式通知</span>
                  <span className="chip"><Icon name="file-spreadsheet" size={12} />&nbsp;表样 Excel</span>
                  <span className="chip"><Icon name="file-text" size={12} />&nbsp;填报说明</span>
                  <span className="chip"><Icon name="messages-square" size={12} />&nbsp;会议纪要</span>
                </div>
                <div className="meta">
                  <span>支持 PDF / DOCX / XLSX / HTML / TXT</span>
                  <span>单次 ≤ 50 MB</span>
                  <span>支持多文件批量</span>
                </div>
              </>
            ) : (
              <>
                <div className="glyph"><Icon name="loader" size={26} /></div>
                <h3>解析中 · {Math.round(progress)}%</h3>
                <p>金发〔2024〕39 号 · 12 页 · 5 个附件</p>
                <div className="bar" style={{ width: "60%", margin: "0 auto" }}><span style={{ width: progress + "%" }} /></div>
                <div className="meta" style={{ marginTop: 22 }}>
                  <span>{progress < 30 ? "正在拆分页面…" : progress < 60 ? "提取条款与表样…" : progress < 90 ? "调用 LLM 生成画像…" : "整理报表候选…"}</span>
                </div>
              </>
            )}
          </div>

          <div className="sec-h mt-24"><h2>从测试样本快速开始</h2><span className="line" /><span className="count">4 份</span></div>
          <div className="sample-grid">
            <button className="sample-doc" onClick={startUpload}>
              <span className="doc-type">推荐 · 正式通知</span>
              <span className="doc-title">2025 年银行业非现场监管报表填报工作通知</span>
              <span className="doc-meta">金发〔2024〕39 号 · PDF · 12 页 · 5 附件</span>
            </button>
            <button className="sample-doc" onClick={startUpload}>
              <span className="doc-type">表样 + 填报说明</span>
              <span className="doc-title">附件 4 · G24 表样和填报说明</span>
              <span className="doc-meta">2025 年 251 版 · ZIP · 解压 6 文件</span>
            </button>
            <button className="sample-doc" onClick={startUpload}>
              <span className="doc-type">监管答疑</span>
              <span className="doc-title">G24 同业融入口径专题答疑（草拟）</span>
              <span className="doc-meta">监管局答复 · DOCX · 3 页</span>
            </button>
            <button className="sample-doc" onClick={startUpload}>
              <span className="doc-type">参考</span>
              <span className="doc-title">银行业金融机构数据治理指引</span>
              <span className="doc-meta">银保监会 · PDF · 24 页</span>
            </button>
          </div>
        </div>

        <div className="upload-tips">
          <div className="card">
            <h4>关于文档画像</h4>
            <div className="tip-list">
              <div className="tip">
                <div>
                  <b>① 自动结构化：</b>抽取标题、文号、发文机关、生效日期、附件结构。
                </div>
              </div>
              <div className="tip">
                <div>
                  <b>② 报表候选：</b>识别可能涉及的 1104 报表（G/S 编号）及其优先级。
                </div>
              </div>
              <div className="tip">
                <div>
                  <b>③ 变更类型：</b>区分新增、停报、口径调整、频度调整、机构范围调整等。
                </div>
              </div>
              <div className="tip">
                <div>
                  <b>④ 待确认问题：</b>AI 必须给出需向业务/科技/监管确认的清单，不替代人工决策。
                </div>
              </div>
            </div>
          </div>

          <div className="card mt-16">
            <h4>最近上传</h4>
            <div className="recent-list">
              <div className="recent-row">
                <div className="ic"><Icon name="file-text" size={14} /></div>
                <div>
                  <div className="nm">G24 同业融入口径专题答疑</div>
                  <div className="meta">DOCX · 18 KB · 张明 · 2 小时前</div>
                </div>
                <span className="tag green"><span className="dot" />画像完成</span>
              </div>
              <div className="recent-row">
                <div className="ic"><Icon name="file-spreadsheet" size={14} /></div>
                <div>
                  <div className="nm">附件 1-1 一组并表口径表</div>
                  <div className="meta">XLS · 256 KB · 江秋萍 · 昨天</div>
                </div>
                <span className="tag amber"><span className="dot" />影响分析中</span>
              </div>
              <div className="recent-row">
                <div className="ic"><Icon name="file-text" size={14} /></div>
                <div>
                  <div className="nm">区域特色报表备案表</div>
                  <div className="meta">XLS · 78 KB · 李婧 · 3 天前</div>
                </div>
                <span className="tag blue"><span className="dot" />已生成工单</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =====================================================================
//                          PORTRAIT SCREEN  (focus)
// =====================================================================
function PortraitScreen({ onContinue, onBack, tweaks }) {
  return (
    <div>
      <div className="portrait-hero">
        <div className="ai-bar">
          <span className="sparkle">✦</span> AI 文档画像 · 大模型生成
        </div>
        <h1>{DOC.title}</h1>
        <div className="meta-row">
          <span><span className="muted">文号：</span><b>{DOC.docNum}</b></span>
          <span><span className="muted">发文机关：</span><b>{DOC.issuer}</b></span>
          <span><span className="muted">发布：</span><b>{DOC.publishedAt}</b></span>
          <span><span className="muted">页数：</span><b>{DOC.pages} 页</b></span>
          <span><span className="muted">附件：</span><b>{DOC.attachments} 个</b></span>
          <span><span className="muted">报送体系：</span><b className="tag orange" style={{ marginLeft: 4 }}>{DOC.system}</b></span>
        </div>
        <div className="actions">
          <button className="btn secondary sm"><Icon name="refresh-ccw" size={12} />重新生成画像</button>
          <button className="btn secondary sm"><Icon name="external-link" size={12} />查看原文</button>
        </div>
      </div>

      <div className="portrait-grid">
        <div className="portrait-main">

          {/* AI 摘要 */}
          <div className="ai-card">
            <div className="card-head">
              <div>
                <div className="ai-bar"><span className="sparkle">✦</span> 文档摘要</div>
                <h3 style={{ marginTop: 8 }}>大模型生成的发文摘要与变更结论</h3>
              </div>
              <div className="row">
                <span className="tag outline">claude-3.5</span>
                <button className="btn ghost sm"><Icon name="copy" size={12} /></button>
                <button className="btn ghost sm"><Icon name="thumbs-up" size={12} /></button>
              </div>
            </div>
            <p className="summary">
              本通知转发国家金融监督管理总局《关于做好 2025 年银行业非现场监管报表填报工作的通知》，明确 2025 年银行业非现场监管报表的制度落地、报表新增与修订、机构范围、报送频度与时限等要求。其中涉及本行的核心变化集中在
              <span className="hl">资金同业相关报表</span>，包含
              <span className="hl">G24 同业融入余额口径调整</span>、
              <span className="hl">G21 期限缺口划分细化</span>以及
              <span className="hl">G25 LCR/NSFR 流动性资产范围更新</span>；并要求各机构于
              <span className="hl">2025 年 4 月底前</span>完成内部报送制度修订备案。
            </p>
          </div>

          {/* 变更动作雷达 */}
          <div className="card">
            <div className="sec-h"><h2>变更动作识别</h2><span className="line" /><span className="count">8 项</span></div>
            <div className="action-grid">
              {DOC.actions.map((a, i) => (
                <div className="action-cell" key={i}>
                  <div className="ico"><Icon name={a.icon} size={14} /></div>
                  <div className="lbl">{a.lbl}</div>
                  <div className="val">{a.val}</div>
                  <div className="hint">{a.hint}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 涉及报表候选 */}
          <div className="card">
            <div className="sec-h">
              <h2>涉及报送对象候选</h2>
              <span className="line" />
              <span className="count">3 命中 · 3 候选</span>
            </div>
            <div className="report-cards">
              {DOC.reports.map((r) => (
                <div key={r.code} className={`report-card ${r.hot ? "hot" : ""}`}>
                  <div className="row between">
                    <span className="code">{r.code}</span>
                    <span className={`tag ${r.tagTone}`}>{r.tag}</span>
                  </div>
                  <div className="name">{r.name}</div>
                  <div className="desc">{r.desc}</div>
                  <div className="foot">
                    <span className="confidence">
                      置信度 <b className="mono" style={{ color: "var(--ink-700)" }}>{r.conf}%</b>
                      <span className="bar"><span style={{ width: r.conf + "%" }} /></span>
                    </span>
                    <button className="btn ghost sm">查看 →</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 关键摘录 */}
          <div className="card">
            <div className="sec-h"><h2>关键摘录与变更证据</h2><span className="line" /><span className="count">{DOC.highlights.length} 条</span></div>
            <div className="quote-list">
              {DOC.highlights.map((h, i) => (
                <div key={i} className="quote">
                  <span className="loc">{h.loc} · <span className={`tag ${h.tagText.includes("调整") ? "amber" : h.tagText.includes("频度") ? "blue" : "violet"}`} style={{ marginLeft: 4 }}>{h.tagText}</span></span>
                  <span>{h.text.split(/(G24|G21|G25|法人合并|月报|6 天|13 天|4 月底前|新型政策性金融工具|三档|9 档)/).map((s, j) =>
                    ["G24","G21","G25","法人合并","月报","6 天","13 天","4 月底前","新型政策性金融工具","三档","9 档"].includes(s)
                      ? <span key={j} className="annotate">{s}</span>
                      : <React.Fragment key={j}>{s}</React.Fragment>
                  )}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 涉及指标候选 */}
          <div className="card">
            <div className="sec-h"><h2>涉及指标 / 字段候选</h2><span className="line" /><span className="count">{DOC.metrics.length} 项</span></div>
            <div className="metric-list">
              {DOC.metrics.map((m, i) => (
                <div className="metric-row" key={i}>
                  <span className="code">{m.code}</span>
                  <div className="nm">
                    {m.name}
                    <div className="sub">{m.sub}</div>
                  </div>
                  <span className={`tag ${m.tagTone}`}>{m.tag}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT SIDE */}
        <div className="portrait-side">

          {/* 画像置信度 */}
          <div className="card">
            <div className="card-head"><div><h3>画像置信度</h3><div className="sub">影响 AI 召回质量</div></div></div>
            <div className="gauge">
              <div className="gauge-ring" style={{ "--p": DOC.confidence }}><b>{DOC.confidence}</b></div>
              <div style={{ flex: 1, fontSize: 12, color: "var(--ink-600)", lineHeight: 1.6 }}>
                <div><b style={{ color: "var(--ink-900)" }}>结构化解析</b> · 95%</div>
                <div><b style={{ color: "var(--ink-900)" }}>报表候选召回</b> · 92%</div>
                <div><b style={{ color: "var(--ink-900)" }}>口径差异识别</b> · 78%</div>
              </div>
            </div>
            {tweaks && tweaks.showAiGloss && (
              <div style={{ marginTop: 14, padding: 10, background: "var(--orange-50)", borderRadius: 8, fontSize: 11.5, color: "var(--orange-700)", lineHeight: 1.55 }}>
                <Icon name="info" size={11} /> &nbsp;口径差异识别置信度偏低，建议人工复核 G25 NSFR 部分稳定资金的三档划分依据。
              </div>
            )}
          </div>

          {/* 报送基本信息 */}
          <div className="card">
            <div className="card-head"><div><h3>报送上下文</h3></div></div>
            <div className="kv-list">
              <div className="kv-row"><span className="k">报送体系</span><span className="v">{DOC.system}</span></div>
              <div className="kv-row"><span className="k">制度版本</span><span className="v">{DOC.version}</span></div>
              <div className="kv-row"><span className="k">机构范围</span><span className="v">{DOC.scope}</span></div>
              <div className="kv-row"><span className="k">生效日期</span><span className="v">{DOC.effectiveFrom}</span></div>
              <div className="kv-row"><span className="k">处理截止</span><span className="v" style={{ color: "var(--red)" }}>2025-04-30</span></div>
              <div className="kv-row"><span className="k">建议负责团队</span><span className="v">数据治理 · 金融市场</span></div>
            </div>
          </div>

          {/* 待确认问题 */}
          <div className="card">
            <div className="card-head"><div><h3>待确认问题</h3><div className="sub">需向业务 / 科技 / 监管确认</div></div><span className="tag amber">{DOC.questions.length} 项</span></div>
            <div className="qa-list">
              {DOC.questions.map((q, i) => (
                <div className="qa-item" key={i}><span className="num">{i + 1}</span><span>{q}</span></div>
              ))}
            </div>
          </div>

          {/* 历史相似 */}
          <div className="card">
            <div className="card-head"><div><h3>相似历史发文</h3><div className="sub">可复用经验</div></div></div>
            <div className="timeline-mini">
              {DOC.history.map((h, i) => (
                <div className="row" key={i} style={{ alignItems: "flex-start", padding: "8px 0", borderBottom: i < DOC.history.length - 1 ? "1px dashed var(--border)" : "none" }}>
                  <div style={{ width: 6, height: 6, borderRadius: 3, background: "var(--orange-400)", marginTop: 7 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12.5, color: "var(--ink-900)", fontWeight: 500, lineHeight: 1.4 }}>{h.title}</div>
                    <div className="mono" style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 3 }}>{h.id} · {h.date} · 相似度 <b style={{ color: "var(--orange-600)" }}>{h.match}%</b></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* CTA */}
          <div className="row" style={{ position: "sticky", bottom: 0, gap: 8 }}>
            <button className="btn secondary" style={{ flex: 1, justifyContent: "center" }} onClick={onBack}><Icon name="arrow-left" size={14} />返回</button>
            <button className="btn primary lg" style={{ flex: 2, justifyContent: "center" }} onClick={onContinue}>
              进入字段定位 <Icon name="arrow-right" size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// =====================================================================
//                       LINEAGE / FIELD LOCATION
// =====================================================================
function LineageScreen({ onContinue, onBack }) {
  const [active, setActive] = useState("g24-r03-c04");

  const tree = [
    { id: "v2025", label: "2025 年 251 版", isFolder: true, children: [
      { id: "g24", label: "G24 最大百家金融机构同业融入情况表", isFolder: true, hit: 5, children: [
        { id: "g24-r03-c04", label: "R03 · C04 同业融入余额", hit: 1 },
        { id: "g24-r03-c06", label: "R03 · C06 按产品分类（新增）", hit: 1 },
        { id: "g24-r03-c08", label: "R03 · C08 到期日分档", hit: 0 },
      ]},
      { id: "g21", label: "G21 流动性期限缺口统计表", isFolder: true, hit: 3, children: [
        { id: "g21-r01-r09", label: "R01-R09 期限分档（9 档）", hit: 1 },
        { id: "g21-r10", label: "R10 期限缺口合计", hit: 0 },
      ]},
      { id: "g25", label: "G25 LCR / NSFR", isFolder: true, hit: 4, children: [
        { id: "g25-r02-c01", label: "R02 · C01 合格优质流动性资产", hit: 1 },
        { id: "g25-nsfr-r04", label: "NSFR R04 部分稳定资金", hit: 1 },
      ]},
    ]},
  ];

  const renderTree = (nodes, level = 0) => (
    <div className={level > 0 ? "tree-child" : ""}>
      {nodes.map((n) => (
        <div key={n.id}>
          <div
            className={`tree-node ${active === n.id ? "active" : ""}`}
            onClick={() => !n.isFolder && setActive(n.id)}
          >
            <span className="chev">{n.isFolder ? "▾" : "·"}</span>
            <span>{n.label}</span>
            {n.hit ? <span className="hit">+{n.hit}</span> : null}
          </div>
          {n.children && renderTree(n.children, level + 1)}
        </div>
      ))}
    </div>
  );

  return (
    <div>
      <div className="row between">
        <div>
          <div className="h-eyebrow">第 3 步</div>
          <h1 className="h-title">报表字段定位</h1>
          <p className="h-sub">将文档画像中的变更条款，定位到 1104 报表的具体行列项目、报送字段和源系统字段血缘。</p>
        </div>
        <div className="row">
          <button className="btn secondary" onClick={onBack}><Icon name="arrow-left" size={14} />画像</button>
          <button className="btn primary" onClick={onContinue}>影响分析 <Icon name="arrow-right" size={14} /></button>
        </div>
      </div>

      <div className="lineage-layout mt-24">
        <div>
          <div className="tree">
            <div style={{ padding: "4px 6px 10px", fontSize: 11.5, color: "var(--ink-500)", display: "flex", justifyContent: "space-between" }}>
              <span>1104 报表目录</span>
              <span className="mono" style={{ color: "var(--orange-600)" }}>+12 命中</span>
            </div>
            {renderTree(tree)}
          </div>
        </div>

        <div className="field-detail">
          <div className="card">
            <div className="card-head">
              <div>
                <div className="row" style={{ gap: 6 }}>
                  <span className="tag outline mono">G24.R03.C04</span>
                  <span className="tag amber">口径调整</span>
                  <span className="tag red"><span className="dot" />高影响</span>
                </div>
                <h3 style={{ marginTop: 8 }}>最大百家金融机构同业融入余额</h3>
                <div className="sub">单元格 · 月报 · 法人合并口径 · 单位：万元</div>
              </div>
              <div className="row">
                <button className="btn ghost sm"><Icon name="external-link" size={12} />查看表样</button>
              </div>
            </div>

            <div style={{ marginBottom: 18, fontSize: 13, lineHeight: 1.7, color: "var(--ink-700)" }}>
              <b style={{ color: "var(--ink-900)" }}>当前口径（2024 版）：</b>
              按金融机构法人合计的同业拆借、卖出回购、同业存放等同业融入项目余额之和。
              <br />
              <b style={{ color: "var(--orange-600)" }}>新口径（2025 版调整）：</b>
              口径调整为<span className="annotate" style={{ background: "rgba(234,84,4,0.16)", color: "var(--orange-700)", padding: "0 4px", borderRadius: 3 }}>按法人金融机构合并计算</span>（含其境内外分支机构），并按 C06 新增产品维度列。
            </div>

            <h4 style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, color: "var(--ink-500)", fontWeight: 600, margin: "8px 0 12px" }}>多段血缘</h4>
            <div className="lineage-chain">
              <div className="lineage-node hot">
                <div className="lbl">报送指标</div>
                <div className="name">G24.R03.C04 同业融入余额</div>
                <div className="sys">1104</div>
              </div>
              <div className="lineage-node">
                <div className="lbl">报送字段</div>
                <div className="name">同业融入余额（法人合并）</div>
                <div className="sys">rpt_g24.interbank_borrowing_bal_top100</div>
              </div>
              <div className="lineage-node">
                <div className="lbl">汇总表</div>
                <div className="name">同业头寸日聚合表</div>
                <div className="sys">dm_funding.interbank_pos_d</div>
              </div>
              <div className="lineage-node">
                <div className="lbl">ODS</div>
                <div className="name">同业交易明细</div>
                <div className="sys">ods.interbank_deal</div>
              </div>
              <div className="lineage-node">
                <div className="lbl">源系统</div>
                <div className="name">资金同业系统 · 交易对手维表</div>
                <div className="sys">FTS · CRMS</div>
              </div>
            </div>

            <h4 style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, color: "var(--ink-500)", fontWeight: 600, margin: "20px 0 10px" }}>命中证据</h4>
            <div className="quote-list">
              <div className="quote">
                <span className="loc">附件 4 · G24 填报说明 · 第 2 页 · 第 5 自然段</span>
                <span>同业融入余额口径调整为按<span className="annotate" style={{ background: "rgba(234,84,4,0.16)", color: "var(--orange-700)", padding: "0 4px", borderRadius: 3 }}>法人金融机构合并</span>计算，并新增按产品分类的列项。</span>
              </div>
            </div>

            <h4 style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1, color: "var(--ink-500)", fontWeight: 600, margin: "20px 0 10px" }}>关联字段映射</h4>
            <table className="tbl">
              <thead><tr><th>报送字段</th><th>内部字段</th><th>源系统</th><th>码值映射</th><th>状态</th></tr></thead>
              <tbody>
                <tr>
                  <td>同业融入余额</td>
                  <td className="mono">interbank_deal.balance</td>
                  <td>资金同业系统 (FTS)</td>
                  <td className="mono">DEAL_TYPE → IBL</td>
                  <td><span className="tag green"><span className="dot" />已确认</span></td>
                </tr>
                <tr>
                  <td>交易对手金融机构</td>
                  <td className="mono">counterparty.legal_entity_id</td>
                  <td>客户主数据 (CRMS)</td>
                  <td className="mono">INST_TYPE → BANK/NBFI</td>
                  <td><span className="tag amber"><span className="dot" />待治理复核</span></td>
                </tr>
                <tr>
                  <td>产品分类（新增）</td>
                  <td className="mono">interbank_deal.product_code</td>
                  <td>资金同业系统</td>
                  <td className="mono">PRD_CODE → 拆借/回购/存放</td>
                  <td><span className="tag red"><span className="dot" />待新增</span></td>
                </tr>
                <tr>
                  <td>分支机构归属</td>
                  <td className="mono">org.branch_path</td>
                  <td>机构主数据</td>
                  <td>—</td>
                  <td><span className="tag blue"><span className="dot" />待业务确认</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// =====================================================================
//                            IMPACT SCREEN
// =====================================================================
function ImpactScreen({ onContinue, onBack }) {
  return (
    <div>
      <div className="row between">
        <div>
          <div className="h-eyebrow">第 4 步</div>
          <h1 className="h-title">影响分析</h1>
          <p className="h-sub">基于字段定位结果，输出影响项清单：影响类型、范围、置信度和待确认问题。</p>
        </div>
        <div className="row">
          <button className="btn secondary" onClick={onBack}><Icon name="arrow-left" size={14} />字段定位</button>
          <button className="btn primary" onClick={onContinue}>生成工单 <Icon name="arrow-right" size={14} /></button>
        </div>
      </div>

      <div className="impact-summary mt-24">
        <div className="impact-stat hot"><div className="lbl">高风险影响项</div><div className="val">5</div><div className="delta">G24 / G25 占 4 项</div></div>
        <div className="impact-stat"><div className="lbl">中风险影响项</div><div className="val">7</div><div className="delta">字段映射 / 码值类</div></div>
        <div className="impact-stat"><div className="lbl">低风险 · 仅参考</div><div className="val">3</div><div className="delta">建议归档</div></div>
        <div className="impact-stat"><div className="lbl">影响系统数</div><div className="val">6</div><div className="delta">FTS / CRMS / DM / 报送 / 调度 / 校验</div></div>
      </div>

      <div className="card mt-16">
        <div className="sec-h"><h2>影响主线 · 血缘穿透</h2><span className="line" /><span className="count">G24.R03.C04 同业融入余额</span></div>
        <div className="lineage-chain">
          <div className="lineage-node hot">
            <div className="lbl">变更条款</div>
            <div className="name">法人合并口径 + 产品分类新增</div>
            <div className="sys">附件 4 · 第 2 页</div>
          </div>
          <div className="lineage-node">
            <div className="lbl">报送指标</div>
            <div className="name">G24.R03 · 同业融入余额</div>
            <div className="sys">月报 · 法人合并</div>
          </div>
          <div className="lineage-node">
            <div className="lbl">报送字段</div>
            <div className="name">interbank_borrowing_bal</div>
            <div className="sys">rpt_g24</div>
          </div>
          <div className="lineage-node">
            <div className="lbl">加工任务</div>
            <div className="name">job_rpt_g24_monthly</div>
            <div className="sys">Hive / Airflow</div>
          </div>
          <div className="lineage-node">
            <div className="lbl">源系统</div>
            <div className="name">资金同业系统 (FTS)</div>
            <div className="sys">interbank_deal · counterparty</div>
          </div>
        </div>
      </div>

      <div className="card mt-16">
        <div className="sec-h"><h2>影响项清单</h2><span className="line" /><span className="count">15 项</span></div>
        <table className="tbl">
          <thead><tr>
            <th style={{ width: 28 }}>#</th>
            <th>影响对象</th>
            <th>影响类型</th>
            <th>来源系统</th>
            <th>责任团队</th>
            <th style={{ width: 84 }}>风险</th>
            <th style={{ width: 100 }}>置信度</th>
            <th style={{ width: 110 }}>复核状态</th>
          </tr></thead>
          <tbody>
            {[
              { i: 1, obj: "G24.R03.C04 同业融入余额（法人合并）", type: "口径调整", sys: "FTS / 报送", team: "金融市场科技", risk: "red", riskTxt: "高", conf: 96, st: "待开发复核" },
              { i: 2, obj: "G24.R03.C06 按产品分类（新增列）", type: "字段新增", sys: "FTS / 码值维表", team: "数据治理", risk: "red", riskTxt: "高", conf: 92, st: "待治理复核" },
              { i: 3, obj: "G24 上报时限 13 天 → 6 天", type: "频度/调度", sys: "调度 / 校验", team: "数据平台", risk: "red", riskTxt: "高", conf: 100, st: "待业务复核" },
              { i: 4, obj: "G21.R01-R09 期限分档细化", type: "结构调整", sys: "DM 流动性主题", team: "流动性管理", risk: "amber", riskTxt: "中", conf: 88, st: "待业务复核" },
              { i: 5, obj: "G25.R02.C01 HQLA 范围", type: "口径调整", sys: "投资 / 货币市场", team: "金融市场部", risk: "red", riskTxt: "高", conf: 81, st: "待业务复核" },
              { i: 6, obj: "G25.NSFR.R04 部分稳定资金三档", type: "口径调整", sys: "存款主题 / 客户分类", team: "存款业务", risk: "amber", riskTxt: "中", conf: 76, st: "待业务复核" },
              { i: 7, obj: "G27 同业存放校验联动", type: "校验规则", sys: "数据质量", team: "数据治理", risk: "amber", riskTxt: "中", conf: 70, st: "待复核" },
              { i: 8, obj: "境外分行同业头寸合并", type: "组织范围", sys: "机构主数据", team: "主数据团队", risk: "amber", riskTxt: "中", conf: 65, st: "待业务确认" },
            ].map((r) => (
              <tr key={r.i}>
                <td className="mono" style={{ color: "var(--ink-400)" }}>{r.i.toString().padStart(2, "0")}</td>
                <td><div style={{ fontWeight: 500, color: "var(--ink-900)" }}>{r.obj}</div></td>
                <td><span className="tag outline">{r.type}</span></td>
                <td className="mono" style={{ fontSize: 12 }}>{r.sys}</td>
                <td>{r.team}</td>
                <td><span className={`tag ${r.risk}`}><span className="dot" />{r.riskTxt}</span></td>
                <td>
                  <span className="confidence">
                    <b className="mono" style={{ color: "var(--ink-700)" }}>{r.conf}%</b>
                    <span className="bar" style={{ width: 48 }}><span style={{ width: r.conf + "%" }} /></span>
                  </span>
                </td>
                <td><span className="tag blue">{r.st}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =====================================================================
//                            TICKET SCREEN
// =====================================================================
const TICKETS = [
  { id: "tk1", type: "口径确认", typeTone: "violet", priority: "P0", title: "G24 同业融入余额 法人合并口径确认", desc: "确认境外分行头寸是否合并、码值映射边界。", team: "金融市场部 · 数据治理" },
  { id: "tk2", type: "数据映射", typeTone: "blue",  priority: "P0", title: "G24 新增产品分类列字段映射", desc: "PRD_CODE → 拆借 / 卖出回购 / 同业存放 / 其他。", team: "数据治理 · 主数据" },
  { id: "tk3", type: "报送加工", typeTone: "orange",priority: "P0", title: "G24 月报加工任务改造（含上报时限）", desc: "调度由 T+13 提前至 T+6，需重排上游依赖。", team: "数据平台 · 报送科技" },
  { id: "tk4", type: "源系统改造", typeTone: "red", priority: "P1", title: "资金同业系统产品代码采集补充", desc: "新增 product_code 字段 + 增量回灌历史数据。", team: "金融市场科技 · FTS 团队" },
  { id: "tk5", type: "校验规则", typeTone: "amber", priority: "P1", title: "G24 ↔ G27 同业存放联动校验", desc: "新增表间一致性规则，覆盖三档差异容忍。", team: "数据质量团队" },
  { id: "tk6", type: "测试验收", typeTone: "green", priority: "P1", title: "G24 / G21 / G25 联合回归测试", desc: "覆盖法人合并、产品分类、HQLA 范围三类样例。", team: "测试团队 · 业务验收" },
  { id: "tk7", type: "归档复盘", typeTone: "outline", priority: "P2", title: "2025 年填报通知处理结论归档", desc: "结论与经验回写至规则库与历史案例。", team: "报送管理" },
];

function TicketScreen({ onBack, onFinish }) {
  const [active, setActive] = useState("tk3");
  const t = TICKETS.find((x) => x.id === active);

  return (
    <div>
      <div className="row between">
        <div>
          <div className="h-eyebrow">第 5 步 · 终</div>
          <h1 className="h-title">工单草稿</h1>
          <p className="h-sub">按影响类型分层生成草稿。AI 给出建议正文与可审查 SQL，最终由人工确认后流转。</p>
        </div>
        <div className="row">
          <button className="btn secondary" onClick={onBack}><Icon name="arrow-left" size={14} />影响分析</button>
          <button className="btn secondary"><Icon name="download" size={14} />导出全部</button>
          <button className="btn primary" onClick={onFinish}><Icon name="send" size={14} />提交流转</button>
        </div>
      </div>

      <div className="ticket-grid mt-24">
        <div>
          <div className="sec-h" style={{ marginBottom: 10 }}><h2>分层工单</h2><span className="line" /><span className="count">{TICKETS.length} 个草稿</span></div>
          <div className="ticket-list">
            {TICKETS.map((tk) => (
              <div key={tk.id} className={`ticket-item ${active === tk.id ? "active" : ""}`} onClick={() => setActive(tk.id)}>
                <div className="row between">
                  <span className={`tag ${tk.typeTone}`}>{tk.type}</span>
                  <span className="tag outline mono">{tk.priority}</span>
                </div>
                <div className="title" style={{ marginTop: 8 }}>{tk.title}</div>
                <div className="desc">{tk.desc}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="ticket-doc">
          <div className="doc-head">
            <div>
              <div className="row" style={{ gap: 6 }}>
                <span className={`tag ${t.typeTone}`}>{t.type}</span>
                <span className="tag outline mono">{t.priority}</span>
                <span className="tag orange">AI 草稿</span>
              </div>
              <h2 style={{ marginTop: 8 }}>{t.title}</h2>
              <div className="doc-meta">TK-2025-{t.id.toUpperCase()} · 关联 REG-2025-0103-002 · 责任 {t.team}</div>
            </div>
            <div className="row">
              <button className="btn ghost sm"><Icon name="copy" size={12} /></button>
              <button className="btn secondary sm"><Icon name="pencil" size={12} />编辑</button>
            </div>
          </div>

          <div className="doc-body">
            <div className="doc-section">
              <h4>背景与变更来源</h4>
              <p>金发〔2024〕39 号《关于做好 2025 年银行业非现场监管报表填报工作的通知》要求：G24「最大百家金融机构同业融入情况表」上报时限由月报 13 天调整为 6 天；同时口径调整为按法人金融机构合并并新增按产品分类的列项。本工单针对报送加工与调度侧改造。</p>
            </div>

            <div className="doc-section">
              <h4>影响范围</h4>
              <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                <span className="tag outline mono">rpt_g24</span>
                <span className="tag outline mono">job_rpt_g24_monthly</span>
                <span className="tag outline mono">dm_funding.interbank_pos_d</span>
                <span className="tag outline mono">ods.interbank_deal</span>
                <span className="tag outline mono">qc_g24_g27_consistency</span>
              </div>
            </div>

            <div className="doc-section">
              <h4>建议处理动作</h4>
              <p>
                1. 修改 G24 月报加工任务：将上游依赖从 T+12 提前至 T+5，对应调整 dm_funding 主题层日聚合任务调度。<br />
                2. 增加产品分类维度：在 dm_funding 聚合中按 product_code 切分，承接报送字段 C06–C09。<br />
                3. 法人合并口径：通过 org.legal_entity_id 进行 group by；境外分行头寸的纳入与否需口径确认工单同步确认。<br />
                4. 与 G27 联动校验脚本需同步更新。
              </p>
            </div>

            <div className="doc-section">
              <h4>可审查 SQL · 差异分析草稿</h4>
              <pre className="sql-block">
<span className="c">-- 法人合并 + 产品分类新口径下的 G24 R03 同业融入余额</span>{"\n"}
<span className="k">SELECT</span>{"  "}cp.legal_entity_id{"  "}<span className="k">AS</span> counterparty_le,{"\n"}
{"        "}d.product_code,{"\n"}
{"        "}<span className="f">SUM</span>(d.balance){"  "}<span className="k">AS</span> interbank_borrowing_bal{"\n"}
<span className="k">FROM</span>   ods.interbank_deal d{"\n"}
<span className="k">JOIN</span>   crms.counterparty cp <span className="k">ON</span> d.counterparty_id = cp.counterparty_id{"\n"}
<span className="k">WHERE</span>  d.deal_type <span className="k">IN</span> (<span className="s">'IBL'</span>, <span className="s">'REPO_SELL'</span>, <span className="s">'NOSTRO'</span>){"\n"}
{"  "}<span className="k">AND</span> d.report_date = <span className="s">'${"{"}biz_date{"}"}'</span>{"\n"}
<span className="k">GROUP</span> <span className="k">BY</span> cp.legal_entity_id, d.product_code{"\n"}
<span className="k">ORDER</span> <span className="k">BY</span> interbank_borrowing_bal <span className="k">DESC</span>{"\n"}
<span className="k">LIMIT</span> 100;
              </pre>
              <div className="checks-row" style={{ marginTop: 10 }}>
                <span className="check-pill ok"><Icon name="shield-check" size={11} />只读查询</span>
                <span className="check-pill ok"><Icon name="shield-check" size={11} />白名单字段</span>
                <span className="check-pill warn"><Icon name="alert-triangle" size={11} />涉及交易对手字段 · 默认脱敏</span>
                <span className="check-pill ok"><Icon name="shield-check" size={11} />未发现 DDL/DML</span>
              </div>
            </div>

            <div className="doc-section">
              <h4>验收标准</h4>
              <p>1) 月度 G24 报表可在 T+5 完成生成与校验；2) C04 / C06 与 G27 同业存放校验差异 ≤ 万分之一；3) 法人合并口径下 Top100 排名变化由业务签字确认；4) 全量历史 6 个月数据完成回灌并通过质量校验。</p>
            </div>

            <div className="doc-section">
              <h4>关联与依赖</h4>
              <table className="tbl">
                <thead><tr><th>类型</th><th>关联对象</th><th>关系</th></tr></thead>
                <tbody>
                  <tr><td>口径确认工单</td><td>TK-2025-TK1 · 法人合并口径</td><td>前置</td></tr>
                  <tr><td>数据映射工单</td><td>TK-2025-TK2 · 产品分类映射</td><td>前置</td></tr>
                  <tr><td>源系统改造工单</td><td>TK-2025-TK4 · FTS product_code 采集</td><td>并行</td></tr>
                  <tr><td>校验规则工单</td><td>TK-2025-TK5 · G24 ↔ G27 联动</td><td>后置</td></tr>
                  <tr><td>测试验收工单</td><td>TK-2025-TK6 · 联合回归</td><td>验收</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =====================================================================
//                            EXPORT TO WINDOW
// =====================================================================
Object.assign(window, {
  DashboardScreen,
  UploadScreen,
  PortraitScreen,
  LineageScreen,
  ImpactScreen,
  TicketScreen,
});
