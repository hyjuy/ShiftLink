import unittest
from scripts import mes_causal_v10b as b


class CalibrationBudgetTests(unittest.TestCase):
    def test_normal_budget_precedes_fault_recall(self):
        def row(rate,hits,mult):
            return dict(params=dict(width=5,q=.995,patience=8,multiplier=mult),metrics=dict(
                pristine_normal_false_starts_per_line_hour=rate,attributable_events=hits,
                duplicate_notifications=0,attributable_within_10s=hits))
        unsafe=row(25.,12,1.);safe=row(0.,10,1.5)
        self.assertIs(b.choose([unsafe,safe]),safe)

    def test_all_methods_have_same_development_budget(self):
        self.assertEqual(len(b.GRID),32)
        self.assertEqual({p['multiplier'] for p in b.GRID},{1.,1.5,2.,3.})


if __name__=='__main__':unittest.main()
