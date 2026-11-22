"""Minimal MCP client for the CADCraft command-line server. Logic adapted from the shared cc_batch tool."""
import json, os, select, subprocess
from pathlib import Path


class MCP:
    def __init__(self, binary, workdir):
        workdir = Path(workdir)
        self.err = open(workdir / 'server-stderr.log', 'w')
        self.p = subprocess.Popen(
            [str(binary), 'mcp', '--config-dir', str(workdir / 'config'),
             '--automation-read-root', '/', '--automation-write-root', str(workdir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err)
        self.n = 0
        self.rpc('initialize', {'protocolVersion': '2025-06-18', 'clientInfo': {'name': 'zev-batch', 'version': '1'}, 'capabilities': {}})

    def rpc(self, method, params, timeout=300):
        self.n += 1
        req = dict(jsonrpc='2.0', id=self.n, method=method, params=params)
        self.p.stdin.write((json.dumps(req) + '\n').encode()); self.p.stdin.flush()
        if not select.select([self.p.stdout], [], [], timeout)[0]:
            raise TimeoutError(f'{method} {params.get("name", "")}: no reply in {timeout}s')
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError('MCP server exited')
        r = json.loads(line)
        if 'error' in r:
            raise RuntimeError(json.dumps(r['error'])[:2000])
        return r['result']

    def call(self, name, **args):
        r = self.rpc('tools/call', {'name': name, 'arguments': args})
        c = r.get('content', [])
        txt = c[0].get('text') if c and c[0].get('type') == 'text' else None
        if r.get('isError'):
            raise RuntimeError((txt or json.dumps(r))[:2000])
        if txt is None:
            return r
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return txt

    def ex(self, command, **params):
        return self.call('execute', command=command, params=params)

    def close(self):
        try:
            self.p.stdin.close(); self.p.wait(timeout=20)
        except Exception:
            self.p.kill()
        self.err.close()
