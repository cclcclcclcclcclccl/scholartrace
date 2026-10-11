import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const releases = JSON.parse(await readFile('artifacts/environment/llama-releases.json', 'utf8'));
const release = releases.find(r => r.assets?.some(a => /bin-win-vulkan-x64\.zip$/.test(a.name)));
const asset = release.assets.find(a => /bin-win-vulkan-x64\.zip$/.test(a.name));
await mkdir('tools/downloads', { recursive: true });
let bytes;
for (const source of [asset.browser_download_url, asset.url, asset.browser_download_url]) {
  try {
    const response = await fetch(source, { signal: AbortSignal.timeout(180000), headers: { 'User-Agent': 'ScholarTrace', Accept: 'application/octet-stream' } });
    console.log('Runtime response', response.status, response.headers.get('content-type'));
    if (!response.ok || response.headers.get('content-type')?.includes('json')) throw new Error(`Runtime HTTP ${response.status} is not binary`);
    bytes = Buffer.from(await response.arrayBuffer());
    break;
  } catch (error) { console.log('Download retry:', String(error)); }
}
if (!bytes) throw new Error('Unable to download verified official runtime');
if (bytes.length !== asset.size) throw new Error('Runtime download size mismatch');
const digest = createHash('sha256').update(bytes).digest('hex');
if (asset.digest?.startsWith('sha256:') && asset.digest !== `sha256:${digest}`) throw new Error('Runtime SHA256 mismatch');
await writeFile('tools/downloads/llama-vulkan.zip', bytes);
await writeFile('artifacts/environment/llama-runtime.json', JSON.stringify({ release: release.tag_name, asset: asset.name, source: asset.browser_download_url, sha256: digest, publisher_digest: asset.digest }, null, 2));
console.log('Verified runtime', release.tag_name, bytes.length, digest);
for (const name of ['LICENSE', 'README.md']) {
  const result = await fetch(`https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF/resolve/master/${name}`, { signal: AbortSignal.timeout(20000) });
  if (!result.ok) throw new Error(`Model ${name}: ${result.status}`);
  await mkdir('models', { recursive: true });
  await writeFile(`models/Qwen3-4B-${name}`, await result.text());
}
