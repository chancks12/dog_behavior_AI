# client/main.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox
from client.network import Network
from client.login_window import LoginWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    network = Network()
    try:
        network.connect()
    except Exception as e:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("연결 오류")
        msg.setText(f"서버에 연결할 수 없습니다\n{e}")
        msg.exec()
        sys.exit(1)

    window = LoginWindow(network)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()