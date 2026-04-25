# client/login_window.py
import sys
from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class LoginWindow(QWidget):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.main_window = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("강아지 행동 인식 AI")
        self.setFixedSize(360, 400)

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        # 타이틀
        title = QLabel("강아지 행동 인식 AI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        sub = QLabel("로그인")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Arial", 11))
        layout.addWidget(sub)
        layout.addSpacing(16)

        # 아이디
        layout.addWidget(QLabel("아이디"))
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("아이디 입력")
        self.input_id.setMaxLength(15)
        self.input_id.setFixedHeight(36)
        layout.addWidget(self.input_id)

        # 비밀번호
        layout.addWidget(QLabel("비밀번호"))
        self.input_pw = QLineEdit()
        self.input_pw.setPlaceholderText("비밀번호 입력")
        self.input_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pw.setFixedHeight(36)
        self.input_pw.returnPressed.connect(self.do_login)
        layout.addWidget(self.input_pw)

        # 오류 메시지
        self.label_error = QLabel("")
        self.label_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_error.setStyleSheet("color: red; font-size: 12px;")
        layout.addWidget(self.label_error)

        layout.addSpacing(4)

        # 로그인 버튼
        btn_login = QPushButton("로그인")
        btn_login.setFixedHeight(38)
        btn_login.setStyleSheet("""
            QPushButton {
                background-color: #1F4E79;
                color: white;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2E6DA4; }
            QPushButton:pressed { background-color: #163D5E; }
        """)
        btn_login.clicked.connect(self.do_login)
        layout.addWidget(btn_login)

        # 회원가입 버튼
        btn_register = QPushButton("회원가입")
        btn_register.setFixedHeight(38)
        btn_register.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #1F4E79;
                border: 1px solid #1F4E79;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #EAF0F8; }
        """)
        btn_register.clicked.connect(self.open_register)
        layout.addWidget(btn_register)

        layout.addStretch()
        self.setLayout(layout)

    def do_login(self):
        username = self.input_id.text().strip()
        password = self.input_pw.text()

        # 1차 클라이언트 유효성 검사
        if not username or not password:
            self.label_error.setText("아이디와 비밀번호를 입력해주세요")
            return

        try:
            response = self.network.login(username, password)
            if response["status"] == "ok":
                self.label_error.setText("")
                self.open_main()
            else:
                self.label_error.setText(response["message"])
        except Exception as e:
            QMessageBox.critical(self, "오류", f"서버 연결 실패\n{e}")

    def open_register(self):
        from client.register_window import RegisterWindow
        self.register_win = RegisterWindow(self.network)
        self.register_win.show()

    def open_main(self):
        from client.main_window import MainWindow
        self.main_window = MainWindow(self.network)
        self.main_window.show()
        self.close()