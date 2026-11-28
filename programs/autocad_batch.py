"""Drive AutoCAD LT in an interactive guest session, one locked batch at a time."""
import base64
import fcntl
import json
import subprocess
import time
from pathlib import Path, PureWindowsPath
from programs.settings import SETTINGS

TRANSFER = Path(SETTINGS.get('autocad_transfer', '/srv/vm-transfer/autocad'))
WINDOWS = SETTINGS.get('autocad_transfer_windows', 'Z:\\')
DOMAIN = SETTINGS.get('autocad_domain', 'autocad')
USER = SETTINGS.get('autocad_user', 'bmas')


def win(path):
    rel = Path(path).resolve().relative_to(TRANSFER.resolve())
    return str(PureWindowsPath(WINDOWS, *rel.parts)).replace('\\', '/')


def quote(value):
    return '"' + str(value).replace('\\', '/').replace('"', '\\"') + '"'


def helpers(log):
    return [
        f'(defun acb-log (lst / f s) (setq f (open {quote(log)} "a") s (car lst)) (foreach x (cdr lst) (setq s (strcat s "\\t" x))) (write-line s f) (close f))',
        '(defun acb-check (expect) (setq acb-ok (= (strcase (getvar "DWGNAME")) (strcase expect))) (if acb-ok (acb-log (list "OPEN-OK" expect)) (acb-log (list "OPEN-ERR" expect (getvar "DWGNAME")))))',
        '(defun acb-save (expect out args) (if acb-ok (progn (if (findfile out) (vl-file-delete out)) (apply \'command (append (list "_.SAVEAS") args (list out))) (acb-log (list (if (findfile out) "SAVE-OK" "SAVE-MISSING") expect out))) (acb-log (list "SAVE-SKIP" expect out))))']


def script(tasks, log, logdir):
    lines = ['FILEDIA', '0', 'CMDDIA', '0', 'SDI', '1', '(setvar "LOGFILEPATH" ' + quote(win(logdir)) + ')', 'LOGFILEON']
    h = helpers(win(log))
    for source, outputs in tasks:
        name = Path(source).name
        lines += h + [f'(acb-log (list "START" {quote(name)}))', 'OPEN', win(source).replace('/', '\\')] + h
        lines += [f'(acb-check {quote(name)})']
        for output, spec in outputs:
            fmt, version, encoding = spec
            args = [version] if fmt == 'DWG' else ['DXF', 'Version', version, 'Binary' if encoding == 'binary' else '']
            lines.append(f'(acb-save {quote(name)} {quote(win(output))} \'(' + ' '.join(map(quote, args)) + '))')
    lines += h + ['(acb-log (list "END"))', 'QUIT', 'N']
    return '\r\n'.join(lines) + '\r\n'


def reason(source, logdir):
    stem = Path(source).stem
    for path in sorted(Path(logdir).glob(stem + '*.log')):
        suffix = path.stem[len(stem):]
        if suffix and stem[-1:].isdigit() and suffix[0].isdigit(): continue
        data = path.read_bytes()
        encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-16-le' if b'\x00' in data[:100] else 'utf-8')
        lines = data.decode(encoding, errors='replace').splitlines()
        for index, line in enumerate(lines):
            lowered = line.lower()
            if not line.lstrip().startswith('[') and ('error' in lowered or 'invalid' in lowered):
                selected = []
                for part in lines[index:index + 4]:
                    selected.append(part.strip())
                    if 'discarded' in part.lower(): break
                return ' '.join(selected).strip()[:300]
    return 'AutoCAD refused to open'


def parse_log(log, tasks, logdir):
    names = {Path(src).name: src for src, _ in tasks}
    outputs = {win(out).lower(): out for _, outs in tasks for out, _ in outs}
    result = {}; current = None
    if not Path(log).exists(): return result
    for line in Path(log).read_text(errors='replace').splitlines():
        parts = line.split('\t'); event = parts[0]
        if event == 'START' and len(parts) > 1 and parts[1] in names:
            current = names[parts[1]]; result[current] = {'open': None, 'saves': {}, 'hang': False}
        elif current and event == 'OPEN-OK': result[current]['open'] = 'ok'
        elif current and event == 'OPEN-ERR': result[current]['open'] = 'err:' + reason(current, logdir)
        elif current and event in ('SAVE-OK', 'SAVE-MISSING', 'SAVE-SKIP') and len(parts) > 2:
            out = outputs.get(parts[2].replace('\\', '/').lower())
            if out is not None: result[current]['saves'][out] = 'OK' if event == 'SAVE-OK' else event
        elif event == 'END': current = None
    return result


