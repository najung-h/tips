# YouTube 영상 자동 처리 파이프라인 설계

## 개요
YouTube 동영상에서 자동으로 오디오 STT와 슬라이드 이미지를 추출하는 도구

## 처리 흐름

```
url.txt (YouTube URL)
    │
    ▼
┌─────────────────────────────────┐
│   1. 영상 다운로드 (yt-dlp)     │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│   2. 오디오 추출 (moviepy)      │
│   └─► audio.mp3                 │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│   3. STT (Whisper)              │
│   └─► audio.txt                 │
└─────────────────────────────────┘
    │
    ▼ (병렬 가능)
┌─────────────────────────────────┐
│   4. 프레임 추출 (OpenCV)       │
│   - 1초 간격으로 프레임 캡처    │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│   5. 슬라이드 전환 감지 (SSIM)  │
│   - 이전 프레임과 유사도 비교   │
│   - threshold 이하 → 새 슬라이드│
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│   6. 슬라이드 저장              │
│   └─► slides/001.png, 002.png...│
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│   7. PDF 합치기 (img2pdf)       │
│   └─► slides.pdf                │
└─────────────────────────────────┘
```

## 출력 구조

```
output/
├── {영상제목}/
│   ├── audio.txt          # STT 결과 텍스트
│   ├── slides/            # 추출된 슬라이드 이미지
│   │   ├── 001.png
│   │   ├── 002.png
│   │   └── ...
│   └── slides.pdf         # 슬라이드 PDF
```

## 활용 모듈

| 모듈 | 용도 | 비고 |
|------|------|------|
| `yt-dlp` | YouTube 영상 다운로드 | download_youtube_video.py 참고 |
| `moviepy` | 비디오에서 오디오 추출 | extract_audio.py 참고 |
| `whisper` | 음성 → 텍스트 변환 | extract_audio.py 참고 |
| `opencv-python` | 프레임 추출 | frame_extractor.py 참고 |
| `scikit-image` | SSIM 유사도 계산 | scene_detector.py 참고 |
| `img2pdf` | 이미지 → PDF 변환 | 새로 추가 |

## 핵심 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `frame_interval` | 1.0초 | 프레임 추출 간격 |
| `ssim_threshold` | 0.85 | 슬라이드 전환 감지 임계값 (낮을수록 민감) |
| `whisper_model` | "base" | Whisper 모델 크기 (base/small/medium/large) |

## 실행 방법

```bash
# 1. url.txt에 YouTube URL 입력
echo "https://www.youtube.com/watch?v=..." > url.txt

# 2. 실행
python main.py

# 또는 직접 URL 지정
python main.py --url "https://www.youtube.com/watch?v=..."
```

## 의존성 설치

```bash
pip install yt-dlp moviepy openai-whisper opencv-python scikit-image img2pdf numpy
```

## 파일 구조

```
youtube/
├── main.py              # 메인 실행 스크립트 (신규)
├── url.txt              # 입력 URL
├── 설계사항.md          # 본 문서
├── output/              # 출력 폴더 (자동 생성)
│
├── download_youtube_video.py  # 기존 (참고용)
├── extract_audio.py           # 기존 (참고용)
├── frame_extractor.py         # 기존 (참고용)
└── scene_detector.py          # 기존 (참고용)
```
