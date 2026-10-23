"""Transactional Pi rollout, preserving the current PDA and all MES data.

The release manifest pins both the new files and expected deployed PDA files.
Run check mode first; --apply changes only this worker unit and the four listed
PDA files. --rollback restores the backup and never touches the MES service.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.request import urlopen

APP=Path('/home/pi/shiftlink/app')
UNIT='shiftlink-analytics.service'
UNIT_PATH=Path('/etc/systemd/system')/UNIT
DATA=Path('/home/pi/shiftlink/analytics')
TARGETS=('shiftlink/pda/__main__.py','shiftlink/pda/ai_insights.py','shiftlink/mes/web/pda.js','shiftlink/mes/web/pda.html')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT).strip()


def get(path):
    with urlopen('http://127.0.0.1:8080'+path,timeout=10) as response:
        body=response.read()
        return json.loads(body) if path.startswith('/api/') else body


def pda_pid():
    matches=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:args=(path/'cmdline').read_bytes().split(b'\0')
        except OSError:continue
        if any(a==b'-m' and b==b'shiftlink.pda' for a,b in zip(args,args[1:])):matches.append(int(path.name))
    if len(matches)!=1:raise RuntimeError('exactly one existing PDA process required')
    return matches[0]


def replace(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.analytics-new')
    shutil.copy2(source,temporary);temporary.replace(target)


def restart_pda():
    old_pid=pda_pid()
    get('/pda/restart')
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        time.sleep(1)
        try:
            new_pid=pda_pid()
            if new_pid==old_pid:continue
            get('/api/state');return new_pid
        except (OSError,ValueError,RuntimeError):pass
    raise RuntimeError('PDA did not return after restart')


def restore(backup):
    record=json.loads((backup/'record.json').read_text())
    subprocess.run(['sudo','-n','systemctl','disable','--now',UNIT],capture_output=True)
    for rel in TARGETS:
        target=APP/rel
        if rel in record['present']:replace(backup/'files'/rel,target)
        elif target.exists():target.unlink()
    if record['unit_present']:
        command('sudo','-n','install','-m','0644',str(backup/'previous.service'),str(UNIT_PATH))
    else:
        command('sudo','-n','rm','-f','--',str(UNIT_PATH))
    command('sudo','-n','systemctl','daemon-reload')
    if record['unit_enabled']:command('sudo','-n','systemctl','enable',UNIT)
    if record['unit_active']:command('sudo','-n','systemctl','start',UNIT)
    try:restart_pda()
    except (OSError,ValueError,RuntimeError):
        try:pda_pid()
        except RuntimeError:
            launch=record['launch']
            log=APP.parent/'logs/pda.log';log.parent.mkdir(exist_ok=True)
            with log.open('ab') as output:
                subprocess.Popen(launch['argv'],cwd=APP,env=dict(os.environ,**launch['environment']),
                                 stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            time.sleep(3);get('/api/state')
        else:raise RuntimeError('PDA still running but unhealthy; do not launch a duplicate')
    return dict(restored=True,files={rel:sha(APP/rel)==value for rel,value in record['present'].items()},pda_pid=pda_pid())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--rollback',type=Path);args=p.parse_args()
    if args.rollback:
        print(json.dumps(restore(args.rollback),indent=2),flush=True);return
    release=args.release.resolve()
    if not release.is_relative_to((DATA/'releases').resolve()):raise ValueError('release outside analytics directory')
    manifest=json.loads((release/'release-manifest.json').read_text())
    for rel,value in manifest['files'].items():
        path=(release/rel).resolve()
        if not path.is_relative_to(release) or sha(path)!=value:raise ValueError('release file hash mismatch: '+rel)
    for rel,value in manifest['expected_live'].items():
        target=APP/rel
        if (sha(target) if target.exists() else None)!=value:raise ValueError('deployed file changed since capture: '+rel)
    unit=release/'shiftlink-analytics.service'
    unit.write_text((release/'deploy/analytics/shiftlink-analytics.service.in').read_text().replace('@RELEASE@',str(release)))
    command('systemd-analyze','verify',str(unit))
    state=get('/api/state');old_pid=pda_pid()
    plan=dict(release=str(release),state={k:state[k] for k in ('run_id','sequence','line_mode')},pda_pid=old_pid,files=list(TARGETS),mes_service_changed=False)
    print('PLAN',json.dumps(plan),flush=True)
    if not args.apply:return
    command('sudo','-n','true')
    backup=DATA/'backups'/time.strftime('%Y%m%d-%H%M%S');backup.mkdir(parents=True,exist_ok=False)
    present={}
    for rel in TARGETS:
        target=APP/rel
        if target.exists():
            path=backup/'files'/rel;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,path);present[rel]=sha(target)
    unit_present=UNIT_PATH.exists()
    if unit_present:shutil.copy2(UNIT_PATH,backup/'previous.service')
    argv=[x.decode() for x in Path(f'/proc/{old_pid}/cmdline').read_bytes().split(b'\0') if x]
    allowed={'DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','WAYLAND_DISPLAY'}
    environment={}
    for entry in Path(f'/proc/{old_pid}/environ').read_bytes().split(b'\0'):
        key,_,value=entry.partition(b'=')
        if key.decode() in allowed:environment[key.decode()]=value.decode()
    record=dict(present=present,unit_present=unit_present,launch=dict(argv=argv,environment=environment),
        unit_enabled=subprocess.run(['systemctl','is-enabled',UNIT],capture_output=True).returncode==0,
        unit_active=subprocess.run(['systemctl','is-active',UNIT],capture_output=True).returncode==0,old_pid=old_pid,plan=plan)
    (backup/'record.json').write_text(json.dumps(record,indent=2));(backup/'before-state.json').write_text(json.dumps(state))
    try:
        for rel in TARGETS:
            source=release/('device-pda.html' if rel.endswith('pda.html') else rel)
            replace(source,APP/rel)
        command('sudo','-n','install','-m','0644',str(unit),str(UNIT_PATH))
        command('sudo','-n','systemctl','daemon-reload');command('sudo','-n','systemctl','enable','--now',UNIT)
        print('WORKER_STARTED',flush=True)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            time.sleep(1)
            latest=Path('/run/shiftlink-analytics/latest.json')
            if latest.exists():
                value=json.loads(latest.read_text())
                if value['status'] not in ('model_error','unavailable'):break
            if subprocess.run(['systemctl','is-active','--quiet',UNIT]).returncode!=0:raise RuntimeError('worker exited before readiness')
        else:raise RuntimeError('worker produced no valid source result')
        new_pid=restart_pda()
        print('PDA_RESTARTED',new_pid,flush=True)
        for _ in range(10):
            time.sleep(1);state=get('/api/state')
            if state.get('ai_insights',{}).get('status') not in (None,'disabled','unavailable','model_error','stale'):break
        else:raise RuntimeError('PDA advisory overlay not healthy')
        result=dict(deployed=True,backup=str(backup),old_pda_pid=old_pid,new_pda_pid=new_pid,
            service_active=command('systemctl','is-active',UNIT),service_enabled=command('systemctl','is-enabled',UNIT),
            source={k:state[k] for k in ('run_id','sequence','line_mode')},ai=state['ai_insights'],
            files={rel:sha(APP/rel) for rel in TARGETS},mes_service_changed=False)
        (backup/'deployment-result.json').write_text(json.dumps(result,indent=2));print('DEPLOYED',json.dumps(result),flush=True)
    except BaseException:
        print('ROLLING_BACK',str(backup),flush=True)
        try:print(json.dumps(restore(backup)),flush=True)
        except Exception as error:print('ROLLBACK_REQUIRES_RECOVERY',type(error).__name__,flush=True)
        raise


if __name__=='__main__':main()
