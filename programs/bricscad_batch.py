"""Run BricsCAD batch open-and-save tasks, in chunks, surviving hangs.

BricsCAD is launched only through the shared locked wrapper bcad_run.sh (one BricsCAD at a time across every agent).
The wrapper runs inside a mount namespace whose passwd file maps the login to the fictional name ZEV_OPERATOR, so the
program records that name instead of the machine account (see programs/CAPABILITIES.md). No code is injected into
BricsCAD. Logic adapted from the shared bc_batch tool; nothing outside the repository is imported.
"""
import os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

from programs.settings import SETTINGS

HERE = Path(__file__).resolve().parent
WRAPPER = SETTINGS['bricscad_wrapper']
REAPER = SETTINGS['xvfb_reaper']
CRASH_DIR = Path(SETTINGS['crash_dir'])
LSP = HERE / 'bricscad_batch.lsp'
AUTHOR = 'ZEV_OPERATOR'


def parse_log(log):
    """Return {infile: {'open': None|'ok'|'err:..', 'saves': {out: 'OK'|message}, 'hang': bool}}."""
    res, cur = {}, None
    if not log.exists():
        return res
    for ln in log.read_text(errors='replace').splitlines():
        p = ln.split('\t')
        if p[0] == 'START':
            cur = p[2]; res[cur] = {'open': None, 'saves': {}, 'hang': False}
        elif cur and p[0] == 'OPEN-OK':
            res[cur]['open'] = 'ok'
        elif cur and p[0] == 'OPEN-ERR':
            res[cur]['open'] = 'err:' + (p[3] if len(p) > 3 else '')
        elif cur and p[0] in ('SAVE-OK', 'SAVE-ERR', 'SAVE-MISSING'):
            res[cur]['saves'][p[2]] = 'OK' if p[0] == 'SAVE-OK' else (p[0] + ' ' + (p[3] if len(p) > 3 else ''))
        elif p[0] == 'HANG' and p[1] in res:
            res[p[1]]['hang'] = True
    return res


def _finished(st, outs):
    return bool(st) and (st['hang'] or (st['open'] or '').startswith('err') or (st['open'] == 'ok' and all(o in st['saves'] for o in outs)))


def fictional_passwd(path):
    """Write a passwd file in which the current user's login and full name are the fictional author."""
    lines = []
    for ln in Path('/etc/passwd').read_text().splitlines():
        f = ln.split(':')
        if len(f) >= 7 and f[2] == str(os.getuid()):
            f[0] = AUTHOR; f[4] = AUTHOR
        lines.append(':'.join(f))
    Path(path).write_text('\n'.join(lines) + '\n')


def shield_prefix(passwd):
    """Mount namespace that (1) maps the login to the fictional author and (2) hides the user font folder.
    DWG 2004 and later record the full path of a text style's font file; a font installed under the home folder
    would write the login name into the drawing, so BricsCAD sees an empty folder there and falls back to a system font."""
    prefix = ['bwrap', '--die-with-parent', '--dev-bind', '/', '/', '--ro-bind', str(passwd), '/etc/passwd']
    fonts = Path.home() / '.local/share/fonts'
    if fonts.is_dir():
        prefix += ['--tmpfs', str(fonts)]
    return prefix


def command(tag_scr, pfx, passwd, shield=True):
    prefix = shield_prefix(passwd) if shield else []
    return prefix + ['bash', WRAPPER, '3000', pfx, str(tag_scr)]


