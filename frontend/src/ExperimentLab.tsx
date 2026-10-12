import { useEffect, useState } from "react";
import { request } from "./workspaceApi";
import {
  ExecutionParameters,
  type Execution,
  type ExecutionDraft,
} from "./ExecutionParameters";

type Protocol = {
  title: string;
  hypothesis: string;
  task: string;
  dataset: string;
  split: string;
  baseline: string;
  variable: string;
  controls: string;
  metric: string;
  direction: string;
  criterion: string;
  seeds: number[];
  resources: string;
  failure: string;
  source_artifact_id: string | null;
  document_ids: string[];
  execution?: Execution | null;
};
type ProtocolContent = {
  protocol: Protocol;
  revision: number;
  checks: string[];
  history?: { revision: number; protocol: Protocol }[];
};
const initial: Protocol = {
  title: "",
  hypothesis: "",
  task: "classification",
  dataset: "",
  split: "",
  baseline: "",
  variable: "",
  controls: "",
  metric: "accuracy",
  direction: "higher",
  criterion: "",
  seeds: [11, 23, 47],
  resources: "",
  failure: "",
  source_artifact_id: null,
  document_ids: [],
};
const labels: [keyof Protocol, string, string][] = [
  ["title", "实验名称", "例如：检索方式对有证据回答率的影响"],
  ["hypothesis", "待验证假设", "明确改变什么、预计影响什么；尚未开展实验"],
  ["dataset", "数据与许可", "数据名称、版本、来源、许可；未确定请填写待定"],
  ["split", "数据划分", "官方固定划分，或训练/验证/测试比例、种子及防泄漏规则"],
  ["baseline", "对照基线", "使用什么作为比较起点"],
  ["variable", "实验变量与取值", "只改变的变量、各组具体配置"],
  [
    "controls",
    "固定条件",
    "模型、数据、预算、批大小、环境；计时还须预热和同步",
  ],
  ["metric", "主要指标", "例如 accuracy、F1、perplexity、Recall@10"],
  ["criterion", "判定标准", "预先约定怎样支持或否定假设，不按结果临时改阈值"],
  [
    "resources",
    "资源与试跑",
    "设备、内存、预计时间和小规模试跑；资源未知写待测",
  ],
  ["failure", "失败与负结果", "区分无效运行与有效负结果；说明如何记录失败运行"],
];

