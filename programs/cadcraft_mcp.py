"""Minimal MCP client for the CADCraft command-line server. Logic adapted from the shared cc_batch tool."""
import json, os, select, subprocess
from pathlib import Path


class HarnessError(RuntimeError):
    """The server could not be driven."""


def launch_options(binary, workdir):
    try:
        result = subprocess.run([str(binary), 'mcp', '--help'], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as ex:
        raise HarnessError(f'MCP help probe failed: {ex}') from ex
    help_text = result.stdout + result.stderr
    options = []
    for option, value in (('--config-dir', str(Path(workdir) / 'config')),
                          ('--automation-read-root', '/'), ('--automation-write-root', str(workdir))):
        if option in help_text:
            options.extend([option, value])
    return options


class MCP:
    def __init__(self, binary, workdir):
        workdir = Path(workdir)
        self.err = open(workdir / 'server-stderr.log', 'w')
        self.launch_options = launch_options(binary, workdir)
        try:
            self.p = subprocess.Popen(
                [str(binary), 'mcp', *self.launch_options],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err)
        except OSError as ex:
            self.err.close()
            raise HarnessError(f'MCP server failed to start: {ex}') from ex
        self.n = 0
        try:
            self.rpc('initialize', {'protocolVersion': '2025-06-18', 'clientInfo': {'name': 'zev-batch', 'version': '1'}, 'capabilities': {}})
        except Exception as ex:
            self.close()
            raise HarnessError(f'MCP server failed to start: {ex}') from ex

    def rpc(self, method, params, timeout=300):
        self.n += 1
        req = dict(jsonrpc='2.0', id=self.n, method=method, params=params)
        try:
            self.p.stdin.write((json.dumps(req) + '\n').encode()); self.p.stdin.flush()
        except (BrokenPipeError, OSError) as ex:
            raise HarnessError(f'MCP server communication failed: {ex}') from ex
        if not select.select([self.p.stdout], [], [], timeout)[0]:
            raise HarnessError(f'{method} {params.get("name", "")}: no reply in {timeout}s')
        line = self.p.stdout.readline()
        if not line:
            raise HarnessError('MCP server exited')
        try:
            r = json.loads(line)
        except (ValueError, UnicodeError) as ex:
            raise HarnessError(f'MCP server returned invalid JSON: {ex}') from ex
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
