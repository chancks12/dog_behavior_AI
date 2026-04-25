# protocol.py
# 클라이언트-서버 공통 통신 규약

import json
import struct

HEADER_SIZE = 4  # 메시지 길이를 4바이트로 표현

def send_msg(sock, data: dict):
    """
    dict → JSON → 바이트 전송
    앞 4바이트: 메시지 길이
    이후: JSON 데이터
    """
    msg   = json.dumps(data, ensure_ascii=False).encode("utf-8")
    # '>I' = big-endian unsigned int (4바이트)
    header = struct.pack(">I", len(msg))
    sock.sendall(header + msg)


def recv_msg(sock) -> dict:
    """
    4바이트 헤더 읽기 → 메시지 길이 파악 → 전체 수신
    """
    # 1단계: 헤더 수신
    header = _recv_exact(sock, HEADER_SIZE)
    if not header:
        return None
    msg_len = struct.unpack(">I", header)[0]

    # 2단계: 본문 수신
    msg = _recv_exact(sock, msg_len)
    if not msg:
        return None

    return json.loads(msg.decode("utf-8"))


def _recv_exact(sock, n: int) -> bytes:
    """
    정확히 n바이트를 수신할 때까지 반복
    TCP는 한 번에 다 안 올 수 있어서 필요함 (C++ Reactor 패턴이랑 같은 이유)
    """
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf