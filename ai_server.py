import socket
import threading
import cv2
import numpy as np
import os
from ultralytics import YOLO
from ultralytics.utils.plotting import Annotator, colors
from tensorflow.keras.models import load_model
from protocol import send_msg, recv_msg

IMG_W = 1280
IMG_H = 720

HOST = "0.0.0.0"
PORT = 9001

MODEL_CNN_PATH  = "models/best_model_v3.keras"
MODEL_YOLO_PATH = "models/best.pt"

CLASSES = [
    "BODYLOWER", "BODYSCRATCH", "BODYSHAKE", "FEETUP", "FOOTUP",
    "HEADING", "LYING", "MOUNTING", "SIT", "TAILING",
    "TAILLOW", "TURN", "WALKRUN"
]




KEYPOINT_MAPPING = [
    14,  # 1번  코점           ← nose
    23,  # 2번  이마점          ← forehead
    22,  # 3번  입꼬리점        ← chin (근사값)
    22,  # 4번  아래 입술점     ← chin
    21,  # 5번  목점            ← throat
     2,  # 6번  오른쪽 앞다리   ← front_left_elbow
     8,  # 7번  왼쪽 앞다리     ← front_right_elbow
     0,  # 8번  오른쪽 앞발목   ← front_left_paw
     6,  # 9번  왼쪽 앞발목     ← front_right_paw
     5,  # 10번 오른쪽 대퇴골   ← rear_left_elbow
    11,  # 11번 왼쪽 대퇴골     ← rear_right_elbow
     3,  # 12번 오른쪽 뒷발목   ← rear_left_paw
     9,  # 13번 왼쪽 뒷발목     ← rear_right_paw
    12,  # 14번 꼬리 시작점     ← tail_start
    13,  # 15번 꼬리 끝점       ← tail_end
]

KEYPOINT_DIM = 30

# ── 모델 로드 ─────────────────────────────────────────────────
print("[AI] 모델 로딩 중...")
yolo_coco_model = YOLO("yolov8n.pt")
yolo_pose_model = YOLO("dog_pose_trained.pt")
cnn_model       = load_model(MODEL_CNN_PATH)
print("[AI] 모델 로딩 완료")


# ── 위치 관계 판단 ────────────────────────────────────────────
def get_location_relation(dog_box, obj_box):
    dog_x1, dog_y1, dog_x2, dog_y2 = dog_box.xyxy[0]
    obj_x1, obj_y1, obj_x2, obj_y2 = obj_box.xyxy[0]

    dog_center_x = (dog_x1 + dog_x2) / 2
    dog_center_y = (dog_y1 + dog_y2) / 2
    obj_height   = obj_y2 - obj_y1

    if (obj_x1 <= dog_center_x <= obj_x2 and
        obj_y1 <= dog_center_y <= obj_y2):
        return "위에서"
    elif dog_center_y < obj_y1 + obj_height * 0.3:
        return "위에서"
    elif dog_center_y > obj_y2:
        return "아래에서"
    else:
        return "옆에서"


# ── 클래스 통합 매핑 ──────────────────────────────────────────
CLASS_MERGE = {
    "BODYSHAKE":   "MOTION",
    "BODYSCRATCH": "MOTION",
    "MOUNTING":    "MOTION",
    "TURN":        "MOTION",

    "FOOTUP":      "PAWUP",
    "FEETUP":      "PAWUP",
}


# ── CNN 행동 분류 ─────────────────────────────────────────────
def classify_behavior(keypoint_vec):
    vec = np.array(keypoint_vec, dtype=np.float32)
    vec = vec.reshape(1, KEYPOINT_DIM)
    pred = cnn_model.predict(vec, verbose=0)
    class_idx  = int(np.argmax(pred))
    confidence = float(np.max(pred))
    behavior   = CLASSES[class_idx]
    behavior   = CLASS_MERGE.get(behavior, behavior)
    return behavior, round(confidence, 4)


# ── 스킵 프레임용 박스 그리기 (YOLO 색상 유지) ───────────────
def draw_boxes_on_frame(frame, last_boxes):
    """
    현재 프레임 위에 지난 분석의 박스를 YOLO 색상으로 그리기
    → 영상 끊김 없이 YOLO 컬러박스 스타일 유지
    """
    annotator = Annotator(frame.copy())  # ← .plot()이 내부적으로 쓰는 클래스
    for x1, y1, x2, y2, cls_id, cls_name, conf in last_boxes:
        color = colors(cls_id, True)
        annotator.box_label(
            [x1, y1, x2, y2],
            f"{cls_name} {conf:.2f}",
            color=color
        )
    return annotator.result()


