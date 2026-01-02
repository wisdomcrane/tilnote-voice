"""
음성 인식 앱 - 시스템 트레이 버전
Ctrl+Win 누르면 녹음 시작, 다시 누르면 중지 후 클립보드에 복사
"""

import threading
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav
from faster_whisper import WhisperModel
import tempfile
import os
import sys
import pyperclip
import keyboard
import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image, ImageDraw, ImageTk
import socket

LOCK_PORT = 47777

def check_already_running():
    """이미 실행 중인지 확인 (포트 바인딩 방식)"""
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        return lock_socket  # 소켓 유지
    except socket.error:
        return None

def signal_existing_instance():
    """이미 실행 중인 인스턴스에 창 열기 신호 보내기"""
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', LOCK_PORT))
        client.send(b'SHOW')
        client.close()
    except:
        pass

# 설정
SAMPLE_RATE = 16000
MODEL_SIZE = "base"
HOTKEY = "ctrl+win"  # 글로벌 핫키
MAX_RECORD_SEC = 60  # 최대 녹음 시간 (초)

def create_icon_image(color="gray"):
    """아이콘 이미지 생성 - 음파 모양"""
    size = 64
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if color == "red":
        fill_color = (255, 80, 80, 255)
    elif color == "green":
        fill_color = (80, 200, 80, 255)
    elif color == "orange":
        fill_color = (255, 180, 80, 255)
    else:
        fill_color = (70, 130, 220, 255)  # 파란색

    # 음파 모양 (세로 막대들)
    draw.rectangle([8, 24, 12, 40], fill=fill_color)
    draw.rectangle([16, 16, 20, 48], fill=fill_color)
    draw.rectangle([24, 8, 28, 56], fill=fill_color)
    draw.rectangle([32, 4, 36, 60], fill=fill_color)
    draw.rectangle([40, 8, 44, 56], fill=fill_color)
    draw.rectangle([48, 16, 52, 48], fill=fill_color)
    draw.rectangle([56, 24, 60, 40], fill=fill_color)

    return image

