from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
CASE=Path(__file__).parents[1]/'CONC-07'
sp=importlib.util.spec_from_file_location('conc07_test_wp',CASE/'private/wellposedness.py');wp=importlib.util.module_from_spec(sp);assert sp and sp.loader;sp.loader.exec_module(wp)
class Conc07Tests(unittest.TestCase):
 def test_truth_fixture_and_gates(self):
  r=wp.gates()
  for k in ('gate1_pristine_fail','gate2_gt_seq_ab_exists','gate3_gt_seq_ba_exists','gate4_gt_naive_race_corrupts','gate5_fixture_feasible'):self.assertTrue(r[k],r)
 def test_private_visual_data_not_in_service_source(self):
  src=(CASE/'integration/service.py').read_text(encoding='utf-8')
  for v in ('1250.0','750.0','1.9','2.2','1.2','HRD-0184-2751-6309','FIN-') : self.assertNotIn(v,src)
  self.assertIn('journal_mode=DELETE',src);self.assertIn('HttpOnly',src)
 def test_prompts_are_english_and_paths_agree(self):
  for n in ('task_conc07a.py','task_conc07b.py'):
   s=(CASE/'integration'/n).read_text(encoding='utf-8');self.assertIn('/home/user/workspace',s);self.assertNotRegex(s,'[\\u4e00-\\u9fff]')
if __name__=='__main__':unittest.main()
