import json,unittest
from pathlib import Path

DATA=Path(__file__).resolve().parents[1]/'data'/'investor_trends.json'

class TestInvestorTrends(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads(DATA.read_text(encoding='utf-8'))['records']

    def total(self,key,start,end='9999-12-31'):
        return sum((r.get(key) or 0) for r in self.rows if start<=r['date']<=end)

    def test_dates_are_unique_and_sorted(self):
        dates=[r['date'] for r in self.rows]
        self.assertEqual(dates,sorted(set(dates)))

    def test_anchor_totals(self):
        self.assertEqual(self.total('foreign','2026-06-19','2026-07-29'),-532491)
        self.assertEqual(self.total('individual','2026-06-19','2026-07-29'),477165)
        self.assertEqual(self.total('institution','2026-06-19','2026-07-29'),32892)
        self.assertEqual(self.total('foreign','2026-07-29'),96424)

    def test_anchor_rows(self):
        by_date={r['date']:r for r in self.rows}
        self.assertEqual(by_date['2026-06-19']['index'],9052.42)
        self.assertEqual(by_date['2026-07-29']['index'],5663.24)

if __name__=='__main__': unittest.main()
