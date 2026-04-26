import socket
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from protocol import send_msg, recv_msg

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9000

class Network:
    def __init__(self):
        self.sock = None
        self.user_id = None
        self.username = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_HOST, SERVER_PORT))

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, data):
        send_msg(self.sock, data)
        return recv_msg(self.sock)

    def register(self, username, password):
        return self.send({
            "type":     "register",
            "username": username,
            "password": password
        })

    def login(self, username, password):
        response = self.send({
            "type":     "login",
            "username": username,
            "password": password
        })
        if response["status"] == "ok":
            self.user_id = response["user_id"]
            self.username = response["username"]
        return response

    def logout(self):
        return self.send({
            "type":    "logout",
            "user_id": self.user_id
        })

    def upload_video(self, filename, file_size, file_data):
        return self.send({
            "type":      "upload_video",
            "user_id":   self.user_id,
            "filename":  filename,
            "file_size": file_size,
            "file_data": file_data
        })

    def get_videos(self):
        return self.send({
            "type":    "get_videos",
            "user_id": self.user_id
        })



    def get_logs(self, video_id):
        return self.send({
            "type":     "get_logs",
            "video_id": video_id
        })

    def delete_video(self, video_id):
        return self.send({
            "type":     "delete_video",
            "user_id":  self.user_id,
            "video_id": video_id
        })