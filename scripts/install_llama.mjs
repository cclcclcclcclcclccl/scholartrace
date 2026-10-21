// Python urllib uses system proxy and verified TLS without historical caches.
import {execFileSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const venv=fileURLToPath(new URL('../.venv/Scripts/python.exe',import.meta.url));
const python=existsSync(venv)?venv:'python';
execFileSync(python,[fileURLToPath(new URL('./install_llama.py',import.meta.url))],{stdio:'inherit',windowsHide:true});
