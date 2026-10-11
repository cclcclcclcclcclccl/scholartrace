import { mkdir, writeFile } from 'node:fs/promises';
const targets = [
  ['huggingface', 'https://huggingface.co/api/models/Qwen/Qwen3-4B-GGUF'],
  ['hf-mirror', 'https://hf-mirror.com/api/models/Qwen/Qwen3-4B-GGUF'],
  ['modelscope', 'https://modelscope.cn/api/v1/models/Qwen/Qwen3-4B-GGUF/repo/files?Revision=master&Recursive=true'],
  ['llama-cpp', 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest'],
];
const results = await Promise.all(targets.map(async ([name, url]) => {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(20000), headers: { 'User-Agent': 'ScholarTrace-local-prototype' } });
    const data = await response.json();
    const result = { name, status: response.status, data };
    console.log(name, response.status, JSON.stringify(data).slice(0, 350));
    return result;
  } catch (error) { console.log(name, String(error)); return { name, error: String(error) }; }
}));
await mkdir('artifacts/environment', { recursive: true });
await writeFile('artifacts/environment/model-sources.json', JSON.stringify(results, null, 2));
