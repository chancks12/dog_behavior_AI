# client/register_window.py
import sys
from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class RegisterWindow(QWidget):
    def __init__(self, network):
        super().__init__()
        self.network = network
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("회원가입")
        self.setFixedSize(360, 440)

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        # 타이틀
        title = QLabel("회원가입")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        sub = QLabel("아이디는 15자 이내로 입력해주세요")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Arial", 10))
        sub.setStyleSheet("color: gray;")
        layout.addWidget(sub)
        layout.addSpacing(16)

        # 아이디
        layout.addWidget(QLabel("아이디"))
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("아이디 입력 (최대 15자)")
        self.input_id.setMaxLength(15)
        self.input_id.setFixedHeight(36)
        layout.addWidget(self.input_id)

        # 비밀번호
        layout.addWidget(QLabel("비밀번호"))
        self.input_pw = QLineEdit()
        self.input_pw.setPlaceholderText("비밀번호 입력 (최소 4자)")
        self.input_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pw.setFixedHeight(36)
        layout.addWidget(self.input_pw)

        # 비밀번호 확인
        layout.addWidget(QLabel("비밀번호 확인"))
        self.input_pw2 = QLineEdit()
        self.input_pw2.setPlaceholderText("비밀번호 재입력")
        self.input_pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pw2.setFixedHeight(36)
        self.input_pw2.returnPressed.connect(self.do_register)
        layout.addWidget(self.input_pw2)

        # 오류 메시지
        self.label_error = QLabel("")
        self.label_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_error.setStyleSheet("color: red; font-size: 12px;")
        layout.addWidget(self.label_error)

        layout.addSpacing(4)

        # 가입하기 버튼
        btn_register = QPushButton("가입하기")
        btn_register.setFixedHeight(38)
        btn_register.setStyleSheet("""
            QPushButton {
                background-color: #1F4E79;
                color: white;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2E6DA4; }
            QPushButton:pressed { background-color: #163D5E; }
        """)
        btn_register.clicked.connect(self.do_register)
        layout.addWidget(btn_register)

        # 돌아가기 버튼
        btn_back = QPushButton("로그인으로 돌아가기")
        btn_back.setFixedHeight(38)
        btn_back.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #1F4E79;
                border: 1px solid #1F4E79;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #EAF0F8; }
        """)
        btn_back.clicked.connect(self.close)
        layout.addWidget(btn_back)

        layout.addStretch()
        self.setLayout(layout)

    def do_register(self):
        username = self.input_id.text().strip()
        password = self.input_pw.text()
        password2 = self.input_pw2.text()

        # 클라이언트 유효성 검사
        if not username or not password:
            self.label_error.setText("아이디와 비밀번호를 입력해주세요")
            return
        if len(username) > 15:
            self.label_error.setText("아이디는 15자 이하여야 합니다")
            return
        if len(password) < 4:
            self.label_error.setText("비밀번호는 최소 4자 이상이어야 합니다")
            return
        if password != password2:
            self.label_error.setText("비밀번호가 일치하지 않습니다")
            return

        try:
            response = self.network.register(username, password)
            if response["status"] == "ok":
                QMessageBox.information(self, "완료", "회원가입이 완료되었습니다")
                self.close()
            else:
                self.label_error.setText(response["message"])
        except Exception as e:
            QMessageBox.critical(self, "오류", f"서버 연결 실패\n{e}")