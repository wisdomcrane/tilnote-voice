# Tilnote Voice

음성을 텍스트로 변환하여 클립보드에 복사하는 Windows 앱

## 기능

- `Ctrl+Win` 단축키로 녹음 시작/중지
- 음성 인식 후 자동으로 클립보드에 복사
- 시스템 트레이에서 백그라운드 실행
- 중복 실행 방지

## 설치

### 1. Python 설치

[Python 3.10+](https://www.python.org/downloads/) 설치 (Add to PATH 체크)

### 2. 프로젝트 다운로드

```bash
git clone <repository-url>
cd voice
```

### 3. 가상환경 생성 및 활성화

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 4. 의존성 설치

```bash
pip install -r requirements.txt
```

## 실행

### 방법 1: 직접 실행

```bash
pythonw voice_app.py
```

### 방법 2: 바탕화면 바로가기 만들기

1. 바탕화면에서 우클릭 → 새로 만들기 → 바로 가기
2. 위치 입력:
   ```
   C:\경로\voice\.venv\Scripts\pythonw.exe voice_app.py
   ```
3. 이름: `Tilnote Voice`
4. 마침

## 사용법

| 동작 | 방법 |
|------|------|
| 녹음 시작 | `Ctrl+Win` |
| 녹음 완료 | `Ctrl+Win` 다시 누르기 또는 완료 버튼 |
| 녹음 취소 | `ESC` 또는 취소 버튼 |
| 창 숨기기 | 트레이로 버튼 |
| 앱 종료 | 종료 버튼 또는 트레이 우클릭 → 종료 |

녹음이 완료되면 텍스트가 자동으로 클립보드에 복사됩니다. `Ctrl+V`로 붙여넣기 하세요.

## 요구사항

- Windows 10/11
- Python 3.10+
- 마이크

## 라이선스

MIT