export function ProtocolEditor({
  identifier,
  content,
  documents = [],
  source,
  suggestion,
}: {
  identifier?: string;
  content?: ProtocolContent;
  documents?: string[];
  source?: string;
  suggestion?: ExecutionDraft;
}) {
  const [draft, setDraft] = useState<Protocol>(
    content?.protocol || {
      ...initial,
      ...(suggestion || {}),
      document_ids: documents,
      source_artifact_id: source || null,
    },
  );
  const [seedText, setSeedText] = useState(
    (content?.protocol.seeds || suggestion?.seeds || initial.seeds).join(", "),
  );
  const [savedId, setSavedId] = useState(identifier || "");
  const [revision, setRevision] = useState(content?.revision || 0);
  const [checks, setChecks] = useState(content?.checks || []);
  const [history, setHistory] = useState(content?.history || []);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  async function save() {
    setBusy(true);
    setNotice("");
    try {
      const parts = seedText.split(/[,，\s]+/).filter(Boolean);
      if (!parts.length || parts.some((v) => !/^\d+$/.test(v)))
        throw new Error("种子请填写不同的非负整数，用逗号分隔。");
      const protocol = {
        ...draft,
        seeds: parts.map(Number),
        document_ids: savedId ? draft.document_ids : documents,
      };
      const value = await request<ProtocolContent & { id: string }>(
        savedId
          ? `/api/experiments/protocols/${savedId}`
          : "/api/experiments/protocols",
        savedId ? { protocol, revision } : protocol,
        savedId ? "PUT" : "POST",
      );
      setSavedId(value.id);
      setRevision(value.revision);
      setDraft(value.protocol);
      setChecks(value.checks);
      setHistory(value.history || []);
      setNotice(
        `实验设计卡第 ${value.revision} 版已保存，可在任务与成果重新打开。尚未执行实验。`,
      );
    } catch (e) {
      setNotice(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="work-card protocol-editor">
      <summary>
        {identifier ? "编辑实验设计卡" : "把研究设想落实为实验设计卡"}
      </summary>
      <p>
        逐项确定对照、变量和判定标准；保存卡片不会开始训练，也不会把拟议设置当成论文事实。关联文献：
        {(savedId ? draft.document_ids : documents).length} 篇。
      </p>
      {savedId && <p>当前保存版本：第 {revision} 版</p>}
      <details className="module-help">
        <summary>功能与用法</summary>
        <p>
          先写清假设、对照、唯一变化的因素、数据划分和判定标准，再填资源与失败记录方式。种子用逗号分隔；每个种子代表一次独立完整运行。
        </p>
        <p>
          保存后在“任务与成果”重开。每次修改生成新版本；可以载入历史版本继续编辑。统计结果绑定保存时的版本。JSON
          导出包含修订历史。
        </p>
      </details>
      <div className="chart-controls">
        <label>
          任务类别
          <select
            aria-label="实验任务类别"
            value={draft.task}
            onChange={(e) => setDraft({ ...draft, task: e.target.value })}
          >
            <option value="classification">分类</option>
            <option value="language_modeling">语言建模</option>
            <option value="translation">机器翻译</option>
            <option value="retrieval">检索</option>
            <option value="other">其他</option>
          </select>
        </label>
        <label>
          指标方向
          <select
            aria-label="实验指标方向"
            value={draft.direction}
            onChange={(e) => setDraft({ ...draft, direction: e.target.value })}
          >
            <option value="higher">越高越好</option>
            <option value="lower">越低越好</option>
          </select>
        </label>
        <label>
          独立运行种子
          <input
            aria-label="实验随机种子"
            value={seedText}
            onChange={(e) => setSeedText(e.target.value)}
          />
        </label>
      </div>
      <div className="protocol-fields">
        {labels.map(([key, label, placeholder]) => (
          <label key={key}>
            {label}
            <textarea
              aria-label={label}
              rows={key === "title" || key === "metric" ? 1 : 2}
              maxLength={key === "title" ? 180 : key === "metric" ? 100 : 1000}
              value={String(draft[key])}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
              placeholder={placeholder}
            />
          </label>
        ))}
      </div>
      <ExecutionParameters
        value={draft.execution}
        onChange={(execution) => setDraft({ ...draft, execution })}
        savedId={savedId}
        revision={revision}
      />
      <button disabled={busy} onClick={() => void save()}>
        {busy ? "正在保存…" : "保存实验设计卡"}
      </button>
      <p role="status">{notice}</p>
      {checks.map((v, i) => (
        <p key={i} className="work-notice">
          {v}
        </p>
      ))}
      {savedId && (
        <div className="work-row">
          <a href={`/api/artifacts/${savedId}/export?format=md`}>导出设计卡</a>
          <a href={`/api/artifacts/${savedId}/export?format=json`}>
            设计与修订记录 JSON
          </a>
        </div>
      )}
      {history
        .slice()
        .reverse()
        .map((h) => (
          <details key={h.revision}>
            <summary>设计修订 {h.revision}</summary>
            <p>历史版本；使用下方按钮载入后保存，会产生新修订。</p>
            <pre className="protocol-history">
              {JSON.stringify(h.protocol, null, 2)}
            </pre>
            <button
              onClick={() => {
                setDraft(h.protocol);
                setSeedText(h.protocol.seeds.join(", "));
                setNotice("已载入历史设计，保存后生成新修订。");
              }}
            >
              载入此设计继续编辑
            </button>
          </details>
        ))}
    </details>
  );
}

type Statistics = {
  group: string;
  n: number;
  mean: number;
  sd: number;
  ci95_low: number;
  ci95_high: number;
};
export type MeasurementContent = {
  summary: Statistics[];
  warnings: string[];
  source_sha256: string;
  spec: { interval: string; metric: string; unit: string; data_label: string };
  protocol_snapshot?: { id: string; revision: number };
};
export function MeasurementResult({
  identifier,
  content,
}: {
  identifier: string;
  content: MeasurementContent;
}) {
  const root = `/api/experiments/${identifier}/files/`;
  const number = (value: number) => Number(value.toPrecision(6)).toString();
  return (
    <div className="measurement-result">
      <p>
        {content.spec.data_label === "example"
          ? "示例数据"
          : "用户提供的测量数据（真实性未核验）"}{" "}
        · {content.spec.metric} {content.spec.unit} · 误差棒：
        {content.spec.interval === "sd" ? "样本标准差" : "均值 95% t 置信区间"}
      </p>
      {content.protocol_snapshot && (
        <p>
          绑定实验设计修订 {content.protocol_snapshot.revision}
          ；以后修改设计卡不会改写这次测量的原计划。
        </p>
      )}
      <img src={root + "chart.png"} alt="各方法均值、误差棒与每次运行原始点" />
      <div className="table-scroll">
        <table className="evidence-matrix">
          <thead>
            <tr>
              {[
                "方法",
                "独立运行数",
                "均值",
                "样本标准差",
                "95% t 均值区间",
              ].map((v) => (
                <th key={v}>{v}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {content.summary.map((r) => (
              <tr key={r.group}>
                <td>{r.group}</td>
                <td>{r.n}</td>
                <td>{number(r.mean)}</td>
                <td>{number(r.sd)}</td>
                <td>
                  [{number(r.ci95_low)}, {number(r.ci95_high)}]
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {content.warnings.map((w, i) => (
        <p className="work-notice" key={i}>
          {w}
        </p>
      ))}
      <div className="work-row">
        {[
          "chart.png",
          "chart.svg",
          "chart.pdf",
          "summary.csv",
          "raw.csv",
          "bundle.zip",
        ].map((name) => (
          <a key={name} href={root + name}>
            {name === "bundle.zip" ? "原始数据、统计与重跑包" : "下载 " + name}
          </a>
        ))}
      </div>
      <details>
        <summary>核对数据指纹</summary>
        <code className="data-fingerprint">{content.source_sha256}</code>
      </details>
    </div>
  );
}

export function MeasurementLab() {
  const [csv, setCsv] = useState("");
  const [title, setTitle] = useState("重复实验统计");
  const [group, setGroup] = useState("method");
  const [run, setRun] = useState("seed");
  const [metric, setMetric] = useState("score");
  const [unit, setUnit] = useState("");
  const [interval, setInterval] = useState("sd");
  const [dataLabel, setDataLabel] = useState("measured");
  const [protocol, setProtocol] = useState("");
  const [protocols, setProtocols] = useState<
    { id: string; title: string; kind: string }[]
  >([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState<
    (MeasurementContent & { id: string }) | null
  >(null);
  async function refresh() {
    try {
      setProtocols(
        (await request<typeof protocols>("/api/artifacts")).filter(
          (a) => a.kind === "protocol",
        ),
      );
    } catch (e) {
      setNotice(String(e));
    }
  }
  useEffect(() => {
    void refresh();
  }, []);
  return (
    <details className="work-card measurement-lab">
      <summary>重复实验统计与误差棒</summary>
      <p>
        每行是一组方法的一次独立运行。上传真实
        CSV，计算均值、样本标准差和均值置信区间；保留所有原始点，不自动宣称哪种方法显著胜出。
      </p>
      <details className="module-help">
        <summary>功能与用法</summary>
        <p>
          导入或粘贴
          CSV，填写方法列、运行标识列、指标列及单位。每组至少两次运行；重复标识、缺值和无穷值会报错。不要把同一次训练的
          batch 当成多次实验。
        </p>
        <p>
          标准差描述运行间波动；95% t
          区间估计均值的不确定性，小样本和偏态时需谨慎解释。先刷新并选择实验设计，再计算保存。图表、原始
          CSV 和复现脚本均可下载。
        </p>
      </details>
      <button
        onClick={() => {
          setCsv(
            "method,seed,score\n基线,11,70\n基线,23,72\n基线,47,71\n改进,11,73\n改进,23,74\n改进,47,72",
          );
          setGroup("method");
          setRun("seed");
          setMetric("score");
          setDataLabel("example");
          setResult(null);
        }}
      >
        载入示例（非实验结果）
      </button>
      <input
        type="file"
        accept=".csv,text/csv"
        aria-label="导入重复实验 CSV"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file)
            void (async () => {
              try {
                if (file.size > 2000000) throw new Error("CSV 上限 2 MB");
                setCsv(await file.text());
                setResult(null);
                setNotice("已载入，请核对列名、单位及数据类型。");
              } catch (error) {
                setNotice(String(error));
              }
            })();
        }}
      />
      <textarea
        aria-label="重复实验 CSV"
        rows={8}
        value={csv}
        onChange={(e) => {
          setCsv(e.target.value);
          setResult(null);
        }}
        placeholder={"method,seed,score\n填写真实实验结果"}
      />
      <div className="chart-controls">
        {[
          ["统计标题", title, setTitle],
          ["方法分组列", group, setGroup],
          ["独立运行标识列", run, setRun],
          ["实测指标列", metric, setMetric],
          ["统计单位", unit, setUnit],
        ].map(([label, value, setter]) => (
          <label key={String(label)}>
            {String(label)}
            <input
              aria-label={String(label)}
              value={String(value)}
              onChange={(e) =>
                (setter as (value: string) => void)(e.target.value)
              }
            />
          </label>
        ))}
        <label>
          误差棒含义
          <select
            aria-label="误差棒含义"
            value={interval}
            onChange={(e) => setInterval(e.target.value)}
          >
            <option value="sd">运行间样本标准差</option>
            <option value="ci95">均值 95% t 置信区间</option>
          </select>
        </label>
        <label>
          数据类型
          <select
            aria-label="统计数据类型"
            value={dataLabel}
            onChange={(e) => setDataLabel(e.target.value)}
          >
            <option value="measured">实际测量（用户声明）</option>
            <option value="example">示例数据</option>
          </select>
        </label>
        <label>
          关联实验设计
          <select
            aria-label="关联实验设计"
            value={protocol}
            onChange={(e) => setProtocol(e.target.value)}
          >
            <option value="">不关联</option>
            {protocols.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      <button onClick={() => void refresh()}>刷新实验设计列表</button>
      <button
        className="primary-button"
        disabled={busy || !csv.trim()}
        onClick={() =>
          void (async () => {
            setBusy(true);
            setNotice("");
            setResult(null);
            try {
              const value = await request<MeasurementContent & { id: string }>(
                "/api/experiments/analyze",
                {
                  title,
                  csv,
                  group,
                  run,
                  metric,
                  unit,
                  interval,
                  protocol_id: protocol || null,
                  data_label: dataLabel,
                },
              );
              setResult(value);
              setNotice("统计与原始数据已保存，可在任务与成果重新打开。");
            } catch (e) {
              setNotice(String(e));
            } finally {
              setBusy(false);
            }
          })()
        }
      >
        {busy ? "正在计算…" : "计算并保存重复实验统计"}
      </button>
      <p role="status">{notice}</p>
      {result && <MeasurementResult identifier={result.id} content={result} />}
    </details>
  );
}

export type { ProtocolContent };

export function ProposalRevision({
  identifier,
  audit,
}: {
  identifier: string;
  audit?: {
    source_title: string;
    original_proposal: Record<string, string>;
    before_checks: string[];
    after_checks: string[];
  };
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  return (
    <section className="work-card proposal-revision">
      <h3>按检查意见修订方案</h3>
      <p>
        依据当前设计问题生成独立修订稿，保留原始出处和原稿。只修订拟议方法与评估；不会自动运行实验，也不会把人工编辑稿覆盖掉。
      </p>
      <details className="module-help">
        <summary>功能与用法</summary>
        <p>
          点击按钮后，到“任务与成果”查看后台进度并打开修订方案。展开检查记录，对照原稿和剩余问题，再填写实验设计卡。人工编辑稿未纳入模型输入；检查提示减少不等于科学性通过。
        </p>
      </details>
      <button
        disabled={busy}
        onClick={() =>
          void (async () => {
            setBusy(true);
            try {
              await request("/api/jobs", {
                kind: "refine_plan",
                payload: { artifact_id: identifier },
              });
              setNotice(
                "修订任务已加入后台，请在任务与成果查看进度并打开修订稿。",
              );
            } catch (e) {
              setNotice(String(e));
            } finally {
              setBusy(false);
            }
          })()
        }
      >
        复核并生成独立修订稿
      </button>
      <p role="status">{notice}</p>
      {audit && (
        <details>
          <summary>核对这次修订的原稿与检查记录</summary>
          <p>来源：{audit.source_title}。提示数减少不代表科学审查通过。</p>
          <h4>原检查意见</h4>
          {audit.before_checks.map((x, i) => (
            <p key={i}>{x}</p>
          ))}
          <h4>修订后仍需核对</h4>
          {audit.after_checks.map((x, i) => (
            <p key={i}>{x}</p>
          ))}
          <h4>修订前的拟议方法</h4>
          <p style={{ whiteSpace: "pre-wrap" }}>
            {audit.original_proposal.method_plan}
          </p>
          <h4>修订前的评估</h4>
          <p style={{ whiteSpace: "pre-wrap" }}>
            {audit.original_proposal.evaluation_plan}
          </p>
        </details>
      )}
    </section>
  );
}
