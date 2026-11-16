import ipaddress,unittest
from unittest.mock import Mock,patch
import server

class NetworkTests(unittest.TestCase):
 def check(self,ip):
  handler=object.__new__(server.Handler);handler.client_address=(ip,12345);handler.reply=Mock()
  with patch.object(server,'ALLOWED_NETWORKS',[ipaddress.ip_network('127.0.0.0/8'),ipaddress.ip_network('192.168.1.0/24')],create=True):result=handler.allowed()
  return result,handler.reply
 def test_intranet_and_localhost(self):
  for ip in ['192.168.1.20','192.168.1.254','127.0.0.1']:
   result,reply=self.check(ip);self.assertTrue(result);reply.assert_not_called()
 def test_other_networks_rejected(self):
  for ip in ['192.168.2.10','10.0.0.1','8.8.8.8']:
   result,reply=self.check(ip);self.assertFalse(result);self.assertEqual(reply.call_args.args[0],403)

if __name__=='__main__':unittest.main()
