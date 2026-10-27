import unittest
from hold_report import hold_report

class HoldReportTests(unittest.TestCase):
    def test_local_hold_does_not_global_stop_and_states_preserved(self):
        rows=[{'id':'u','state':'UNKNOWN','scope':['A'],'global_stop':False},
              {'id':'h','state':'HOLD','scope':['B'],'global_stop':False},
              {'id':'c','state':'CONFLICT','scope':['C'],'global_stop':False},
              {'id':'o','state':'OPEN','scope':['D'],'global_stop':False},
              {'id':'z','state':'CLOSED','scope':['E'],'global_stop':True}]
        result=hold_report(rows)
        self.assertEqual(result['counts'],{'HOLD':1,'UNKNOWN':1,'CONFLICT':1,'OPEN':1,'CLOSED':1})
        self.assertEqual([r['id'] for r in result['open_items']],['c','h','o','u'])
        self.assertEqual([r['state'] for r in result['open_items']],['CONFLICT','HOLD','OPEN','UNKNOWN'])
        self.assertFalse(result['global_stop'])
        self.assertEqual(result['open_items'][0]['scope'],['C'])

    def test_explicit_open_global_stop(self):
        self.assertTrue(hold_report([{'id':'g','state':'HOLD','scope':['A'],'global_stop':True}])['global_stop'])

    def test_invalid_state_is_rejected(self):
        with self.assertRaises(ValueError):
            hold_report([{'id':'x','state':'PASS','scope':['A'],'global_stop':False}])

    def test_empty(self):
        self.assertEqual(hold_report([]),{'counts':{'HOLD':0,'UNKNOWN':0,'CONFLICT':0,'OPEN':0,'CLOSED':0},'open_items':[],'global_stop':False})

if __name__=='__main__':unittest.main(verbosity=2)
