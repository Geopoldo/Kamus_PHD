import ipaddress,unittest
import dashboard
class NetworkTests(unittest.TestCase):
 def test_intranet(self):
  old=dashboard.NETWORK
  try:
   dashboard.NETWORK=ipaddress.ip_network('192.168.1.0/24')
   for value in ['127.0.0.1','192.168.1.14','192.168.1.222']:self.assertTrue(dashboard.permitted_client(value))
   for value in ['192.168.2.10','10.0.0.1','8.8.8.8','invalid']:self.assertFalse(dashboard.permitted_client(value))
  finally:dashboard.NETWORK=old
if __name__=='__main__':unittest.main()
