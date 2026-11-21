import socket
import threading


class RangeServer(threading.Thread):
	"""Minimal mock of a front-end/back-end chain for desync testing.

	mode "strict": honors Content-Length (not vulnerable)
	mode "cl0":    ignores Content-Length, leftover body bytes are parsed
	               as the next request on the connection (CL.0 vulnerable)
	"""

	def __init__(self, mode="strict"):
		super().__init__(daemon=True)
		self.mode = mode
		self._lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._lsock.bind(("127.0.0.1", 0))
		self._lsock.listen(8)
		self._lsock.settimeout(0.5)
		self.port = self._lsock.getsockname()[1]
		self._running = True

	def run(self):
		while self._running:
			try:
				conn, _ = self._lsock.accept()
			except socket.timeout:
				continue
			except OSError:
				break
			threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

	def stop(self):
		self._running = False
		self._lsock.close()

	def _read_headers(self, conn, buf):
		while b"\r\n\r\n" not in buf:
			data = conn.recv(8192)
			if not data:
				return None, buf
			buf += data
		head, buf = buf.split(b"\r\n\r\n", 1)
		return head, buf

	def _handle(self, conn):
		conn.settimeout(10)
		buf = b""
		try:
			while True:
				head, buf = self._read_headers(conn, buf)
				if head is None:
					return
				lines = head.split(b"\r\n")
				try:
					path = lines[0].split(b" ")[1].decode("latin-1")
				except IndexError:
					return
				cl = 0
				for line in lines[1:]:
					if line.lower().startswith(b"content-length:"):
						cl = int(line.split(b":")[1].strip())
				if self.mode == "strict":
					while len(buf) < cl:
						data = conn.recv(8192)
						if not data:
							return
						buf += data
					buf = buf[cl:]
				# mode "cl0" ignores Content-Length: body bytes stay in buf
				status = 404 if "404" in path else 200
				reason = {200: b"OK", 404: b"Not Found"}[status]
				conn.sendall(b"HTTP/1.1 %d %s\r\nContent-Length: 0\r\n\r\n" % (status, reason))
		except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError, ValueError):
			pass
		finally:
			conn.close()
