import importlib.util
import unittest
from pathlib import Path

mod_path = Path(__file__).resolve().parents[1] / 'scripts' / 'update_opportunities.py'
spec = importlib.util.spec_from_file_location('collector', mod_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CollectionTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(module.parse_dates('20261101 ~ 20261215'),('2026-11-01','2026-12-15'))
        self.assertEqual(module.parse_dates('2026-11-01 ~ 2026-11-30'),('2026-11-01','2026-11-30'))
    def test_json_shape(self):
        self.assertEqual(len(module.json_items({'jsonArray':{'item':[{'title':'A'}]}})),1)
        self.assertEqual(len(module.json_items({'jsonArray':{'item':{'title':'A'}}})),1)
    def test_normalize(self):
        item = {'title':'실증 프로그램','link':'https://www.bizinfo.go.kr/a','reqstDt':'20261101 ~ 20261130','author':'가상기관','description':'<div>실증 지원</div>','seq':'PBLN_1'}
        o=module.normalize(item)
        self.assertEqual(o['deadline'],'2026-11-30')
        self.assertEqual(o['type'],'실증·PoC')
        self.assertIn('실증 지원',o['summary'])
        self.assertEqual(o['restriction'],'unverified')
    def test_dangerous_url(self):
        self.assertEqual(module.safe_url('javascript:alert(1)'), '')
    def test_no_false_eligibility(self):
        item = {'title':'청정에너지 지원사업','link':'https://example.com/a','description':'정부지원사업 참가 기업' }
        self.assertEqual(module.normalize(item)['restriction'],'unverified')

if __name__ == '__main__':
    unittest.main()
