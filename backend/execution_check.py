"""Explicit planned settings and a bounded NumPy attention shape check, never training."""

import hashlib
import json
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, StrictInt, model_validator


class AttentionExecution(BaseModel):
    kind: Literal["attention_from_scratch"] = "attention_from_scratch"
    d_model: int = Field(ge=8, le=1024, strict=True)
    heads: list[StrictInt] = Field(min_length=2, max_length=8)
    training_steps: int = Field(ge=1, le=1_000_000, strict=True)
    optimizer: Literal["Adam", "AdamW", "SGD"]
    learning_rate: float = Field(gt=0, le=1)
    batch_size: int = Field(ge=1, le=4096, strict=True)
    sequence_length: int = Field(ge=2, le=32768, strict=True)
    warmup_runs: int = Field(ge=1, le=1000, strict=True)
    timing_runs: int = Field(ge=2, le=10000, strict=True)
    device: Literal["cpu", "gpu", "undecided"]
    failure_policy: Literal["retain_all_runs"] = "retain_all_runs"

    @model_validator(mode="after")
    def dimensions(self):
        if len(set(self.heads)) != len(self.heads) or any(
            type(h) is not int or h < 1 or h > 64 or self.d_model % h
            for h in self.heads
        ):
            raise ValueError("头数必须是 1—64 中不同的整数，且每个头数都整除 d_model")
        return self


def describe(spec):
    plan = AttentionExecution.model_validate(spec)
    return (
        "结构化拟议参数（尚未训练）：从零训练；"
        f"固定 d_model={plan.d_model}，h={plan.heads}，每头 d_k=d_v=d_head=d_model/h 随头数改变。"
        f"各组训练 {plan.training_steps} 步，优化器 {plan.optimizer}，学习率 {plan.learning_rate}，"
        f"批大小 {plan.batch_size}，序列长度 {plan.sequence_length}。"
        f"计时前预热 {plan.warmup_runs} 次，重复计时 {plan.timing_runs} 次，报告中位数及波动；"
        "推理模式，GPU 计时须同步。保留全部失败原因、次数及日志；不得按效果筛除有效负结果。"
        "这些参数只表示拟议设置，硬件和许可仍需实测与核对。"
    )


def attention(q, k, v):
    logits = q @ k.swapaxes(-1, -2) / np.sqrt(q.shape[-1])
    logits -= logits.max(axis=-1, keepdims=True)
    weights = np.exp(logits)
    weights /= weights.sum(axis=-1, keepdims=True)
    return weights @ v, weights


def preflight(spec, seed):
    plan = AttentionExecution.model_validate(spec)
    # Deliberately fixed small shape: this checks arithmetic/reshape feasibility,
    # not the user's full model, training, hardware budget or target latency.
    batch, length = 1, min(16, plan.sequence_length)
    rng = np.random.default_rng(seed)
    projected = rng.normal(size=(3, batch, length, plan.d_model)).astype(np.float64)
    results = []
    for heads in plan.heads:
        width = plan.d_model // heads
        q, k, v = [
            x.reshape(batch, length, heads, width).transpose(0, 2, 1, 3)
            for x in projected
        ]
        output, weights = attention(q, k, v)
        output = output.transpose(0, 2, 1, 3).reshape(batch, length, plan.d_model)
        finite = bool(np.isfinite(output).all())
        normalized = bool(np.allclose(weights.sum(axis=-1), 1, atol=1e-12))
        if not finite or not normalized:
            raise ValueError("前向数值检查失败，未保存成功结果")
        results.append(
            {
                "heads": heads,
                "d_head": width,
                "output_shape": list(output.shape),
                "finite": finite,
                "normalized_attention": normalized,
                "output_sha256": hashlib.sha256(output.tobytes()).hexdigest(),
            }
        )
    return {
        "results": results,
        "seed": seed,
        "actual_batch_size": batch,
        "actual_sequence_length": length,
        "numpy_version": np.__version__,
        "notice": "仅在本机 CPU 用固定小张量运行 NumPy 注意力计算与形状检查。未训练模型，未加载预训练权重，未测量目标模型耗时或证明效果；计划的完整批大小和序列长度未在此执行。",
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    data = data.get("content", data)
    if "protocol_snapshot" in data:
        protocol = data["protocol_snapshot"]["protocol"]
        data = {"execution": protocol["execution"], "seed": data["seed"]}
    print(
        json.dumps(
            preflight(data["execution"], data["seed"]), ensure_ascii=False, indent=2
        )
    )