def run_batch(tasks, workdir, tag='bcb', chunk=40, stall=150, shield=True):
    """tasks: list of (infile, [(outfile, spec), ...]). Returns the parsed log for all tasks."""
    workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)
    log = workdir / (tag + '.log')
    todo = [t for t in tasks]
    outs_of = {t[0]: [o for o, _ in t[1]] for t in tasks}
    cwd = Path(tempfile.mkdtemp(prefix='bcad-cwd-'))   # a timed-out session writes crash_report.txt here, outside the repo
    fails = 0
    try:
        while True:
            d = parse_log(log)
            todo = [t for t in todo if not _finished(d.get(t[0]), outs_of[t[0]])]
            if not todo:
                break
            batch, todo = todo[:chunk], todo[chunk:]
            lst = workdir / (tag + '.list.txt')
            lst.write_text(''.join(inf + '|' + '|'.join(o + '|' + s for o, s in outs) + '\n' for inf, outs in batch))
            scr = workdir / (tag + '.scr')
            scr.write_text('(setvar "FILEDIA" 0)\n(setvar "PROXYNOTICE" 0)\n'
                           f'(load "{LSP}")\n(bcb-run "{lst}" "{log}")\n_.QUIT _Y\n')
            pfx = str(workdir / (tag + '.run'))
            t0 = time.time()
            fictional_passwd(workdir / 'passwd')
            proc = subprocess.Popen(command(scr, pfx, workdir / 'passwd', shield), cwd=str(cwd), start_new_session=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            last = (-1, time.time()); bc_seen = False; killed = False
            while proc.poll() is None:
                time.sleep(5)
                sz = log.stat().st_size if log.exists() else 0
                if sz != last[0]:
                    last = (sz, time.time())
                elif time.time() - last[1] > stall and (sz > 0 or time.time() - last[1] > stall * 2):
                    # A wait for the shared lock also shows as no log growth: kill only when BricsCAD is running for us.
                    if subprocess.run(['pgrep', '-f', f'bricscad .*{tag}.scr'], capture_output=True).stdout.strip():
                        if bc_seen:
                            os.killpg(proc.pid, signal.SIGKILL); killed = True; break
                        bc_seen = True
                    last = (sz, time.time())
            out = proc.stdout.read().decode(errors='replace') if proc.stdout else ''
            subprocess.run(['bash', REAPER], capture_output=True)
            d = parse_log(log)
            unfinished = [t for t in batch if not _finished(d.get(t[0]), outs_of[t[0]])]
            if unfinished:
                first = unfinished[0][0]
                if first in d and (d[first]['open'] is None or d[first]['open'] == 'ok'):
                    with open(log, 'a') as f:
                        f.write(f'HANG\t{first}\n')
                    unfinished = unfinished[1:]; fails = 0
                else:
                    fails += 1
                    if fails >= 3:
                        raise RuntimeError('BricsCAD did not start the tasks three times in a row: ' + out[-300:])
                todo = unfinished + todo
            else:
                fails = 0
            print(f'  bricscad chunk of {len(batch)} tasks, {int(time.time() - t0)} s, killed={killed}', flush=True)
            for crash in cwd.glob('crash_report*.txt'):
                CRASH_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(crash), str(CRASH_DIR / f'crash_report_phase2b_{tag}_{int(time.time())}.txt'))
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    return parse_log(log)


def run_script(script_text, workdir, tag='gen', timeout=900):
    """Run one BricsCAD script (a new empty drawing) in the fictional-login namespace; returns the exit status."""
    workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)
    scr = workdir / (tag + '.scr'); scr.write_text(script_text)
    fictional_passwd(workdir / 'passwd')
    cwd = Path(tempfile.mkdtemp(prefix='bcad-cwd-'))
    command_line = shield_prefix(workdir / 'passwd') + [
                    'bash', WRAPPER, str(timeout), str(workdir / (tag + '.run')), str(scr)]
    try:
        for attempt in range(3):   # a random display number can collide with another session's: the Qt platform plugin then fails to start
            r = subprocess.run(command_line, cwd=str(cwd), capture_output=True, text=True)
            subprocess.run(['bash', REAPER], capture_output=True)
            if r.returncode == 0 or r.returncode == 124:
                break
            time.sleep(5)
        for crash in cwd.glob('crash_report*.txt'):
            CRASH_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(crash), str(CRASH_DIR / f'crash_report_phase2b_{tag}_{int(time.time())}.txt'))
        return r.returncode
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
