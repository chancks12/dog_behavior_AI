import socket
import threading
import json
import os
import base64
from datetime import datetime
from db import get_connection, init_db
from protocol import send_msg, recv_msg

HOST = "0.0.0.0"
PORT = 9000
AI_HOST = "127.0.0.1"
AI_PORT = 9001
UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".wmv")

# ── 업로드 폴더 초기화 ────────────────────────────────────────
def ensure_upload_dir(user_id):
    path = os.path.join(UPLOAD_DIR, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

# ── AI 서버에 분석 요청 (별도 스레드) ────────────────────────
def request_ai_analysis(video_id, filepath):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((AI_HOST, AI_PORT))

        send_msg(sock, {
            "type":     "analyze",
            "video_id": video_id,
            "filepath": filepath
        })

        response = recv_msg(sock)
        sock.close()

        conn = get_connection()
        cursor = conn.cursor()

        if response["status"] == "ok":
            now = datetime.now().isoformat()
            for log in response["logs"]:
                nearby = json.dumps(log.get("nearby_objects", []),
                                    ensure_ascii=False)
                cursor.execute("""
                               INSERT INTO logs
                               (video_id, timestamp_sec, behavior_class, confidence, nearby_objects, created_at)
                               VALUES (?, ?, ?, ?, ?, ?)
                               """, (video_id, log["timestamp_sec"],
                                     log["behavior_class"], log["confidence"], nearby, now))

            annotated_path = response.get("annotated_path", "")
            cursor.execute(
                "UPDATE videos SET status='done', annotated_path=? WHERE id=?",
                (annotated_path, video_id))
            # ↓ 이 줄 삭제
            # cursor.execute("UPDATE videos SET status='done' WHERE id=?", (video_id,))
            print(f"[AI] video_id={video_id} 분석 완료",flush=True)
        else:
            cursor.execute(
                "UPDATE videos SET status='error' WHERE id=?", (video_id,))
            print(f"[AI] video_id={video_id} 분석 실패: {response.get('message')}",flush=True)

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[AI] 연결 오류: {e}",flush=True)
        conn = get_connection()
        conn.execute("UPDATE videos SET status='error' WHERE id=?", (video_id,))
        conn.commit()
        conn.close()

# ── 요청 핸들러 ───────────────────────────────────────────────
def handle_register(cursor, data):
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return {"status": "error", "message": "아이디와 비밀번호를 입력해주세요"}
    if len(username) > 15:
        return {"status": "error", "message": "아이디는 15자 이하여야 합니다"}

    try:
        cursor.execute("""
            INSERT INTO users (username, password, created_at)
            VALUES (?, ?, ?)
        """, (username, password, datetime.now().isoformat()))
        return {"status": "ok", "message": "회원가입 성공"}
    except Exception:
        return {"status": "error", "message": "이미 사용 중인 아이디입니다"}


def handle_login(cursor, data):
    username = data.get("username", "").strip()
    password = data.get("password", "")

    cursor.execute(
        "SELECT id, username FROM users WHERE username=? AND password=?",
        (username, password)
    )
    row = cursor.fetchone()

    if row:
        return {"status": "ok", "user_id": row["id"], "username": row["username"]}
    return {"status": "error", "message": "아이디 또는 비밀번호가 틀렸습니다"}


def handle_logout(data):
    return {"status": "ok", "message": "로그아웃 되었습니다"}


def handle_upload_video(cursor, conn, data):
    user_id   = data.get("user_id")
    filename  = data.get("filename", "")
    file_size = data.get("file_size", 0)
    file_data = data.get("file_data", "")

    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        return {"status": "error", "message": "지원하지 않는 파일 형식입니다"}
    if not file_data:
        return {"status": "error", "message": "파일 데이터가 없습니다"}

    # 파일 저장
    save_dir  = ensure_upload_dir(user_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_name = f"{timestamp}_{filename}"
    filepath  = os.path.join(save_dir, save_name)

    with open(filepath, "wb") as f:
        f.write(base64.b64decode(file_data))

    # DB 저장
    cursor.execute("""
        INSERT INTO videos
            (user_id, filename, filepath, file_size, status, uploaded_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (user_id, filename, filepath, file_size, datetime.now().isoformat()))
    conn.commit()
    video_id = cursor.lastrowid

    # AI 분석 요청 (비동기 - 별도 스레드)
    cursor.execute(
        "UPDATE videos SET status='processing' WHERE id=?", (video_id,))
    conn.commit()
    threading.Thread(
        target=request_ai_analysis,
        args=(video_id, filepath),
        daemon=True
    ).start()

    return {"status": "ok", "video_id": video_id,
            "message": "업로드 완료. 분석을 시작합니다"}


def handle_get_videos(cursor, data):
    user_id = data.get("user_id")
    cursor.execute("""
        SELECT id, filename, filepath, status, annotated_path, uploaded_at
        FROM videos
        WHERE user_id=?
        ORDER BY uploaded_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    videos = [{"video_id":       r["id"],
               "filename":       r["filename"],
               "filepath":       r["filepath"],
               "status":         r["status"],
               "annotated_path": r["annotated_path"],
               "uploaded_at":    r["uploaded_at"]} for r in rows]
    return {"status": "ok", "videos": videos}


def handle_get_logs(cursor, data):
    video_id = data.get("video_id")

    cursor.execute("SELECT status FROM videos WHERE id=?", (video_id,))
    video = cursor.fetchone()

    if not video:
        return {"status": "error", "message": "존재하지 않는 영상입니다"}
    if video["status"] != "done":
        return {"status": "error", "message": "아직 분석이 완료되지 않았습니다"}

    cursor.execute("""
        SELECT id, timestamp_sec, behavior_class, confidence, nearby_objects
        FROM logs
        WHERE video_id=?
        ORDER BY timestamp_sec ASC
    """, (video_id,))
    rows = cursor.fetchall()

    logs = []
    for r in rows:
        # JSON 문자열 → 리스트로 파싱
        try:
            nearby = json.loads(r["nearby_objects"]) if r["nearby_objects"] else []
        except Exception:
            nearby = []

        logs.append({
            "log_id":         r["id"],
            "timestamp_sec":  r["timestamp_sec"],
            "behavior_class": r["behavior_class"],
            "confidence":     r["confidence"],
            "nearby_objects": nearby  # ← 파싱된 리스트로 전달
        })

    return {"status": "ok", "video_id": video_id, "logs": logs}


def handle_delete_video(cursor, conn, data):
    user_id  = data.get("user_id")
    video_id = data.get("video_id")

    # 권한 확인
    cursor.execute(
        "SELECT filepath, user_id FROM videos WHERE id=?", (video_id,))
    video = cursor.fetchone()

    if not video:
        return {"status": "error", "message": "존재하지 않는 영상입니다"}
    if video["user_id"] != user_id:
        return {"status": "error", "message": "삭제 권한이 없습니다"}

    # 파일 삭제
    if os.path.exists(video["filepath"]):
        os.remove(video["filepath"])

    # DB 삭제 (logs는 CASCADE로 자동 삭제)
    cursor.execute("DELETE FROM videos WHERE id=?", (video_id,))
    conn.commit()

    return {"status": "ok", "message": "영상 및 로그가 삭제되었습니다"}


# ── 클라이언트 연결 처리 ──────────────────────────────────────
def handle_client(client_sock, addr):
    print(f"[서버] 연결: {addr}",flush=True)
    conn = get_connection()
    cursor = conn.cursor()

    try:
        while True:
            data = recv_msg(client_sock)
            if data is None:
                break

            msg_type = data.get("type")
            print(f"[서버] 요청: {msg_type} from {addr}",flush=True)

            if   msg_type == "register":     response = handle_register(cursor, data); conn.commit()
            elif msg_type == "login":        response = handle_login(cursor, data)
            elif msg_type == "logout":       response = handle_logout(data)
            elif msg_type == "upload_video": response = handle_upload_video(cursor, conn, data)
            elif msg_type == "get_videos":   response = handle_get_videos(cursor, data)
            elif msg_type == "get_logs":     response = handle_get_logs(cursor, data)
            elif msg_type == "delete_video": response = handle_delete_video(cursor, conn, data)
            else:                            response = {"status": "error", "message": "알 수 없는 요청"}

            send_msg(client_sock, response)

    except Exception as e:
        print(f"[서버] 오류 ({addr}): {e}",flush=True)
    finally:
        conn.close()
        client_sock.close()
        print(f"[서버] 연결 종료: {addr}",flush=True)


# ── 메인 ─────────────────────────────────────────────────────
def main():
    init_db()
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(5)
    print(f"[서버] 시작 — {HOST}:{PORT}",flush=True)

    while True:
        client_sock, addr = server_sock.accept()
        threading.Thread(
            target=handle_client,
            args=(client_sock, addr),
            daemon=True
        ).start()

if __name__ == "__main__":
    main()