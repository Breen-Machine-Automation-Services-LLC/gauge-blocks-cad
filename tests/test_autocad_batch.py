from pathlib import Path
from programs import autocad_batch as batch
from programs.adapters import AutoCad


def test_script_and_log(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, 'TRANSFER', tmp_path)
    source = str(tmp_path / 'i0.dxf')
    outs = [(str(tmp_path / ('o' + str(n) + '.' + fmt.lower())), (fmt, version, enc)) for n, (fmt, version, enc) in enumerate([('DXF','R12','ASCII'), ('DXF','2018','binary'), ('DWG','2000','binary')])]
    text = batch.script([(source, outs)], tmp_path/'events.log', tmp_path)
    assert text.count('(defun acb-check') == 3
    assert '(setq acb-ok (= (strcase (getvar "DWGNAME")) (strcase expect)))' in text
    assert '(defun acb-save (expect out args) (if acb-ok ' in text
    assert "'(" + '"DXF" "Version" "R12" ""' + ')' in text
    assert "'(" + '"DXF" "Version" "2018" "Binary"' + ')' in text
    assert "'(" + '"2000"' + ')' in text
    assert '\n' not in text.replace('\r\n','')
    log=tmp_path/'events.log'
    log.write_text('START\ti0.dxf\nOPEN-OK\ti0.dxf\nSAVE-OK\ti0.dxf\t'+batch.win(outs[0][0])+'\nSAVE-MISSING\ti0.dxf\t'+batch.win(outs[1][0])+'\nSAVE-SKIP\ti0.dxf\t'+batch.win(outs[2][0])+'\nEND\n')
    row=batch.parse_log(log,[(source,outs)],tmp_path)[source]
    assert row['open']=='ok' and list(row['saves'].values())==['OK','SAVE-MISSING','SAVE-SKIP']
    (tmp_path/'i0.log').write_text('Error: invalid drawing\n')
    log.write_text('START\ti0.dxf\nOPEN-ERR\ti0.dxf\tDrawing1.dwg\nEND\n')
    assert batch.parse_log(log,[(source,outs)],tmp_path)[source]['open']=='err:Error: invalid drawing'
    (tmp_path/'i0.log').write_text('Error: UTF-16 failure\n', encoding='utf-16')
    assert batch.parse_log(log,[(source,outs)],tmp_path)[source]['open']=='err:Error: UTF-16 failure'


def test_multiple_saves_and_multiline_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, 'TRANSFER', tmp_path)
    source = str(tmp_path / 'i0.dxf')
    outputs = [(str(tmp_path / 'o0.dxf'), ('DXF', '2018', 'ASCII')),
               (str(tmp_path / 'o1.dwg'), ('DWG', '2018', 'binary'))]
    tasks = [(source, outputs)]
    log = tmp_path / 'events.log'
    log.write_text('START\ti0.dxf\nOPEN-OK\ti0.dxf\n' + ''.join(
        'SAVE-OK\ti0.dxf\t' + batch.win(out) + '\n' for out, _ in outputs) + 'END\n')
    assert batch.parse_log(log, tasks, tmp_path)[source]['saves'] == {
        out: 'OK' for out, _ in outputs}

    (tmp_path / 'i0.log').write_text(
        'The following error was encountered while reading\n'
        'in HATCH starting at line 5072: Error: expected group code 47\n'
        'Invalid or incomplete DXF input -- drawing discarded.\n'
        'This line must not be included.\n')
    log.write_text('START\ti0.dxf\nOPEN-ERR\ti0.dxf\tDrawing1.dwg\nEND\n')
    reason = batch.parse_log(log, tasks, tmp_path)[source]['open']
    assert 'expected group code 47' in reason and 'drawing discarded' in reason
    assert 'This line' not in reason

    (tmp_path/'i0.log').write_bytes(
        b'[ AutoCAD LT - Sat Nov 28 01:15:58 2026  ]----------------------------------------\r\n'
        b'Invalid anonymous block *D1 on line 1224.\r\n'
        b'Invalid or incomplete DXF input -- drawing discarded.\r\n')
    expected = ('Invalid anonymous block *D1 on line 1224. '
                'Invalid or incomplete DXF input -- drawing discarded.')
    assert batch.reason(source, tmp_path) == expected
    assert batch.parse_log(log, tasks, tmp_path)[source]['open'] == 'err:' + expected


def test_adapter_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(batch,'TRANSFER',tmp_path)
    sources=[]; jobs=[]
    for i in range(4):
        src=tmp_path/f's{i}.dxf';src.write_text('input');sources.append(src)
        jobs.append((src,tmp_path/f'd{i}.dxf','DXF','2018','ASCII'))
    def fake(tasks, work, tag):
        result={}
        for i,(src,outs) in enumerate(tasks):
            out=outs[0][0]
            if i==0: Path(out).write_text('output')
            result[src]={'open': 'err:bad' if i==1 else 'ok','hang':i==2,'saves':{out:'OK' if i==0 else 'SAVE-MISSING'}}
        return result
    monkeypatch.setattr(batch,'run_batch',fake)
    monkeypatch.setattr('programs.adapters.privacy.assert_clean',lambda p: None)
    results=AutoCad().save_many(jobs)
    assert results[jobs[0][1]] is None
    assert 'refused to open: bad' in results[jobs[1][1]]
    assert 'hung' in results[jobs[2][1]]
    assert 'save failed' in results[jobs[3][1]]


def test_resume_after_early_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, 'TRANSFER', tmp_path)
    monkeypatch.setattr(batch, 'SETTINGS', {'autocad_chunk': 2, 'autocad_stall_seconds': 1})
    first=str(tmp_path/'i0.dxf'); second=str(tmp_path/'i1.dxf')
    tasks=[(first, [(str(tmp_path/'o0.dxf'),('DXF','2018','ASCII'))]), (second, [(str(tmp_path/'o1.dxf'),('DXF','2018','ASCII'))])]
    launches=[]
    def fake(command):
        if command.startswith('Stop-Process'): return 0
        launches.append(command)
        if len(launches)==1:
            (tmp_path/'run.log').write_text('START\ti0.dxf\n')
        else:
            (tmp_path/'run.log').write_text('START\ti1.dxf\nOPEN-OK\ti1.dxf\nSAVE-OK\ti1.dxf\t'+batch.win(tasks[1][1][0][0])+'\nEND\n')
        return len(launches)
    monkeypatch.setattr(batch,'powershell',fake)
    monkeypatch.setattr(batch,'status',lambda pid: {'exited':True})
    result=batch.run_batch(tasks,tmp_path,'run')
    assert result[first]['hang'] and result[second]['open']=='ok'
    assert len(launches)==2


def test_every_format_version_and_encoding(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, 'TRANSFER', tmp_path)
    versions=('R12','2000','2004','2007','2010','2013','2018')
    outputs=[]
    for version in versions:
        for encoding in ('ASCII','binary'):
            outputs.append((str(tmp_path/f'{version}-{encoding}.dxf'),('DXF',version,encoding)))
        if version!='R12': outputs.append((str(tmp_path/f'{version}.dwg'),('DWG',version,'binary')))
    text=batch.script([(str(tmp_path/'i.dxf'),outputs)],tmp_path/'events.log',tmp_path)
    for out,(fmt,version,encoding) in outputs:
        args=f'"{version}"' if fmt=='DWG' else f'"DXF" "Version" "{version}" "'+('Binary' if encoding=='binary' else '')+'"'
        assert f'(acb-save "i.dxf" "{batch.win(out)}" \'({args}))' in text


def test_stall_stops_session_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, 'TRANSFER', tmp_path)
    monkeypatch.setattr(batch, 'SETTINGS', {'autocad_chunk': 2, 'autocad_stall_seconds': 1})
    tasks=[(str(tmp_path/f'i{i}.dxf'),[(str(tmp_path/f'o{i}.dxf'),('DXF','2018','ASCII'))]) for i in range(2)]
    launches=[]; stops=[]; ticks=iter(range(100))
    def fake(command):
        if command.startswith('Stop-Process'):
            stops.append(command); return 99
        launches.append(command)
        if len(launches)==1: (tmp_path/'run.log').write_text('START\ti0.dxf\n')
        else: (tmp_path/'run.log').write_text('START\ti1.dxf\nOPEN-OK\ti1.dxf\nSAVE-OK\ti1.dxf\t'+batch.win(tasks[1][1][0][0])+'\nEND\n')
        return len(launches)
    monkeypatch.setattr(batch,'powershell',fake)
    monkeypatch.setattr(batch,'status',lambda pid: {'exited':pid!=1 or bool(stops)})
    monkeypatch.setattr(batch.time,'monotonic',lambda: next(ticks))
    monkeypatch.setattr(batch.time,'sleep',lambda n: None)
    result=batch.run_batch(tasks,tmp_path,'run')
    assert result[tasks[0][0]]['hang'] and result[tasks[1][0]]['open']=='ok'
    assert len(stops)==1 and len(launches)==2