def agent(payload):
    proc = subprocess.run(['virsh', '-c', 'qemu:///session', 'qemu-agent-command', DOMAIN, json.dumps(payload), '--timeout', '30'], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)['return']


def powershell(command):
    encoded = base64.b64encode(command.encode('utf-16-le')).decode()
    return agent({'execute': 'guest-exec', 'arguments': {'path': 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe', 'arg': ['-NoProfile', '-EncodedCommand', encoded], 'capture-output': True}})['pid']


def status(pid):
    return agent({'execute': 'guest-exec-status', 'arguments': {'pid': pid}})


def run_batch(tasks, work, tag='acb'):
    work = Path(work); work.mkdir(parents=True, exist_ok=True); TRANSFER.mkdir(parents=True, exist_ok=True)
    all_results = {}; todo = list(tasks); chunk = int(SETTINGS.get('autocad_chunk', 40)); stall = float(SETTINGS.get('autocad_stall_seconds', 120))
    if chunk < 1 or stall <= 0: raise ValueError('Invalid AutoCAD batch settings')
    with (TRANSFER / '.autocad.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        while todo:
            batch, todo = todo[:chunk], todo[chunk:]
            log = work / (tag + '.log'); log.unlink(missing_ok=True)
            scr = work / (tag + '.scr'); scr.write_bytes(script(batch, log, work).encode('utf-8'))
            ps = "$e=(Get-ChildItem 'C:\\Program Files\\Autodesk\\AutoCAD LT 2027' -Filter acadlt.exe | Select-Object -First 1).FullName; "
            ps += "$a=New-ScheduledTaskAction -Execute $e -Argument '/b \"" + win(scr) + "\"'; "
            ps += "$p=New-ScheduledTaskPrincipal -UserId '" + USER.replace("'", "''") + "' -LogonType Interactive; "
            ps += "Register-ScheduledTask -TaskName acadrun -Action $a -Principal $p -Force | Out-Null; Start-ScheduledTask -TaskName acadrun; Start-Sleep 5; while (Get-Process acadlt -ErrorAction SilentlyContinue) { Start-Sleep 2 }; Unregister-ScheduledTask -TaskName acadrun -Confirm:$false"
            pid = powershell(ps); last_lines = 0; last = time.monotonic()
            while True:
                lines = log.read_bytes().count(b'\n') if log.exists() else 0
                if lines != last_lines: last_lines = lines; last = time.monotonic()
                state = status(pid)
                if state.get('exited') or time.monotonic() - last >= stall: break
                time.sleep(1)
            parsed = parse_log(log, batch, work); all_results.update(parsed)
            unfinished = [(src, outs) for src, outs in batch if src not in parsed or not ((parsed[src]['open'] or '').startswith('err:') or (parsed[src]['open'] == 'ok' and all(out in parsed[src]['saves'] for out, _ in outs)))]
            if unfinished:
                stop_pid = powershell('Stop-Process -Name acadlt -Force -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName acadrun -Confirm:$false -ErrorAction SilentlyContinue')
                deadline = time.monotonic() + 30
                while not status(stop_pid).get('exited'):
                    if time.monotonic() >= deadline: raise TimeoutError('AutoCAD stop command timed out')
                    time.sleep(1)
                while not status(pid).get('exited'):
                    if time.monotonic() >= deadline: raise TimeoutError('AutoCAD launcher did not exit')
                    time.sleep(1)
                src = unfinished[0][0]; all_results.setdefault(src, {'open': None, 'saves': {}, 'hang': False})['hang'] = True
                todo = unfinished[1:] + todo
                for pattern in ('*.dwl', '*.dwl2'):
                    for path in work.rglob(pattern): path.unlink(missing_ok=True)
    return all_results
