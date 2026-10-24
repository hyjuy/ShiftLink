"""Progressive synthetic faults: persistent episodes, public sensor-only evidence."""
import json
import subprocess
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT/'docs/data/reference/00_plant_and_relations.json'

class ProgressiveFaultTests(unittest.TestCase):
    def engine(self, nonce='progressive', **kw):
        from shiftlink.mes.progressive_factory import ProgressiveFactoryEngine
        from shiftlink.mes.configuration import from_catalog
        from shiftlink.mes.scenarios.priority import expand
        from shiftlink.mes.contracts import Run
        cfg=expand(from_catalog(json.loads(CATALOG.read_text())))
        return ProgressiveFactoryEngine(Run.create(31,datetime(2026,10,24,tzinfo=timezone.utc),cfg.config_id),cfg,run_nonce=nonce,**kw)

    def test_slow_attack_then_same_fault_until_explicit_repair(self):
        e=self.engine();e.start()
        while not e.scheduler.active:e.tick()
        first=dict(e.scheduler.active);levels=[]
        for _ in range(260):
            e.tick();self.assertEqual(e.scheduler.active['id'],first['id']);levels.append(e.scheduler.active['intensity'])
        self.assertLess(levels[0],.1);self.assertEqual(levels[-1],1)
        self.assertEqual(levels,sorted(levels))
        self.assertIsNone(e.scheduler.active['end'])
        self.assertGreaterEqual(first['start'],180)
        e.pause();e.repair_fault(first['equipment_id']);self.assertIsNone(e.scheduler.active)
        self.assertGreaterEqual(e.scheduler.next_fault-e.scheduler.clock,180)

    def test_all_mechanisms_and_sensor_coupling(self):
        from shiftlink.mes.progressive_factory import MECHANISMS
        e=self.engine();e.start();e.tick()
        options={kind:eq for eq,kind in e.scheduler.options}
        self.assertEqual(set(options),set(MECHANISMS))
        for kind,eq in options.items():
            e.scheduler.active=e.scheduler.make_fault(eq,kind,e.snapshot.sequence)
            e.scheduler.active['age']=119
            s=e.tick();values={(m.equipment_id,m.signal):m.value for m in s.measurements}
            for signal,direction in MECHANISMS[kind].items():
                spec=e.dynamics.specs[(eq,signal)]
                self.assertTrue(values[(eq,signal)]>spec.normal_max if direction>0 else values[(eq,signal)]<spec.normal_min,(kind,signal,values[(eq,signal)]))
            if kind.startswith('hydraulic') or kind=='cooling_loss':
                self.assertAlmostEqual(values[(eq,'hpu_oil_temp')],values[(eq,'hpu_cooler_oil_in_temp')],places=5)
                self.assertAlmostEqual(values[(eq,'hpu_flow')],values[(eq,'hpu_cooler_oil_flow')],places=5)
            self.assertFalse(s.active_alarms)

    def test_pause_and_non_running_equipment_do_not_advance_fault(self):
        e=self.engine();e.start()
        while not e.scheduler.active:e.tick()
        original=dict(e.scheduler.active);seq=e.snapshot.sequence
        e.pause();e.tick(200)
        self.assertEqual(seq,e.snapshot.sequence);self.assertEqual(original,e.scheduler.active)
        states=tuple(replace(x,operating_state='stopped') for x in e.snapshot.equipment)
        e.scheduler.step(seq+1,states)
        self.assertEqual(original['age'],e.scheduler.active['age'])
        self.assertEqual(e.scheduler.last_output,e.scheduler.step(seq+1,states))
        with self.assertRaises(ValueError):e.scheduler.step(seq+3,states)

    def test_seed_nonce_replay_and_reset(self):
        def collect(nonce):
            e=self.engine(nonce);e.start();e.tick(190)
            return [(m.signal,m.value) for m in e.snapshot.measurements],e.scheduler.next_fault
        self.assertEqual(collect('same'),collect('same'))
        self.assertNotEqual(collect('same'),collect('other'))
        e=self.engine();e.start();e.tick(190);old=e.run.run_id;e.reset()
        self.assertNotEqual(old,e.run.run_id);self.assertIsNone(e.scheduler.active)
        self.assertEqual(e.scheduler.clock,0)

    def test_repair_requires_pause_correct_equipment_and_does_not_clear_alarms(self):
        e=self.engine();e.start()
        while not e.scheduler.active:e.tick()
        eq=e.scheduler.active['equipment_id'];before=e.snapshot.active_alarms
        with self.assertRaises(ValueError):e.repair_fault(eq)
        with self.assertRaises(ValueError):e.set_scenario('normal')
        e.pause()
        with self.assertRaises(ValueError):e.repair_fault('unknown')
        e.repair_fault(eq);self.assertEqual(before,e.snapshot.active_alarms)
        scenario=next(iter(e._scenario_by_id))
        e.set_scenario(scenario);e.start();e.tick()
        self.assertEqual(e.snapshot.scenario_id,scenario)
        self.assertEqual(e.truth[-1]['profile']['mode'],'manual_scenario')

    def test_normal_wait_and_bad_quality_are_not_overwritten(self):
        e=self.engine();e.start();s=e.tick()
        self.assertFalse(e.scheduler.active);self.assertFalse(s.active_alarms)
        eq,kind=e.scheduler.options[0];e.scheduler.active=e.scheduler.make_fault(eq,kind,s.sequence)
        e.scheduler.active['age']=120
        signal=next(iter(e.scheduler.active['signal_targets']))
        rows=tuple(replace(m,quality='bad') if (m.equipment_id,m.signal)==(eq,signal) else m for m in s.measurements)
        over=e._overlay(rows,e.scheduler.active,s.equipment)
        original=next(m for m in rows if (m.equipment_id,m.signal)==(eq,signal))
        self.assertEqual(original,next(m for m in over if (m.equipment_id,m.signal)==(eq,signal)))
        stopped=tuple(replace(x,operating_state='stopped') for x in s.equipment)
        self.assertEqual(rows,e._overlay(rows,e.scheduler.active,stopped))

    def test_partial_configuration_excludes_incomplete_mechanisms(self):
        from shiftlink.mes.progressive_factory import ProgressiveFaultSchedule
        e=self.engine();cfg=replace(e.config,equipment=tuple(replace(x,signals=()) for x in e.config.equipment))
        scheduler=ProgressiveFaultSchedule(cfg,'empty');self.assertEqual(scheduler.options,[])
        self.assertIsNone(scheduler.step(1,()))
        with self.assertRaises(ValueError):scheduler.step(True,())

    def test_service_mode_private_truth_replay_and_repair_control(self):
        from shiftlink.mes.server import MesService
        service=MesService(CATALOG,seed=31,progressive_faults=True,run_nonce='integration')
        self.addCleanup(service.storage.close)
        service.control({'command':'start'})
        while not service.engine.scheduler.active:service.tick()
        eq=service.engine.scheduler.active['equipment_id'];run=service.engine.run.run_id
        live=service.state();self.assertEqual(len(live['measurements']),69)
        replay=service.replay(run,live['sequence']-1)['snapshots'][-1]
        self.assertEqual(live['measurements'],replay['measurements'])
        for field in ['signal_targets','intensity','next_fault','hydraulic_leak']:
            self.assertNotIn(field,json.dumps(live))
            self.assertNotIn(field,service.export(run,'jsonl'))
        self.assertTrue(service.storage.connection.execute('SELECT COUNT(*) FROM simulation_labels WHERE run_id=?',(run,)).fetchone()[0])
        self.assertEqual(service.engine.truth,[])
        service.control({'command':'pause'})
        service.control({'command':'repair_fault','equipment_id':eq})
        self.assertIsNone(service.engine.scheduler.active)
        service.control({'command':'reset'})
        self.assertEqual(type(service.engine).__name__,'ProgressiveFactoryEngine')

    def test_loopback_http_start_repair_resume_and_replay(self):
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from shiftlink.mes.server import MesService, _Handler
        service=MesService(CATALOG,seed=31,progressive_faults=True,run_nonce='http')
        handler=type('IsolatedHandler',(_Handler,),dict(service=service,web_root=ROOT/'shiftlink/mes/web',api_only=True))
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        def call(path,body=None):
            data=None if body is None else json.dumps(body).encode()
            with urlopen(Request(f'http://127.0.0.1:{server.server_port}'+path,data=data,headers={'Content-Type':'application/json'}),timeout=5) as r:return json.load(r)
        try:
            call('/api/control',{'command':'start'})
            while not service.engine.scheduler.active:service.tick()
            fault=dict(service.engine.scheduler.active)
            with self.assertRaises(HTTPError) as error:call('/api/control',{'command':'repair_fault','equipment_id':fault['equipment_id']})
            self.assertEqual(error.exception.code,400)
            self.assertEqual(fault,service.engine.scheduler.active)
            call('/api/control',{'command':'pause'})
            call('/api/control',{'command':'repair_fault','equipment_id':fault['equipment_id']})
            self.assertIsNone(service.engine.scheduler.active)
            call('/api/control',{'command':'resume'});service.tick()
            state=call('/api/state');self.assertEqual(len(state['measurements']),69)
            self.assertFalse(state['active_alarms'])
        finally:
            server.shutdown();server.server_close();thread.join();service.storage.close()
    def test_cli_opt_in_and_exclusive_flags(self):
        p=subprocess.run([sys.executable,'-m','shiftlink.mes','--help'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0);self.assertIn('--progressive-faults',p.stdout)
        p=subprocess.run([sys.executable,'-m','shiftlink.mes','--progressive-faults','--random-faults'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,2)

if __name__=='__main__':unittest.main()