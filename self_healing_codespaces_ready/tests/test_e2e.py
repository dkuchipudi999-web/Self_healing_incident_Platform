import json, time, unittest, urllib.request

def get(url):
 with urllib.request.urlopen(url,timeout=5) as r:return json.load(r)
class RecoveryTest(unittest.TestCase):
 def test_services_healthy(self):
  for port in [8081,8082,8083]:self.assertEqual(get(f'http://localhost:{port}/actuator/health')['status'],'UP')
 def test_order(self):
  req=urllib.request.Request('http://localhost:8081/order',data=b'{"item":"laptop","qty":1}',headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=10) as r:self.assertEqual(json.load(r)['status'],'CONFIRMED')
if __name__=='__main__':unittest.main()
