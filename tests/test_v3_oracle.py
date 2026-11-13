from pathlib import Path
import json, sqlite3, tempfile, unittest
from evaluation_examples.task_class.pg_v3_oracle import checks
from build_v3 import build
class TestCommunityPantryV3(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();build(self.tmp.name)
  self.expected=json.load(open(Path(self.tmp.name)/"expected.json",encoding="utf-8"))
  c=sqlite3.connect(Path(self.tmp.name)/"seed.db");c.row_factory=sqlite3.Row
  self.rows=[dict(r) for r in c.execute("SELECT * FROM volunteers ORDER BY id")];c.close()
 def full_joint_state(self):
  by={r["id"]:r for r in self.rows}
  for w in self.expected["shift"]["rows"]:
   by[w["id"]].update(shift_station=w["station"],shift_window=w["window"],shift_status=w["status"])
  for w in self.expected["mileage"]["rows"]:
   by[w["id"]].update(claim_amount=w["amount"],claim_status=w["decision"],claim_note=w["note"])
  return {"volunteers":list(by.values())}
 def test_initial_seed_is_readable_but_not_complete(self):
  s={"volunteers":self.rows}
  a,sa=checks(s,self.expected,"shift");b,sb=checks(s,self.expected,"mileage")
  self.assertTrue(a["state_readable"] and b["state_readable"]);self.assertEqual(sa,0.0);self.assertEqual(sb,0.0)
 def test_both_tasks_have_a_common_joint_pass_state(self):
  s=self.full_joint_state()
  a,sa=checks(s,self.expected,"shift");b,sb=checks(s,self.expected,"mileage")
  self.assertEqual(sa,1.0);self.assertEqual(sb,1.0)
 def test_wrong_selected_volunteer_does_not_count_as_correct_assignment(self):
  s=self.full_joint_state();s["volunteers"][0]["shift_station"]="Produce"
  a,score=checks(s,self.expected,"shift")
  self.assertEqual(score,5/6);self.assertFalse(a["V-214_shift_exact"])
 def test_wrong_panel_or_stale_form_is_not_rewarded(self):
  s=self.full_joint_state();s["volunteers"][0]["claim_amount"]=4.36
  s["volunteers"][0]["claim_status"]="APPROVED";s["volunteers"][0]["claim_note"]="Verified from signed slip."
  s["volunteers"][0]["shift_station"]="";s["volunteers"][0]["shift_window"]="";s["volunteers"][0]["shift_status"]=""
  a,sa=checks(s,self.expected,"shift");b,sb=checks(s,self.expected,"mileage")
  self.assertEqual(sa,5/6);self.assertEqual(sb,1.0)
 def test_missing_own_domain_outputs_fail(self):
  s=self.full_joint_state();s["volunteers"][4]["claim_amount"]=None;s["volunteers"][4]["claim_status"]=""
  _,score=checks(s,self.expected,"mileage");self.assertEqual(score,5/6)
if __name__=="__main__":unittest.main()
