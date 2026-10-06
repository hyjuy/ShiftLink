"""Synthetic 4.8 metre equipment travel must follow its speed signal."""
import math
import unittest
from shiftlink.mes.contracts import Configuration, EquipmentConfig, Run, SignalSpec
from shiftlink.mes.engine import MesEngine


class FactoryTransportTests(unittest.TestCase):
    def engine(self, speed):
        eq=EquipmentConfig("EQ-01", "ASSET-01", "RT-01", "Roller", "SG-01", "rt", ("transport",),
                           (SignalSpec("rt_speed", "Speed", "m_min", speed, speed),))
        config=Configuration("test", "v1", "test", "LN-01", (eq,), (), (eq.equipment_id,), ())
        engine=MesEngine(Run.create(seed=1), config)
        engine.start()
        return engine

    def test_speed_sets_distance(self):
        engine=self.engine(30)
        old=engine.snapshot.coils[0]["position"]
        snapshot=engine.tick()
        self.assertAlmostEqual(snapshot.coils[0]["position"]-old, engine.run.tick_seconds*.5/4.8, places=5)

    def test_zero_negative_and_nonfinite_speed_do_not_move(self):
        for speed in (0, -1, math.nan, math.inf):
            with self.subTest(speed=speed):
                engine=self.engine(speed)
                old=engine.snapshot.coils[0]["position"]
                self.assertEqual(engine.tick().coils[0]["position"],old)

    def test_pause_preserves_position(self):
        engine=self.engine(30)
        engine.pause()
        self.assertEqual(engine.tick().coils,engine.snapshot.coils)


if __name__=="__main__":
    unittest.main()
