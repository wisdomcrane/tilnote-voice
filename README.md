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
- 저장 공간: 약 150MB (모델 파일)

## 음성 인식 모델

[faster-whisper](https://github.com/guillaumekln/faster-whisper)의 `base` 모델을 사용합니다.

### 첫 실행 시
- 모델이 자동으로 다운로드됩니다 (약 150MB)
- 다운로드 위치: `~/.cache/huggingface/hub/`
- 인터넷 연결 필요

### 권장 사양

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | 듀얼코어 | 쿼드코어 이상 |
| RAM | 4GB | 8GB 이상 |
| 저장공간 | 500MB | 1GB 이상 |

### 모델 크기 변경 (선택)

`voice_app.py`에서 `MODEL_SIZE`를 수정하면 정확도/속도를 조절할 수 있습니다:

| 모델 | 파라미터 | 모델 크기 | 필요 메모리 | 속도 | 정확도 |
|------|----------|-----------|-------------|------|--------|
| tiny | 39M | ~75MB | ~1GB | 빠름 | 낮음 |
| base | 74M | ~150MB | ~1GB | 보통 | 보통 |
| small | 244M | ~500MB | ~2GB | 느림 | 높음 |
| medium | 769M | ~1.5GB | ~5GB | 매우 느림 | 매우 높음 |
| large-v3 | 1550M | ~3GB | ~10GB | 가장 느림 | 최고 |

## 라이선스

MIT
