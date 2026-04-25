# client/main_window.py
import os
import base64
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTabWidget,
    QListWidget, QListWidgetItem, QSplitter,
    QFileDialog, QMessageBox, QProgressBar,  QSlider
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget

ALLOWED_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".wmv")

BEHAVIOR_LABEL = {
    # 현재 사용 중인 클래스
    "SIT":       "앉아있음",
    "LYING":     "엎드려있음",
    "WALKRUN":   "돌아다니는 중",
    "TAILING":   "꼬리 올리기",
    "TAILLOW":   "꼬리 내리기",
    "BODYLOWER": "몸 낮추기",
    "HEADING":   "고개 움직임",
    "PAWUP":     "앞발 들기",
    "MOTION":    "몸 움직임",

    #  통합된 클래스 (이전 로그 호환용)
    # "FOOTUP":      "앞발 들기",    → PAWUP으로 통합
    # "FEETUP":      "두 앞발 들기", → PAWUP으로 통합
    # "BODYSHAKE":   "몸 털기",      → MOTION으로 통합
    # "BODYSCRATCH": "몸 긁는 중",   → MOTION으로 통합
    # "MOUNTING":    "올라타기",     → MOTION으로 통합
    # "TURN":        "제자리 회전",  → MOTION으로 통합
}

OBJECT_LABEL = {
    "couch":   "소파",
    "bed":     "침대",
    "chair":   "의자",
    "table":   "테이블",
    "person":  "사람",
    "bowl":    "밥그릇",
    "tv":      "TV",
    "cat":     "고양이",
    "bottle":  "물병",
    "door":    "문",
    "laptop":  "노트북",
    "remote":  "리모컨",
}

def format_log_message(behavior_class, nearby_objects):
    behavior = BEHAVIOR_LABEL.get(behavior_class, behavior_class)

    location = ""
    for obj in nearby_objects:
        obj_name = OBJECT_LABEL.get(obj["object"], obj["object"])
        relation = obj["relation"]
        location = f"{obj_name} {relation}"
        break

    if location:
        return f"{location} {behavior}"
    return behavior
# ── 업로드 워커 (별도 스레드) ─────────────────────────────────
class UploadWorker(QThread):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, network, filename, file_size, file_data):
        super().__init__()
        self.network   = network
        self.filename  = filename
        self.file_size = file_size
        self.file_data = file_data

    def run(self):
        try:
            response = self.network.upload_video(
                self.filename, self.file_size, self.file_data)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


