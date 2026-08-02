import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from strategy import classify,simulate
class TestStrategy(unittest.TestCase):
 def test_math(self):
  r=simulate();self.assertAlmostEqual(r['average_entry'],5529.0,delta=.1);self.assertAlmostEqual(r['profit'],2316880,delta=2)
 def test_zones(self):
  self.assertEqual(classify(5900),'1차 매수권');self.assertEqual(classify(5300,1,1),'반전 확인 후보');self.assertEqual(classify(5050,-1,-1),'손절 경보')
if __name__=='__main__':unittest.main()

