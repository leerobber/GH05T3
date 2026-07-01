import socket
import struct

HOST = "127.0.0.1"
PORT = 8005

UNIVERSE = {
    "Physics": 0,
    "Chemistry": 1,
    "Biology": 2,
    "Psychology": 3,
    "Fungal": 4,
    "Cosmic": 5,
    "Entropy": 6,
}

def pack_request(req_type: int, universe: int, skill: int, payload: bytes) -> bytes:
    return struct.pack("<IIII", req_type, universe, skill, len(payload)) + payload

def unpack_response(data: bytes):
    if len(data) < 8:
        raise ValueError("response too short")
    status, length = struct.unpack("<II", data[:8])
    if len(data) < 8 + length:
        raise ValueError("response truncated")
    payload = data[8:8+length]
    return status, payload

def send_bme(universe_name: str, skill_id: int, payload: bytes):
    uni = UNIVERSE.get(universe_name, 0)
    req = pack_request(1, uni, skill_id, payload)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    s.sendall(req)

    header = s.recv(8)
    if not header:
        s.close()
        raise RuntimeError("no response from router")

    status, length = struct.unpack("<II", header)
    body = b""
    while len(body) < length:
        chunk = s.recv(length - len(body))
        if not chunk:
            break
        body += chunk

    s.close()
    return status, body

if __name__ == "__main__":
    status, payload = send_bme("Cosmic", 42, b"hello-omni")
    print("status:", status)
    print("payload:", payload.decode("utf-8", errors="ignore"))