# ── 메인 윈도우 ───────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.current_video_id = None
        self.upload_worker    = None
        self.init_ui()
        self.load_videos()

    def init_ui(self):
        self.setWindowTitle("강아지 행동 인식 AI")
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 상단 바 ──
        topbar = QWidget()
        topbar.setFixedHeight(48)
        topbar.setStyleSheet("background-color: #1F4E79;")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 0, 16, 0)

        lbl_user = QLabel(f"안녕하세요,  {self.network.username}  님")
        lbl_user.setStyleSheet("color: white; font-size: 13px;")
        topbar_layout.addWidget(lbl_user)
        topbar_layout.addStretch()

        btn_logout = QPushButton("로그아웃")
        btn_logout.setFixedSize(80, 30)
        btn_logout.setStyleSheet("""
            QPushButton {
                color: white;
                border: 1px solid white;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2E6DA4; }
        """)
        btn_logout.clicked.connect(self.do_logout)
        topbar_layout.addWidget(btn_logout)
        root.addWidget(topbar)

        # ── 탭 ──
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { height: 36px; min-width: 120px; font-size: 13px; }")
        self.tabs.addTab(self.build_upload_tab(),  "영상 업로드")
        self.tabs.addTab(self.build_log_tab(),     "로그 확인")
        self.tabs.addTab(self.build_delete_tab(),  "영상 삭제")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        root.addWidget(self.tabs)

    # ── 탭 1: 영상 업로드 ─────────────────────────────────────
    def build_upload_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(12)

        # 파일 선택 영역
        zone = QWidget()
        zone.setFixedHeight(100)
        zone.setStyleSheet("""
            border: 2px dashed #AAAAAA;
            border-radius: 8px;
            background-color: #F8F8F8;
        """)
        zone_layout = QVBoxLayout(zone)
        zone_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_zone = QLabel("mp4, mov, avi, mkv, wmv 파일을 선택해주세요")
        lbl_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_zone.setStyleSheet("border: none; color: gray; font-size: 13px;")
        zone_layout.addWidget(lbl_zone)

        btn_select = QPushButton("파일 선택")
        btn_select.setFixedSize(100, 32)
        btn_select.setStyleSheet("border: 1px solid #AAAAAA; border-radius: 4px; background: white;")
        btn_select.clicked.connect(self.select_file)
        zone_layout.addWidget(btn_select, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(zone)

        # 선택된 파일 정보
        self.lbl_file_info = QLabel("선택된 파일 없음")
        self.lbl_file_info.setStyleSheet("color: #444; font-size: 13px;")
        layout.addWidget(self.lbl_file_info)

        # 업로드 버튼 + 상태
        btn_row = QHBoxLayout()
        self.btn_upload = QPushButton("업로드 시작")
        self.btn_upload.setFixedSize(120, 38)
        self.btn_upload.setEnabled(False)
        self.btn_upload.setStyleSheet("""
            QPushButton {
                background-color: #1F4E79;
                color: white;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:disabled { background-color: #AAAAAA; }
            QPushButton:hover:!disabled { background-color: #2E6DA4; }
        """)
        self.btn_upload.clicked.connect(self.do_upload)
        btn_row.addWidget(self.btn_upload)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #E07B00; font-size: 12px;")
        btn_row.addWidget(self.lbl_status)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        self.selected_filepath = None
        return widget

    # ── 탭 2: 로그 확인 ──────────────────────────────────────
    def build_log_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 좌측 패널 (30%)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 6, 12)
        left_layout.setSpacing(8)

        lbl_videos = QLabel("내 영상 목록")
        lbl_videos.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(lbl_videos)

        self.list_videos = QListWidget()
        self.list_videos.setStyleSheet("font-size: 12px;")
        self.list_videos.itemClicked.connect(self.on_video_selected)
        left_layout.addWidget(self.list_videos)

        lbl_logs = QLabel("행동 로그")
        lbl_logs.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        left_layout.addWidget(lbl_logs)

        self.list_logs = QListWidget()
        self.list_logs.setStyleSheet("font-size: 12px;")
        self.list_logs.itemClicked.connect(self.on_log_selected)
        left_layout.addWidget(self.list_logs)

        splitter.addWidget(left)

        # 우측 패널 (70%) — 영상 재생
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 4, 12, 4)  # 여백 줄이기
        right_layout.setSpacing(4)  # 간격 줄이기

        # 영상 위젯 (stretch로 최대한 크게)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        right_layout.addWidget(self.video_widget, stretch=1)  # ← stretch=1 추가

        # 미디어 플레이어
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)

        # 슬라이더
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.on_slider_moved)
        right_layout.addWidget(self.slider)

        # 시간 + 컨트롤 버튼 한 줄로
        bottom_layout = QHBoxLayout()

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("font-size: 11px; color: gray;")
        bottom_layout.addWidget(self.lbl_time)

        bottom_layout.addStretch()

        btn_play = QPushButton("재생")
        btn_play.setFixedSize(60, 28)
        btn_play.clicked.connect(self.media_player.play)
        bottom_layout.addWidget(btn_play)

        btn_pause = QPushButton("일시정지")
        btn_pause.setFixedSize(80, 28)
        btn_pause.clicked.connect(self.media_player.pause)
        bottom_layout.addWidget(btn_pause)

        btn_stop = QPushButton("정지")
        btn_stop.setFixedSize(60, 28)
        btn_stop.clicked.connect(self.media_player.stop)
        bottom_layout.addWidget(btn_stop)

        right_layout.addLayout(bottom_layout)

        splitter.addWidget(right)
        splitter.setSizes([270, 630])

        layout.addWidget(splitter)
        return widget

    # ── 탭 3: 영상 삭제 ──────────────────────────────────────
    def build_delete_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(8)

        lbl = QLabel("업로드한 영상 목록")
        lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(lbl)

        self.list_delete = QListWidget()
        self.list_delete.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.list_delete)

        btn_delete = QPushButton("선택 영상 삭제")
        btn_delete.setFixedSize(130, 38)
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #C0392B;
                color: white;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #E74C3C; }
        """)
        btn_delete.clicked.connect(self.do_delete)
        layout.addWidget(btn_delete)
        return widget

    # ── 영상 목록 로드 ────────────────────────────────────────
    def load_videos(self):
        try:
            response = self.network.get_videos()
            if response["status"] != "ok":
                return

            videos = response["videos"]

            # 탭2 영상 목록
            self.list_videos.clear()
            for v in videos:
                status_text = {
                    "pending":    "대기중",
                    "processing": "분석중",
                    "done":       "완료",
                    "error":      "오류"
                }.get(v["status"], v["status"])
                item = QListWidgetItem(f"{v['filename']}  [{status_text}]")
                item.setData(Qt.ItemDataRole.UserRole, v)
                self.list_videos.addItem(item)

            # 탭3 삭제 목록
            self.list_delete.clear()
            for v in videos:
                item = QListWidgetItem(
                    f"{v['filename']}  |  {v['uploaded_at'][:10]}")
                item.setData(Qt.ItemDataRole.UserRole, v)
                self.list_delete.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "오류", f"영상 목록 로드 실패\n{e}")

    # ── 파일 선택 ─────────────────────────────────────────────
    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "영상 파일 선택", "",
            "영상 파일 (*.mp4 *.mov *.avi *.mkv *.wmv)"
        )
        if not path:
            return

        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            QMessageBox.warning(self, "오류", "지원하지 않는 파일 형식입니다")
            return

        size_mb = os.path.getsize(path) / (1024 * 1024)
        self.lbl_file_info.setText(f"{filename}  ({size_mb:.1f} MB)")
        self.selected_filepath = path
        self.btn_upload.setEnabled(True)

    # ── 업로드 ───────────────────────────────────────────────
    def do_upload(self):
        if not self.selected_filepath:
            return

        self.btn_upload.setEnabled(False)
        self.lbl_status.setText("업로드 중...")

        filename  = os.path.basename(self.selected_filepath)
        file_size = os.path.getsize(self.selected_filepath)

        with open(self.selected_filepath, "rb") as f:
            file_data = base64.b64encode(f.read()).decode("utf-8")

        self.upload_worker = UploadWorker(
            self.network, filename, file_size, file_data)
        self.upload_worker.finished.connect(self.on_upload_finished)
        self.upload_worker.error.connect(self.on_upload_error)
        self.upload_worker.start()

    def on_upload_finished(self, response):
        if response["status"] == "ok":
            self.lbl_status.setText("분석 중... (AI 서버 처리 중)")
            self.load_videos()
        else:
            self.lbl_status.setText(f"오류: {response['message']}")
            self.btn_upload.setEnabled(True)

    def on_upload_error(self, msg):
        self.lbl_status.setText(f"오류: {msg}")
        self.btn_upload.setEnabled(True)

    # ── 영상 선택 (로그 탭) ───────────────────────────────────
    def on_video_selected(self, item):
        video = item.data(Qt.ItemDataRole.UserRole)
        self.current_video_id = video["video_id"]

        # 영상 즉시 로드 (로그 클릭 전에도 재생 가능)
        annotated = video.get("annotated_path", "")
        filepath = annotated if annotated and os.path.exists(annotated) else video.get("filepath", "")

        if filepath and os.path.exists(filepath):
            self.media_player.setSource(QUrl.fromLocalFile(os.path.abspath(filepath)))
            self.media_player.play()

        if video["status"] != "done":
            self.list_logs.clear()
            self.list_logs.addItem("아직 분석이 완료되지 않았습니다")
            return

        try:
            response = self.network.get_logs(self.current_video_id)
            self.list_logs.clear()

            if response["status"] != "ok":
                self.list_logs.addItem(response["message"])
                return

            for log in response["logs"]:
                ts = log["timestamp_sec"]
                cls = log["behavior_class"]
                conf = int(log["confidence"] * 100)
                nearby = log.get("nearby_objects", [])
                m = int(ts // 60)
                s = ts % 60

                message = format_log_message(cls, nearby)
                item = QListWidgetItem(f"{m:02d}:{s:05.2f}  {message}  {conf}%")
                item.setData(Qt.ItemDataRole.UserRole, log)
                self.list_logs.addItem(item)

        except Exception as e:
            QMessageBox.critical(self, "오류", f"로그 로드 실패\n{e}")

    # ── 로그 클릭 → 영상 해당 시점 재생 ─────────────────────
    def on_log_selected(self, item):
        log = item.data(Qt.ItemDataRole.UserRole)
        if not log:
            return

        selected = self.list_videos.currentItem()
        if not selected:
            return

        video = selected.data(Qt.ItemDataRole.UserRole)
        annotated = video.get("annotated_path", "")
        filepath = annotated if annotated and os.path.exists(annotated) else video.get("filepath")

        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "오류", "영상 파일을 찾을 수 없습니다")
            return

        timestamp_ms = int(log["timestamp_sec"] * 1000)
        self.media_player.setSource(QUrl.fromLocalFile(os.path.abspath(filepath)))
        self.media_player.setPosition(timestamp_ms)
        self.media_player.play()


    # ── 영상 삭제 ─────────────────────────────────────────────
    def do_delete(self):
        selected = self.list_delete.currentItem()
        if not selected:
            QMessageBox.warning(self, "알림", "삭제할 영상을 선택해주세요")
            return

        video = selected.data(Qt.ItemDataRole.UserRole)
        if not video:
            return

        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{video['filename']}' 을 삭제하시겠습니까?\n로그도 함께 삭제됩니다",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            response = self.network.delete_video(video["video_id"])
            if response["status"] == "ok":
                QMessageBox.information(self, "완료", "삭제되었습니다")
                self.load_videos()
            else:
                QMessageBox.warning(self, "오류", response["message"])
        except Exception as e:
            QMessageBox.critical(self, "오류", f"삭제 실패\n{e}")

    # ── 탭 전환 시 목록 갱신 ─────────────────────────────────
    def on_tab_changed(self, index):
        if index in (1, 2):  # 로그 확인, 영상 삭제 탭
            self.load_videos()

    def on_slider_moved(self, position):
        self.media_player.setPosition(position)

    def on_position_changed(self, position):
        self.slider.setValue(position)
        total = self.media_player.duration()
        cur_s = position // 1000
        tot_s = total // 1000
        self.lbl_time.setText(
            f"{cur_s // 60:02d}:{cur_s % 60:02d} / {tot_s // 60:02d}:{tot_s % 60:02d}"
        )

    def on_duration_changed(self, duration):
        self.slider.setRange(0, duration)
    # ── 로그아웃 ─────────────────────────────────────────────
    def do_logout(self):
        try:
            self.network.logout()
        except Exception:
            pass
        self.media_player.stop()
        from client.login_window import LoginWindow
        self.login_win = LoginWindow(self.network)
        self.login_win.show()
        self.close()