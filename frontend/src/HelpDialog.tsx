import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CircleHelp,
  GitCompareArrows,
  Layers3,
  ShieldCheck,
  StickyNote,
  X,
} from "lucide-react";
import { helpContent, type HelpTopic } from "./helpContent";
import "./help.css";

export function HelpButton({
  topic,
  onOpen,
  label,
}: {
  topic: HelpTopic;
  onOpen: (topic: HelpTopic) => void;
  label?: string;
}) {
  const name = `${helpContent[topic].label}使用说明`;
  return (
    <button
      type="button"
      className="module-help"
      aria-label={name}
      title={name}
      onClick={() => onOpen(topic)}
    >
      <CircleHelp size={16} />
      {label && <span>{label}</span>}
    </button>
  );
}

const tour: HelpTopic[] = ["overview", "reader", "notes", "audit"];
const topicIcons = {
  overview: Layers3,
  library: BookOpen,
  reader: BookOpen,
  ask: CircleHelp,
  notes: StickyNote,
  audit: GitCompareArrows,
};
export function HelpDialog({
  initialTopic,
  tutorial,
  onClose,
  onNavigate,
}: {
  initialTopic: HelpTopic;
  tutorial: boolean;
  onClose: () => void;
  onNavigate: (view: "reader" | "notes" | "audit") => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const [topic, setTopic] = useState(initialTopic);
  const content = helpContent[topic];
  const step = Math.max(0, tour.indexOf(topic));
  const Icon = topicIcons[topic];
  const topics = tutorial ? tour : (Object.keys(helpContent) as HelpTopic[]);
  useEffect(() => {
    const node = dialog.current!;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    node.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      node.close();
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    body.current?.scrollTo(0, 0);
    title.current?.focus({ preventScroll: true });
  }, [topic]);
  function go(view: "reader" | "notes" | "audit") {
    onNavigate(view);
    onClose();
  }
  return (
    <dialog
      ref={dialog}
      className="help-dialog"
      aria-labelledby="help-title"
      aria-describedby="help-intro"
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not([disabled]), a[href], input, select, textarea, [tabindex="0"]',
          ),
        ).filter((node) => node.getClientRects().length > 0);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            !controls.includes(document.activeElement as HTMLElement))
        ) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header className="help-top">
        <span>
          <Layers3 size={18} />
          墨衡 · {tutorial ? "首次使用指南" : "使用帮助"}
        </span>
        <button
          className="help-close"
          aria-label="关闭使用教程"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      <nav
        className="help-topics"
        aria-label={tutorial ? "教程步骤" : "帮助主题"}
      >
        {topics.map((item, index) => (
          <button
            key={item}
            aria-current={item === topic ? "step" : undefined}
            onClick={() => setTopic(item)}
          >
            {tutorial && <span>{index + 1}</span>}
            {helpContent[item].label}
          </button>
        ))}
      </nav>
      <div className="help-body" ref={body}>
        <div className="help-kicker">
          <Icon size={18} />
          {tutorial ? `第 ${step + 1} 步，共 ${tour.length} 步` : content.label}
        </div>
        <h2 id="help-title" tabIndex={-1} ref={title}>
          {content.title}
        </h2>
        <p id="help-intro" className="help-intro">
          {content.intro}
        </p>
        {topic === "overview" && (
          <div className="help-flow" aria-label="阅读到复核的完整流程">
            <span>
              <BookOpen size={21} />
              阅读 · 找依据
            </span>
            <ArrowRight size={18} />
            <span>
              <StickyNote size={21} />
              笔记 · 留出处
            </span>
            <ArrowRight size={18} />
            <span>
              <GitCompareArrows size={21} />
              更新 · 再核对
            </span>
          </div>
        )}
        <ol className="help-steps">
          {content.steps.map((item) => (
            <li key={item.title}>
              <strong>{item.title}</strong>
              <p>{item.text}</p>
            </li>
          ))}
        </ol>
        {topic === "audit" && (
          <section className="help-example" aria-label="版本复核真实示例">
            <h3>用已有样例，第一次就能看懂</h3>
            <p>Attention Is All You Need · 两个版本的 PDF 第 10 页</p>
            <div className="help-example-pair">
              <div>
                <small>v1 · 保存的旧证据</small>
                <strong>代码将于近期公开</strong>
                <p>“We intend to make the code … available soon.”</p>
              </div>
              <ArrowRight size={20} />
              <div>
                <small>v7 · 目标版本</small>
                <strong>代码已经可获取</strong>
                <p>“The code … is available at …”并给出仓库地址。</p>
              </div>
            </div>
            <p className="help-example-result">
              <ShieldCheck size={16} />
              这条笔记关注的代码公开状态变了，值得更新判断。
            </p>
            <p>
              再看训练硬件样例：两版第 7 页都写了 8 张 NVIDIA P100
              GPU。措辞变化，硬件信息未见变化。
            </p>
          </section>
        )}
        <h3 className="help-detail-title">
          {topic === "overview" ? "开始之前" : "功能与使用要点"}
        </h3>
        <dl className="help-features">
          {content.features.map((item) => (
            <div key={item.title}>
              <dt>{item.title}</dt>
              <dd>{item.text}</dd>
            </div>
          ))}
        </dl>
        <p className="help-tip">
          <ShieldCheck size={17} />
          <span>{content.tip}</span>
        </p>
      </div>
      <footer className="help-footer">
        {tutorial ? (
          <>
            <button className="help-secondary" onClick={onClose}>
              稍后再看
            </button>
            <div>
              {step > 0 && (
                <button
                  className="help-secondary"
                  onClick={() => setTopic(tour[step - 1])}
                >
                  <ArrowLeft size={15} />
                  上一步
                </button>
              )}
              {step < tour.length - 1 ? (
                <button
                  className="primary-button"
                  onClick={() => setTopic(tour[step + 1])}
                >
                  下一步
                  <ArrowRight size={15} />
                </button>
              ) : (
                <button className="primary-button" onClick={() => go("reader")}>
                  开始使用
                  <BookOpen size={16} />
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <span className="help-footer-note">模块旁的“？”可随时打开说明</span>
            <div>
              <button className="help-secondary" onClick={onClose}>
                我知道了
              </button>
              <button
                className="primary-button"
                onClick={() =>
                  go(
                    topic === "notes"
                      ? "notes"
                      : topic === "audit"
                        ? "audit"
                        : "reader",
                  )
                }
              >
                {topic === "audit"
                  ? "去版本复核"
                  : topic === "notes"
                    ? "去证据笔记"
                    : "去阅读台"}
                <ArrowRight size={15} />
              </button>
            </div>
          </>
        )}
      </footer>
    </dialog>
  );
}
