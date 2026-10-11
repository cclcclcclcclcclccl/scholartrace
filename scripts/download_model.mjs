import { mkdir, open, rename, stat } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { createHash } from 'node:crypto';

const target = 'models/Qwen3-4B-Q4_K_M.gguf';
const partial = target + '.part';
const expectedSize = 2497280256;
const expectedHash = '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5';
await mkdir('models', { recursive: true });
let completed = await stat(target).then(s => s.size).catch(() => 0);
if (completed === expectedSize) { console.log('Model file already present; verifying.'); }
else {
  let offset = await stat(partial).then(s => s.size).catch(() => 0);
  const response = await fetch('https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF/resolve/master/Qwen3-4B-Q4_K_M.gguf', {
    headers: offset ? { Range: `bytes=${offset}-` } : {}, signal: AbortSignal.timeout(20 * 60 * 1000)
  });
  if (!response.ok || !response.body) throw new Error(`Download HTTP ${response.status}`);
  if (offset && response.status !== 206) offset = 0;
  const file = await open(partial, offset ? 'a' : 'w');
  const started = Date.now(); let count = offset; let last = 0;
  console.log('Download started', response.status, 'resume_bytes', offset);
  try {
    for await (const chunk of response.body) {
      // FileHandle.write may write fewer bytes than supplied.
      let position = 0;
      while (position < chunk.byteLength) {
        const { bytesWritten } = await file.write(chunk, position, chunk.byteLength-position);
        position += bytesWritten;
      }
      count += chunk.byteLength;
      if (Date.now()-last > 30000) {
        console.log(`${(count/expectedSize*100).toFixed(1)}% ${(count/1048576).toFixed(1)} MiB, ${((count-offset)/1048576/Math.max(1,(Date.now()-started)/1000)).toFixed(2)} MiB/s`);
        last = Date.now();
      }
    }
  } finally { await file.close(); }
  if (count !== expectedSize) throw new Error(`Incomplete file: ${count} bytes`);
  completed = count;
}
const fileToVerify = await stat(target).then(() => target).catch(() => partial);
const hash = createHash('sha256');
for await (const chunk of createReadStream(fileToVerify)) hash.update(chunk);
const actualHash = hash.digest('hex');
if (actualHash !== expectedHash) throw new Error(`Model SHA256 mismatch: ${actualHash}`);
if (fileToVerify === partial) await rename(partial, target);
console.log('Verified model:', target, completed, actualHash);
