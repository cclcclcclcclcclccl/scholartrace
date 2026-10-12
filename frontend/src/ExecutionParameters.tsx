import { useState } from "react";
import { request } from "./workspaceApi";

export type Execution = {
  kind: "attention_from_scratch";
  d_model: number;
  heads: number[];
  training_steps: number;
  optimizer: "Adam" | "AdamW" | "SGD";
  learning_rate: number;
  batch_size: number;
  sequence_length: number;
  warmup_runs: number;
  timing_runs: number;
  device: "cpu" | "gpu" | "undecided";
  failure_policy: "retain_all_runs";
};
export type ExecutionDraft = {
  execution: Execution;
  seeds: number[];
  task: string;
  metric: string;
  direction: string;
};
const example: Execution = {
  kind: "attention_from_scratch",
  d_model: 128,
  heads: [1, 2, 4, 8],
  training_steps: 200,
  optimizer: "AdamW",
  learning_rate: 0.001,
  batch_size: 8,
  sequence_length: 128,
  warmup_runs: 10,
  timing_runs: 30,
  device: "undecided",
  failure_policy: "retain_all_runs",
};
const fields = [
  ["d_model", "总隐藏维度 d_model"],
  ["training_steps", "每组训练步数"],
  ["learning_rate", "学习率"],
  ["batch_size", "计划批大小"],
  ["sequence_length", "计划序列长度"],
  ["warmup_runs", "计时预热次数"],
  ["timing_runs", "计时重复次数"],
] as const;
export type PreflightContent = {
  notice: string;
  protocol_snapshot: { revision: number };
  actual_batch_size: number;
  actual_sequence_length: number;
  seed: number;
  results: {
    heads: number;
    d_head: number;
    output_shape: number[];
    finite: boolean;
    normalized_attention: boolean;
  }[];
};
export function ExecutionResult({
  content,
  id,
}: {
  content: PreflightContent;
  id: string;
}) {
  return (
    <section className="execution-result">
      <h4>已保存设计第 {content.protocol_snapshot.revision} 版的执行预检</h4>
      <p>{content.notice}</p>
      <p>
        实际预检：CPU · batch={content.actual_batch_size} · sequence=
        {content.actual_sequence_length} · seed={content.seed}
      </p>
      <div className="table-scroll">
        <table className="evidence-matrix">
          <thead>
            <tr>
              <th>头数</th>
              <th>每头维度</th>
              <th>输出形状</th>
              <th>数值检查</th>
            </tr>
          </thead>
          <tbody>
            {content.results.map((row) => (
              <tr key={row.heads}>
                <td>{row.heads}</td>
                <td>{row.d_head}</td>
                <td>{row.output_shape.join(" × ")}</td>
                <td>
                  {row.finite && row.normalized_attention
                    ? "有限值、权重和通过"
                    : "需检查"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <a href={`/api/artifacts/${id}/export?format=json`}>
        下载预检参数、结果与设计快照
      </a>
      <p>
        在项目根目录运行：
        <code>
          .venv/Scripts/python.exe -m backend.execution_check 下载的JSON文件路径
        </code>
        。只重跑数值与形状预检，不训练模型。
      </p>
    </section>
  );
}
export function ExecutionParameters({
  value,
  onChange,
  savedId,
  revision,
}: {
  value?: Execution | null;
  onChange: (value: Execution | null) => void;
  savedId: string;
  revision: number;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState<
    (PreflightContent & { id: string }) | null
  >(null);
  return (
    <details className="execution-parameters">
      <summary>注意力头数实验：结构化参数与执行预检</summary>
      <p>
        这个可选模板用于从零训练的小型注意力语言模型。所填数值是拟议条件，不是论文事实；不适合直接修改已有预训练权重。
      </p>
      <details className="module-help">
        <summary>功能与用法</summary>
        <p>
          填写能整除总隐藏维度的不同头数，补齐训练预算、优化器和计时条件，再保存实验设计卡。预检只针对已保存版本，用小张量实际检查注意力计算；不会训练，也不测目标模型的真实耗时。未保存的更改不参与预检。
        </p>
      </details>
      {!value ? (
        <button
          onClick={() => onChange({ ...example, heads: [...example.heads] })}
        >
          启用拟议参数模板
        </button>
      ) : (
        <>
          <div className="protocol-fields">
            {fields.map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  aria-label={label}
                  type="number"
                  step={key === "learning_rate" ? "any" : "1"}
                  value={value[key] ?? ""}
                  onChange={(event) =>
                    onChange({
                      ...value,
                      [key]:
                        event.target.value === ""
                          ? undefined
                          : Number(event.target.value),
                    })
                  }
                />
              </label>
            ))}
            <label>
              注意力头数列表
              <input
                aria-label="注意力头数列表"
                defaultValue={value.heads.join(", ")}
                key={value.heads.join(",")}
                onBlur={(event) =>
                  onChange({
                    ...value,
                    heads: event.target.value
                      .split(/[,，\s]+/)
                      .filter(Boolean)
                      .map(Number),
                  })
                }
              />
            </label>
            <label>
              优化器
              <select
                aria-label="实验优化器"
                value={value.optimizer}
                onChange={(event) =>
                  onChange({
                    ...value,
                    optimizer: event.target.value as Execution["optimizer"],
                  })
                }
              >
                {["Adam", "AdamW", "SGD"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label>
              计划设备
              <select
                aria-label="计划设备"
                value={value.device}
                onChange={(event) =>
                  onChange({
                    ...value,
                    device: event.target.value as Execution["device"],
                  })
                }
              >
                <option value="undecided">待实测确认</option>
                <option value="cpu">CPU</option>
                <option value="gpu">GPU（计时须同步）</option>
              </select>
            </label>
          </div>
          <p>所有失败运行和有效负结果均须保留。每头维度按 d_model / h 计算。</p>
          <button
            onClick={() => {
              onChange(null);
              setResult(null);
            }}
          >
            移除此可选模板
          </button>
        </>
      )}
      <button
        disabled={!value || !savedId || busy}
        onClick={() =>
          void (async () => {
            setBusy(true);
            setNotice("");
            setResult(null);
            try {
              const data = await request<PreflightContent & { id: string }>(
                `/api/experiments/protocols/${savedId}/preflight`,
                { revision },
              );
              setResult(data);
            } catch (error) {
              setNotice(String(error));
            } finally {
              setBusy(false);
            }
          })()
        }
      >
        {busy ? "正在预检…" : `预检已保存的第 ${revision} 版`}
      </button>
      <p role="status">{notice}</p>
      {result && <ExecutionResult id={result.id} content={result} />}
    </details>
  );
}
