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
import json
import pyperclip
import keyboard
import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image, ImageDraw, ImageTk
import socket

# 설정 파일 경로
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# 기본 설정
DEFAULT_CONFIG = {
    "model_size": "small",
    "language": "ko",
    "history": []
}

def load_config():
    """설정 로드"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 기본값 병합
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """설정 저장"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

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
MODEL_SIZE = "medium" # 모델 크기 설정 (예: tiny, base, small, medium, large-v3)
MAX_RECORD_SEC = 60  # 최대 녹음 시간 (초)

# 플랫폼별 단축키 설정
if sys.platform == "darwin":  # Mac
    HOTKEY = "ctrl+cmd"
else:  # Windows, Linux
    HOTKEY = "ctrl+win"

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
        self.config = load_config()
        self.model = None
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.timeout_id = None
        self.tray_icon = None
        self.model_loaded = False
        self.lock_socket = None
        self.hotkey_pressed = False
        self.timer_id = None
        self.record_seconds = 0
        self.current_volume = 0  # 음성 레벨

        # UI 설정
        self.root = tk.Tk()
        self.root.title("Tilnote Voice")
        self.root.geometry("400x200")
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
        self.status_label.pack(pady=4)

        # 타이머 & 볼륨 프레임
        self.timer_frame = ttk.Frame(frame)

        # 타이머 라벨
        self.timer_label = ttk.Label(self.timer_frame, text="0:00", font=("맑은 고딕", 12))
        self.timer_label.pack(side="left", padx=10)

        # 볼륨 미터 (캔버스)
        self.volume_canvas = tk.Canvas(self.timer_frame, width=150, height=16, bg="#e0e0e0", highlightthickness=0)
        self.volume_canvas.pack(side="left", padx=10)
        self.volume_bar = self.volume_canvas.create_rectangle(0, 0, 0, 16, fill="#4CAF50", outline="")

        # 결과 라벨
        self.result_label = ttk.Label(frame, text="", font=("맑은 고딕", 10), wraplength=280)
        self.result_label.pack(pady=4)

        # 일반 버튼 프레임
        self.normal_btn_frame = ttk.Frame(frame)
        self.normal_btn_frame.pack(pady=10)

        # 녹음 시작 버튼
        self.record_btn = ttk.Button(self.normal_btn_frame, text="녹음 시작", width=8, command=self.start_recording_if_ready)
        self.record_btn.pack(side="left", padx=3)

        # 히스토리 버튼
        ttk.Button(self.normal_btn_frame, text="히스토리", width=8, command=self.show_history).pack(side="left", padx=3)

        # 설정 버튼
        ttk.Button(self.normal_btn_frame, text="설정", width=6, command=self.show_settings).pack(side="left", padx=3)

        # 최소화 버튼
        ttk.Button(self.normal_btn_frame, text="최소화", width=6, command=self.hide_window).pack(side="left", padx=3)

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

    def show_settings(self):
        """설정 창 표시"""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("설정")
        settings_win.geometry("300x200")
        settings_win.attributes("-topmost", True)
        settings_win.resizable(False, False)
        settings_win.transient(self.root)
        settings_win.grab_set()

        frame = ttk.Frame(settings_win, padding=15)
        frame.pack(fill="both", expand=True)

        # 모델 크기 선택
        ttk.Label(frame, text="모델 크기:", font=("맑은 고딕", 10)).grid(row=0, column=0, sticky="w", pady=5)
        model_var = tk.StringVar(value=self.config.get("model_size", "small"))
        model_combo = ttk.Combobox(frame, textvariable=model_var, values=["tiny", "base", "small", "medium", "large-v3"], state="readonly", width=15)
        model_combo.grid(row=0, column=1, pady=5, padx=10)

        # 언어 선택
        ttk.Label(frame, text="언어:", font=("맑은 고딕", 10)).grid(row=1, column=0, sticky="w", pady=5)
        lang_var = tk.StringVar(value=self.config.get("language", "ko"))
        lang_combo = ttk.Combobox(frame, textvariable=lang_var, values=["ko", "en", "ja", "zh"], state="readonly", width=15)
        lang_combo.grid(row=1, column=1, pady=5, padx=10)

        # 현재 모델 표시
        current_label = ttk.Label(frame, text=f"현재 로드됨: {self.config.get('model_size', 'small')}", font=("맑은 고딕", 9), foreground="gray")
        current_label.grid(row=2, column=0, columnspan=2, pady=10)

        def save_and_close():
            new_model = model_var.get()
            new_lang = lang_var.get()
            model_changed = new_model != self.config.get("model_size")

            self.config["model_size"] = new_model
            self.config["language"] = new_lang
            save_config(self.config)

            if model_changed:
                messagebox.showinfo("설정", f"모델이 '{new_model}'로 변경됩니다.\n앱을 재시작해주세요.", parent=settings_win)
            settings_win.destroy()

        # 저장 버튼
        ttk.Button(frame, text="저장", width=10, command=save_and_close).grid(row=3, column=0, columnspan=2, pady=15)

    def show_history(self):
        """히스토리 창 표시"""
        history_win = tk.Toplevel(self.root)
        history_win.title("히스토리")
        history_win.geometry("400x300")
        history_win.attributes("-topmost", True)
        history_win.resizable(False, False)
        history_win.transient(self.root)

        frame = ttk.Frame(history_win, padding=10)
        frame.pack(fill="both", expand=True)

        # 리스트박스 + 스크롤바
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")

        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("맑은 고딕", 10), height=12)
        listbox.pack(fill="both", expand=True)
        scrollbar.config(command=listbox.yview)

        # 히스토리 로드
        history = self.config.get("history", [])
        for item in reversed(history):  # 최신 먼저
            listbox.insert("end", item[:60] + "..." if len(item) > 60 else item)

        if not history:
            listbox.insert("end", "(히스토리 없음)")

        def copy_selected():
            selection = listbox.curselection()
            if selection and history:
                idx = len(history) - 1 - selection[0]  # reversed 순서 보정
                pyperclip.copy(history[idx])
                messagebox.showinfo("복사됨", "클립보드에 복사되었습니다.", parent=history_win)

        def clear_history():
            if messagebox.askyesno("확인", "히스토리를 모두 삭제하시겠습니까?", parent=history_win):
                self.config["history"] = []
                save_config(self.config)
                listbox.delete(0, "end")
                listbox.insert("end", "(히스토리 없음)")

        btn_frame = ttk.Frame(history_win)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="복사", width=10, command=copy_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="전체 삭제", width=10, command=clear_history).pack(side="left", padx=5)

    def add_to_history(self, text):
        """히스토리에 추가"""
        if text:
            history = self.config.get("history", [])
            history.append(text)
            # 최대 50개 유지
            if len(history) > 50:
                history = history[-50:]
            self.config["history"] = history
            save_config(self.config)

    def load_model(self):
        """모델 로드"""
        model_size = self.config.get("model_size", "small")
        self.status_label.config(text=f"모델 로딩 중... ({model_size})")
        self.root.update()

        # GPU 자동 감지
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
                print(f"[Voice App] GPU 사용: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                compute_type = "int8"
                print("[Voice App] CPU 사용")
        except ImportError:
            device = "cpu"
            compute_type = "int8"
            print("[Voice App] CPU 사용 (torch 없음)")

        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.model_loaded = True
        self.status_label.config(text=f"[{HOTKEY}] 녹음 시작")
        self.update_tray_icon("gray")

    def show_window(self):
        """창 표시"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        # 화면 우측 하단에 배치 (작업표시줄 위)
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        margin = 20  # 화면 가장자리 여백
        taskbar_height = 80  # 작업표시줄 높이 + 시스템 알림 영역
        x = screen_w - w - margin
        y = screen_h - h - taskbar_height - margin
        self.root.geometry(f"+{x}+{y}")

    def hide_window(self):
        """창 숨기기 (트레이로)"""
        self.root.withdraw()

    def start_recording_if_ready(self):
        """녹음 시작 (모델 로드 완료 시)"""
        if self.model_loaded and not self.recording:
            self.start_recording()

    def quit_app(self):
        """앱 종료"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()

    def audio_callback(self, indata, frames, time, status):
        """오디오 스트림 콜백"""
        if self.recording:
            self.audio_data.append(indata.copy())
            # 볼륨 레벨 계산 (RMS)
            self.current_volume = np.sqrt(np.mean(indata**2)) * 5  # 0~1 범위로 스케일링

    def start_recording(self):
        """녹음 시작"""
        self.audio_data = []
        self.recording = True
        self.record_seconds = 0
        self.current_volume = 0
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

        # 타이머 & 볼륨 표시
        self.timer_frame.pack(pady=4)
        self.update_timer()

        # 버튼 전환
        self.normal_btn_frame.pack_forget()
        self.recording_btn_frame.pack(pady=10)

        # 자동 타임아웃 설정
        self.timeout_id = self.root.after(MAX_RECORD_SEC * 1000, self.auto_stop)

    def update_timer(self):
        """타이머 및 볼륨 업데이트"""
        if self.recording:
            self.record_seconds += 1
            mins = self.record_seconds // 60
            secs = self.record_seconds % 60
            self.timer_label.config(text=f"{mins}:{secs:02d}")

            # 볼륨 바 업데이트
            volume_width = min(int(self.current_volume * 150), 150)
            self.volume_canvas.coords(self.volume_bar, 0, 0, volume_width, 16)

            # 볼륨에 따라 색상 변경
            if self.current_volume > 0.7:
                self.volume_canvas.itemconfig(self.volume_bar, fill="#f44336")  # 빨강
            elif self.current_volume > 0.4:
                self.volume_canvas.itemconfig(self.volume_bar, fill="#FF9800")  # 주황
            else:
                self.volume_canvas.itemconfig(self.volume_bar, fill="#4CAF50")  # 초록

            self.timer_id = self.root.after(1000, self.update_timer)

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
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.audio_data = []
        self.status_label.config(text="녹음 취소됨", foreground="gray")
        self.result_label.config(text="")
        self.update_tray_icon("gray")

        # 타이머 숨기기
        self.timer_frame.pack_forget()

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
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        if self.stream:
            self.stream.stop()
            self.stream.close()

        # 타이머 숨기기
        self.timer_frame.pack_forget()

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
                self.add_to_history(text)  # 히스토리 저장
                display_text = text[:50] + "..." if len(text) > 50 else text
                self.result_label.config(text=f"복사됨: {display_text}")
                self.status_label.config(text="클립보드에 복사됨!", foreground="green")
                self.update_tray_icon("green")
            else:
                self.status_label.config(text="인식 실패", foreground="gray")
                self.update_tray_icon("gray")
        else:
            self.status_label.config(text="녹음 데이터 없음", foreground="gray")
            self.update_tray_icon("gray")

        # 3초 후 상태 초기화 및 창 숨기기
        self.root.after(3000, self.reset_status)

    def reset_status(self):
        """상태 초기화 및 창 숨기기"""
        self.status_label.config(text=f"[{HOTKEY}] 녹음 시작", foreground="black")
        self.update_tray_icon("gray")
        self.hide_window()

    def transcribe(self, audio: np.ndarray) -> str:
        """음성을 텍스트로 변환"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            audio_int16 = (audio * 32767).astype(np.int16)
            write_wav(temp_path, SAMPLE_RATE, audio_int16)

        try:
            language = self.config.get("language", "ko")
            segments, _ = self.model.transcribe(temp_path, language=language, beam_size=5)
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
