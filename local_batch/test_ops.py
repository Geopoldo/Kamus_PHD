import json,os,signal,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import ops

class OpsTests(unittest.TestCase):
 def test_events_are_persistent_and_have_process_identity(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(ops,'ROOT',Path(tmp)):
   ops.event('test_failure',reason='controlled')
   r=json.loads((Path(tmp)/'events.jsonl').read_text());self.assertEqual(r['pid'],os.getpid());self.assertEqual(r['event'],'test_failure');self.assertIn('session',r)
 def test_watchdog_datagram(self):
  with tempfile.TemporaryDirectory() as tmp:
   address=str(Path(tmp)/'notify.sock')
   with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as receiver:
    receiver.bind(address);receiver.settimeout(2)
    with patch.dict(os.environ,NOTIFY_SOCKET=address):ops.notify('WATCHDOG=1')
    self.assertEqual(receiver.recv(1024),b'WATCHDOG=1')
 def test_signal_handler_records_and_exits(self):
  import run
  with patch.object(run,'event') as log:
   with self.assertRaises(SystemExit) as raised:run.received_signal(signal.SIGTERM,None)
   self.assertEqual(raised.exception.code,143);self.assertEqual(log.call_args.kwargs['signal'],'SIGTERM')

if __name__=='__main__':unittest.main()