class VoiceApp:
    def __init__(self):
        self.model = None
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.timeout_id = None
        self.tray_icon = None
        self.model_loaded = False
        self.lock_socket = None
        self.hotkey_pressed = False

        # UI 설정
        self.root = tk.Tk()
        self.root.title("Tilnote Voice")
        self.root.geometry("350x180")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        # 창 아이콘 설정
        self.window_icon = ImageTk.PhotoImage(create_icon_image())
        self.root.iconphoto(True, self.window_icon)

        self.root.withdraw()  # 시작시 숨김

        # 프레임
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill="both", expand=True)

        # 상태 라벨
        self.status_label = ttk.Label(frame, text="준비 중...", font=("맑은 고딕", 14))
        self.status_label.pack(pady=8)

        # 결과 라벨
        self.result_label = ttk.Label(frame, text="", font=("맑은 고딕", 10), wraplength=280)
        self.result_label.pack(pady=8)

        # 일반 버튼 프레임
        self.normal_btn_frame = ttk.Frame(frame)
        self.normal_btn_frame.pack(pady=10)

        # 최소화 버튼
        ttk.Button(self.normal_btn_frame, text="최소화", width=8, command=self.minimize_window).pack(side="left", padx=4)

        # 숨기기 버튼 (트레이로)
        ttk.Button(self.normal_btn_frame, text="트레이로", width=8, command=self.hide_window).pack(side="left", padx=4)

        # 종료 버튼
        ttk.Button(self.normal_btn_frame, text="종료", width=8, command=self.quit_app).pack(side="left", padx=4)

        # 녹음 중 버튼 프레임
        self.recording_btn_frame = ttk.Frame(frame)

        # 완료 버튼
        ttk.Button(self.recording_btn_frame, text="완료", width=12, command=self.stop_recording).pack(side="left", padx=4)

        # 취소 버튼
        ttk.Button(self.recording_btn_frame, text="취소", width=12, command=self.cancel_recording).pack(side="left", padx=4)

        # ESC로 녹음 취소 또는 창 숨기기
        self.root.bind("<Escape>", self.on_escape)

        # 창 닫기 버튼 동작 변경 (숨기기)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

    def on_escape(self, event=None):
        """ESC 키 처리 - 녹음 중이면 취소, 아니면 창 숨김"""
        if self.recording:
            self.cancel_recording()
        else:
            self.hide_window()

    def load_model(self):
        """모델 로드"""
        self.status_label.config(text="모델 로딩 중...")
        self.root.update()
        self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        self.model_loaded = True
        self.status_label.config(text=f"[{HOTKEY}] 녹음 시작")
        self.update_tray_icon("gray")

    def show_window(self):
        """창 표시"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        # 화면 중앙에 배치
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

    def hide_window(self):
        """창 숨기기 (트레이로)"""
        self.root.withdraw()

    def minimize_window(self):
        """창 최소화 (작업표시줄로)"""
        self.root.iconify()

    def quit_app(self):
        """앱 종료"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()

    def audio_callback(self, indata, frames, time, status):
        """오디오 스트림 콜백"""
        if self.recording:
            self.audio_data.append(indata.copy())

    def start_recording(self):
        """녹음 시작"""
        self.audio_data = []
        self.recording = True
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            callback=self.audio_callback
        )
        self.stream.start()
        self.status_label.config(text="● 녹음 중...", foreground="red")
        self.result_label.config(text=f"[{HOTKEY}] 다시 누르면 완료")
        self.update_tray_icon("red")

        # 버튼 전환
        self.normal_btn_frame.pack_forget()
        self.recording_btn_frame.pack(pady=10)

        # 자동 타임아웃 설정
        self.timeout_id = self.root.after(MAX_RECORD_SEC * 1000, self.auto_stop)

    def auto_stop(self):
        """자동 녹음 종료"""
        if self.recording:
            self.stop_recording()

    def cancel_recording(self):
        """녹음 취소"""
        self.recording = False
        if self.timeout_id:
            self.root.after_cancel(self.timeout_id)
            self.timeout_id = None
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.audio_data = []
        self.status_label.config(text="녹음 취소됨", foreground="gray")
        self.result_label.config(text="")
        self.update_tray_icon("gray")

        # 버튼 전환
        self.recording_btn_frame.pack_forget()
        self.normal_btn_frame.pack(pady=10)

        self.root.after(1500, lambda: self.status_label.config(
            text=f"[{HOTKEY}] 녹음 시작", foreground="black"
        ))

    def stop_recording(self):
        """녹음 중지 및 변환"""
        self.recording = False
        if self.timeout_id:
            self.root.after_cancel(self.timeout_id)
            self.timeout_id = None
        if self.stream:
            self.stream.stop()
            self.stream.close()

        # 버튼 전환
        self.recording_btn_frame.pack_forget()
        self.normal_btn_frame.pack(pady=10)

        self.status_label.config(text="변환 중...", foreground="orange")
        self.update_tray_icon("orange")
        self.root.update()

        # 오디오 데이터 합치기
        if self.audio_data:
            audio = np.concatenate(self.audio_data).flatten()
            text = self.transcribe(audio)

            if text:
                pyperclip.copy(text)
                self.result_label.config(text=f"복사됨: {text[:50]}...")
                self.status_label.config(text="클립보드에 복사됨!", foreground="green")
                self.update_tray_icon("green")
            else:
                self.status_label.config(text="인식 실패", foreground="gray")
                self.update_tray_icon("gray")
        else:
            self.status_label.config(text="녹음 데이터 없음", foreground="gray")
            self.update_tray_icon("gray")

        # 2초 후 상태 초기화
        self.root.after(2000, self.reset_status)

    def reset_status(self):
        """상태 초기화"""
        self.status_label.config(text=f"[{HOTKEY}] 녹음 시작", foreground="black")
        self.update_tray_icon("gray")

    def transcribe(self, audio: np.ndarray) -> str:
        """음성을 텍스트로 변환"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            audio_int16 = (audio * 32767).astype(np.int16)
            write_wav(temp_path, SAMPLE_RATE, audio_int16)

        try:
            segments, _ = self.model.transcribe(temp_path, language="ko", beam_size=5)
            text = " ".join([seg.text for seg in segments])
            return text.strip()
        finally:
            os.unlink(temp_path)

    def toggle_recording(self):
        """녹음 토글"""
        if not self.model_loaded:
            return
        if self.hotkey_pressed:
            return  # 키 반복 방지
        self.hotkey_pressed = True
        self.show_window()
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def on_hotkey_release(self):
        """핫키 릴리즈"""
        self.hotkey_pressed = False

    def update_tray_icon(self, color):
        """트레이 아이콘 색상 업데이트"""
        if self.tray_icon:
            self.tray_icon.icon = create_icon_image(color)

    def on_tray_show(self, icon=None, item=None):
        """트레이 메뉴/클릭 - 창 보이기"""
        self.root.after(0, self.show_window)

    def on_tray_quit(self, icon, item):
        """트레이 메뉴 - 종료"""
        icon.stop()
        self.root.after(0, self.root.quit)

    def setup_tray(self):
        """시스템 트레이 설정"""
        menu = pystray.Menu(
            pystray.MenuItem("창 열기", self.on_tray_show, default=True),
            pystray.MenuItem(f"녹음: {HOTKEY}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", self.on_tray_quit)
        )

        self.tray_icon = pystray.Icon(
            "tilnote_voice",
            create_icon_image("orange"),
            "Tilnote Voice",
            menu
        )

        # 트레이 아이콘 클릭 시 창 열기
        self.tray_icon.on_activate = self.on_tray_show

        # 트레이 아이콘을 별도 스레드에서 실행
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()

    def start_socket_listener(self):
        """소켓 리스너 시작 (다른 인스턴스의 신호 받기)"""
        if self.lock_socket:
            self.lock_socket.listen(1)
            def listen():
                while True:
                    try:
                        conn, addr = self.lock_socket.accept()
                        data = conn.recv(1024)
                        if data == b'SHOW':
                            self.root.after(0, self.show_window)
                        conn.close()
                    except:
                        break
            listener_thread = threading.Thread(target=listen, daemon=True)
            listener_thread.start()

    def run(self):
        """앱 실행"""
        print(f"[Voice App] 시작됨 - 시스템 트레이에서 실행 중")
        print(f"[Voice App] {HOTKEY} 키로 녹음 시작/중지")
        print(f"[Voice App] 트레이 아이콘 우클릭으로 종료")

        # 소켓 리스너 시작
        self.start_socket_listener()

        # 시스템 트레이 설정
        self.setup_tray()

        # 모델 로드 (백그라운드)
        self.show_window()
        self.root.after(100, self.load_model)

        # 글로벌 핫키 등록
        keyboard.add_hotkey(HOTKEY, self.toggle_recording)
        keyboard.on_release_key('win', lambda e: self.on_hotkey_release())

        # UI 실행
        self.root.mainloop()

        # 정리
        keyboard.unhook_all()
        if self.tray_icon:
            self.tray_icon.stop()

if __name__ == "__main__":
    lock = check_already_running()
    if lock is None:
        # 이미 실행 중 - 기존 창 열기 신호 보내기
        signal_existing_instance()
        sys.exit(0)

    app = VoiceApp()
    app.lock_socket = lock
    app.run()
