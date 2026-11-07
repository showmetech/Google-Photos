import sys, unittest
from types import SimpleNamespace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent/'backend'))
from ui_supervisor import supervise
class RecoveryTests(unittest.TestCase):
    def check_run(self, codes):
        events=[]; delays=[]; iterator=iter(codes)
        result=supervise(['test'],events.append,lambda *a,**k:SimpleNamespace(returncode=next(iterator)),delays.append)
        return result,events,delays
    def test_clean_exit_is_not_restarted(self):
        code,events,delays=self.check_run([0]);self.assertEqual((code,len(events),delays),(0,1,[]))
    def test_crash_recovers_then_respects_exit(self):
        code,events,delays=self.check_run([1,0]);self.assertEqual((code,len(events),delays),(0,2,[2]))
    def test_repeated_crashes_open_circuit(self):
        code,events,delays=self.check_run([1]*5);self.assertEqual(code,1);self.assertEqual(events[-1]['event'],'recovery_paused');self.assertEqual(delays,[2,4,8,16])
unittest.main()
