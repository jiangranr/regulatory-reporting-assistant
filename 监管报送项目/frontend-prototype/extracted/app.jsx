// app.jsx — root shell, sidebar nav, topbar, page routing
const { useState, useEffect, useMemo, useRef } = React;
const Icon = window.Icon;
const {
  DashboardScreen, UploadScreen, PortraitScreen,
  LineageScreen, ImpactScreen, TicketScreen,
} = window;

// --- Sidebar -----------------------------------------------------------
const STEPS = [
  { id: "dashboard", num: "·", label: "工作台", icon: "layout-dashboard" },
  { id: "upload",    num: "1", label: "上传发文", icon: "upload-cloud" },
  { id: "portrait",  num: "2", label: "文档画像", icon: "scan-text" },
  { id: "lineage",   num: "3", label: "字段定位", icon: "git-fork" },
  { id: "impact",    num: "4", label: "影响分析", icon: "radar" },
  { id: "ticket",    num: "5", label: "工单草稿", icon: "clipboard-list" },
];

function Sidebar({ current, onNavigate, completed }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">报</div>
        <div className="brand-text">
          <div className="brand-title">监管报送治理</div>
          <div className="brand-sub">一表通 · 1104 · 资金同业</div>
        </div>
      </div>

      <div className="nav-section">主流程</div>
      <nav className="nav">
        {STEPS.map((s) => {
          const isComplete = completed.includes(s.id);
          const isActive = current === s.id;
          return (
            <button
              key={s.id}
              className={`nav-item ${isActive ? "active" : ""} ${isComplete && !isActive ? "complete" : ""}`}
              onClick={() => onNavigate(s.id)}
            >
              <span className="step-num">{isComplete && !isActive ? "" : s.num}</span>
              <span>{s.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="nav-section">知识与设置</div>
      <nav className="nav">
        <button className="nav-item">
          <span className="step-num"><Icon name="database" size={12} /></span>
          <span>报送目录</span>
        </button>
        <button className="nav-item">
          <span className="step-num"><Icon name="library" size={12} /></span>
          <span>规则与口径</span>
        </button>
        <button className="nav-item">
          <span className="step-num"><Icon name="history" size={12} /></span>
          <span>历史案例</span>
        </button>
        <button className="nav-item">
          <span className="step-num"><Icon name="settings" size={12} /></span>
          <span>系统设置</span>
        </button>
      </nav>

      <div className="sidebar-foot">
        <div className="avatar">江</div>
        <div style={{ flex: 1 }}>
          <div style={{ color: "#FFFFFF", fontWeight: 500 }}>江秋萍</div>
          <div>数据治理团队</div>
        </div>
      </div>
    </aside>
  );
}

// --- Topbar ------------------------------------------------------------
function Topbar({ crumbs }) {
  return (
    <div className="topbar">
      <div className="crumb">
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="sep">/</span>}
            {i === crumbs.length - 1 ? <b>{c}</b> : <span>{c}</span>}
          </React.Fragment>
        ))}
      </div>
      <div className="topbar-actions">
        <div className="search">
          <Icon name="search" size={14} />
          <span>搜索发文、报表、指标、工单</span>
          <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-400)" }}>⌘K</span>
        </div>
        <button className="btn ghost" title="通知"><Icon name="bell" size={16} /></button>
        <button className="btn ghost" title="帮助"><Icon name="circle-help" size={16} /></button>
        <button className="btn secondary"><Icon name="upload" size={14} />新建任务</button>
      </div>
    </div>
  );
}

// --- App ---------------------------------------------------------------
function App() {
  const [page, setPage] = useState("upload");
  const [completed, setCompleted] = useState([]);
  const [t, setTweak] = window.useTweaks ? window.useTweaks(window.TWEAK_DEFAULTS) : [window.TWEAK_DEFAULTS, () => {}];

  // Apply accent color globally
  useEffect(() => {
    if (t.accent) {
      const r = document.documentElement;
      r.style.setProperty("--orange-500", t.accent);
      // Compute lighter/darker variants approximately
      const c = t.accent;
      // simple shading: not perfect but good enough for token shift
    }
  }, [t.accent]);

  useEffect(() => {
    if (window.lucide) window.lucide.createIcons();
  });

  const goto = (id) => {
    setCompleted((c) => {
      const idx = STEPS.findIndex((s) => s.id === id);
      const newComplete = STEPS.slice(1, idx).map((s) => s.id);
      return Array.from(new Set([...c, ...newComplete]));
    });
    setPage(id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const crumbsByPage = {
    dashboard: ["监管报送治理", "工作台"],
    upload: ["监管报送治理", "1104 · 资金同业", "上传发文"],
    portrait: ["监管报送治理", "1104 · 资金同业", "REG-2025-0103-002", "文档画像"],
    lineage: ["监管报送治理", "1104 · 资金同业", "REG-2025-0103-002", "字段定位"],
    impact: ["监管报送治理", "1104 · 资金同业", "REG-2025-0103-002", "影响分析"],
    ticket: ["监管报送治理", "1104 · 资金同业", "REG-2025-0103-002", "工单草稿"],
  };

  let body;
  if (page === "dashboard") body = <DashboardScreen onGo={goto} />;
  else if (page === "upload") body = <UploadScreen onContinue={() => goto("portrait")} />;
  else if (page === "portrait") body = <PortraitScreen onContinue={() => goto("lineage")} onBack={() => goto("upload")} tweaks={t} />;
  else if (page === "lineage") body = <LineageScreen onContinue={() => goto("impact")} onBack={() => goto("portrait")} />;
  else if (page === "impact") body = <ImpactScreen onContinue={() => goto("ticket")} onBack={() => goto("lineage")} />;
  else if (page === "ticket") body = <TicketScreen onBack={() => goto("impact")} onFinish={() => goto("dashboard")} />;

  return (
    <div className="app">
      <Sidebar current={page} onNavigate={goto} completed={completed} />
      <main className="main">
        <Topbar crumbs={crumbsByPage[page]} />
        <div className="page">{body}</div>
      </main>
      <TweaksUI t={t} setTweak={setTweak} />
    </div>
  );
}

function TweaksUI({ t, setTweak }) {
  if (!window.TweaksPanel) return null;
  const { TweaksPanel, TweakSection, TweakColor, TweakToggle } = window;
  return (
    <TweaksPanel title="Tweaks">
      <TweakSection title="主色调">
        <TweakColor
          value={t.accent}
          onChange={(v) => setTweak("accent", v)}
          options={["#EA5404", "#D94A1F", "#FF6D2C", "#B23A00"]}
        />
      </TweakSection>
      <TweakSection title="展示">
        <TweakToggle
          label="显示 AI 解释说明"
          value={!!t.showAiGloss}
          onChange={(v) => setTweak("showAiGloss", v)}
        />
      </TweakSection>
    </TweaksPanel>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