# ── 분석 메인 로직 ────────────────────────────────────────────
def analyze_video(filepath):
    os.makedirs("debug", exist_ok=True)
    cap = cv2.VideoCapture(filepath)
    fps = cap.get(cv2.CAP_PROP_FPS)

    ANALYSIS_FPS = 3
    skip_frames  = max(1, int(fps / ANALYSIS_FPS))
    print(f"[AI] 영상 fps: {fps}, 분석 간격: {skip_frames}프레임마다")

    ret, first_frame = cap.read()
    if not ret:
        return None, None

    h, w = first_frame.shape[:2]
    if h > w:
        first_frame = cv2.rotate(first_frame, cv2.ROTATE_90_CLOCKWISE)
        h, w = first_frame.shape[:2]

    filename       = os.path.basename(filepath)
    basename       = os.path.splitext(filename)[0]
    annotated_path = os.path.join("debug", f"annotated_{basename}.mp4")
    fourcc         = cv2.VideoWriter_fourcc(*"mp4v")
    out            = cv2.VideoWriter(annotated_path, fourcc, fps, (w, h))

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    logs             = []
    frame_idx        = 0
    dog_detected_any = False
    last_behavior    = None
    last_boxes       = None  # ← (x1,y1,x2,y2, cls_id, cls_name, conf) 리스트

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        if h > w:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

        # ── 스킵 프레임: 현재 프레임 위에 지난 박스 그리기 ──────
        if frame_idx % skip_frames != 0:
            if last_boxes is not None:
                out.write(draw_boxes_on_frame(frame, last_boxes))
            else:
                out.write(frame)
            frame_idx += 1
            continue

        try:
            coco_results = yolo_coco_model(frame, verbose=False)
            all_boxes    = coco_results[0].boxes

            # 강아지 박스만 필터링
            dog_boxes = [
                b for b in all_boxes
                if yolo_coco_model.names[int(b.cls)] == "dog"
            ] if all_boxes else []

            if dog_boxes:
                best_box     = max(dog_boxes, key=lambda b: float(b.conf))
                dog_detected = True
            else:
                best_box     = None
                dog_detected = False

            # 주변 객체 탐지
            nearby_objects = []
            if best_box is not None:
                for b in all_boxes:
                    cls_name = yolo_coco_model.names[int(b.cls)]
                    if cls_name != "dog":
                        relation = get_location_relation(best_box, b)
                        nearby_objects.append({
                            "object":   cls_name,
                            "relation": relation
                        })
                seen          = set()
                unique_nearby = []
                for obj in nearby_objects:
                    key = f"{obj['object']}_{obj['relation']}"
                    if key not in seen:
                        seen.add(key)
                        unique_nearby.append(obj)
                nearby_objects = unique_nearby

            if frame_idx % (skip_frames * 15) == 0:
                print(f"[AI] frame {frame_idx} — 강아지: {dog_detected}, 주변: {nearby_objects}")

            # ── last_boxes 업데이트 (cls_id 포함) ─────────────────
            last_boxes = []
            for b in all_boxes:
                x1, y1, x2, y2 = map(int, b.xyxy[0])
                cls_id   = int(b.cls)
                cls_name = yolo_coco_model.names[cls_id]
                conf     = float(b.conf)
                last_boxes.append((x1, y1, x2, y2, cls_id, cls_name, conf))

            # ── 분석 프레임: YOLO 원본 렌더링 저장 ───────────────
            annotated_frame = coco_results[0].plot()
            out.write(annotated_frame)

            if dog_detected:
                dog_detected_any = True

                x1, y1, x2, y2 = map(int, best_box.xyxy[0])
                dog_crop        = frame[y1:y2, x1:x2]

                pose_results = yolo_pose_model(dog_crop, verbose=False)

                if pose_results[0].keypoints is not None:
                    kps = pose_results[0].keypoints.xy.cpu().numpy()
                    if len(kps) > 0:
                        kp_24 = kps[0]

                        vec = []
                        for idx in KEYPOINT_MAPPING:
                            if idx < len(kp_24):
                                x = (float(kp_24[idx][0]) + x1) / IMG_W
                                y = (float(kp_24[idx][1]) + y1) / IMG_H
                                vec.append(x)
                                vec.append(y)
                            else:
                                vec.extend([0.0, 0.0])

                        vec = [0.0 if (v != v) else v for v in vec]
                        behavior, confidence = classify_behavior(vec)

                        if behavior != last_behavior and confidence >= 0.6:
                            logs.append({
                                "timestamp_sec":  round(frame_idx / fps, 2),
                                "behavior_class": behavior,
                                "confidence":     confidence,
                                "nearby_objects": nearby_objects
                            })
                            last_behavior = behavior

        except Exception as e:
            print(f"[AI] frame {frame_idx} 오류: {e}")
            import traceback
            traceback.print_exc()

        frame_idx += 1

    cap.release()
    out.release()

    if not dog_detected_any:
        return None, None

    return logs, annotated_path


# ── 클라이언트(서버) 요청 처리 ───────────────────────────────
def handle_server(client_sock, addr):
    print(f"[AI] 연결: {addr}")
    try:
        data = recv_msg(client_sock)
        if data is None:
            return

        msg_type = data.get("type")
        video_id = data.get("video_id")
        filepath = data.get("filepath")

        if msg_type != "analyze":
            send_msg(client_sock, {
                "status": "error", "message": "알 수 없는 요청"})
            return

        print(f"[AI] 분석 시작 — video_id={video_id}, filepath={filepath}")
        logs, annotated_path = analyze_video(filepath)

        if logs is None:
            send_msg(client_sock, {
                "status":   "error",
                "video_id": video_id,
                "message":  "강아지를 탐지할 수 없습니다"
            })
        else:
            send_msg(client_sock, {
                "status":         "ok",
                "video_id":       video_id,
                "logs":           logs,
                "annotated_path": annotated_path
            })
            print(f"[AI] 분석 완료 — video_id={video_id}, 로그 {len(logs)}개")

    except Exception as e:
        print(f"[AI] 오류: {e}")
        send_msg(client_sock, {
            "status": "error", "message": str(e)})
    finally:
        client_sock.close()


# ── 메인 ─────────────────────────────────────────────────────
def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(5)
    print(f"[AI] 시작 — {HOST}:{PORT}")

    while True:
        client_sock, addr = server_sock.accept()
        threading.Thread(
            target=handle_server,
            args=(client_sock, addr),
            daemon=True
        ).start()

if __name__ == "__main__":
    main()