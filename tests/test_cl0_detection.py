import argparse
import contextlib
import io
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, REPO_ROOT)

import smuggler
from tests.range_server import RangeServer

CL0_PAYLOAD_FILE = os.path.join(REPO_ROOT, "payloads", "http_127_0_0_1_CL0_CL0.txt")


def make_args():
	return argparse.Namespace(vhost="", timeout=2.0, quiet=False, exit_early=False)


def run_smuggler(port):
	smuggler.NOCOLOR = True
	desyncr = smuggler.Desyncr(
		"../tests/empty.py", "127.0.0.1", port,
		url="http://127.0.0.1:%d/" % port, method="POST", endpoint="/",
		SSLFlag=False, logh=None, smargs=make_args())
	buf = io.StringIO()
	with contextlib.redirect_stdout(buf):
		desyncr.run()
	return buf.getvalue()


class Cl0DetectionTest(unittest.TestCase):
	def setUp(self):
		self._argv0 = sys.argv[0]
		sys.argv[0] = os.path.join(REPO_ROOT, "smuggler.py")
		if os.path.exists(CL0_PAYLOAD_FILE):
			os.remove(CL0_PAYLOAD_FILE)
		self.server = None

	def tearDown(self):
		sys.argv[0] = self._argv0
		if self.server is not None:
			self.server.stop()
		if os.path.exists(CL0_PAYLOAD_FILE):
			os.remove(CL0_PAYLOAD_FILE)

	def start_server(self, mode):
		self.server = RangeServer(mode)
		self.server.start()
		return self.server.port

	def test_detects_cl0_desync(self):
		port = self.start_server("cl0")
		out = run_smuggler(port)
		self.assertIn("Potential CL0 Issue Found", out)
		self.assertRegex(out, r"\[CL0\]\s+: Potential CL0 Issue Found - POST @ http://127\.0\.0\.1/ - empty\.py")
		self.assertTrue(os.path.exists(CL0_PAYLOAD_FILE))
		with open(CL0_PAYLOAD_FILE) as f:
			poc = f.read()
		self.assertIn("GET /hopefully404 HTTP/1.1", poc)
		self.assertIn("Content-Length: 30", poc)

	def test_no_finding_on_strict_server(self):
		port = self.start_server("strict")
		out = run_smuggler(port)
		self.assertNotIn("Potential CL0 Issue Found", out)
		self.assertRegex(out, r"\[CL0\]\s+: OK \(CL0: \d+\.\d\d - 200\)")
		self.assertFalse(os.path.exists(CL0_PAYLOAD_FILE))


if __name__ == "__main__":
	unittest.main()
