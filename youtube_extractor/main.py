"""
YouTube 영상 자동 처리 파이프라인
- 오디오 추출 → STT → audio.txt
- 슬라이드 전환 감지 → slides/*.png → slides.pdf
"""

import sys
import re
import argparse
import shutil
import tempfile
from pathlib import Path

import yt_dlp
import moviepy as mp
import whisper
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import img2pdf


def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거"""
    # Windows 파일명 금지 문자 제거
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # 공백 정리
    name = re.sub(r'\s+', ' ', name).strip()
    # 너무 긴 경우 자르기
    if len(name) > 100:
        name = name[:100]
    return name


def download_video(url: str, output_dir: Path) -> Path:
    """YouTube 영상 다운로드"""
    print(f"\n📥 영상 다운로드 중: {url}")

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_title = sanitize_filename(info['title'])
        video_path = output_dir / f"{video_title}.mp4"

        # 실제 다운로드된 파일 찾기
        for file in output_dir.glob("*.mp4"):
            if file.name != "video.mp4":
                video_path = file
                break

    print(f"✅ 다운로드 완료: {video_path.name}")
    return video_path


def extract_audio_and_stt(video_path: Path, output_dir: Path, whisper_model: str = "base") -> Path:
    """오디오 추출 및 STT 수행"""
    audio_path = output_dir / "audio.mp3"
    result_path = output_dir / "audio.txt"

    # 1. 오디오 추출
    print(f"\n🎵 오디오 추출 중...")
    video = mp.VideoFileClip(str(video_path))
    video.audio.write_audiofile(str(audio_path), logger=None)
    video.close()
    print(f"✅ 오디오 추출 완료: {audio_path.name}")

    # 2. Whisper STT
    print(f"\n🤖 음성 인식 중 (Whisper {whisper_model} 모델)...")
    model = whisper.load_model(whisper_model)
    result = model.transcribe(str(audio_path), language="ko")

    # 3. 결과 저장
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(result["text"])

    print(f"✅ STT 완료: {result_path.name}")

    # 임시 오디오 파일 삭제 (선택)
    # audio_path.unlink()

    return result_path


def open_video_capture(video_path: Path):
    """한글 경로 호환 VideoCapture 열기"""
    # 먼저 일반 방법 시도
    cap = cv2.VideoCapture(str(video_path))
    if cap.isOpened():
        return cap

    # 한글 경로 문제시 임시 파일로 복사
    print("   ⚠️ 한글 경로 감지, 대체 방법 사용...")

    # 임시 디렉토리에 영문 이름으로 복사
    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / "temp_video.mp4"
    shutil.copy2(video_path, temp_path)

    cap = cv2.VideoCapture(str(temp_path))
    return cap


def extract_frames(video_path: Path, interval_sec: float = 1.0) -> list[tuple[int, float, np.ndarray]]:
    """비디오에서 프레임 추출 (frame_number, timestamp, image)"""
    print(f"\n🎬 프레임 추출 중 (간격: {interval_sec}초)...")
    print(f"   비디오 경로: {video_path}")
    print(f"   파일 존재: {video_path.exists()}")

    cap = open_video_capture(video_path)
    if not cap.isOpened():
        raise ValueError(f"비디오 파일을 열 수 없습니다: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    frame_interval = int(fps * interval_sec)
    if frame_interval == 0:
        frame_interval = 1

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps
    print(f"   총 프레임: {total_frames}, 영상 길이: {duration_sec:.1f}초")

    frames = []
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            timestamp = frame_count / fps
            frames.append((len(frames), timestamp, frame))

            # 진행 상황 (30초마다)
            if len(frames) % 30 == 0:
                progress = (timestamp / duration_sec * 100) if duration_sec > 0 else 0
                print(f"   진행: {timestamp:.1f}s / {duration_sec:.1f}s ({progress:.1f}%)")

        frame_count += 1

    cap.release()
    print(f"✅ 프레임 추출 완료: {len(frames)}개")
    return frames


def detect_slide_changes(frames: list[tuple[int, float, np.ndarray]], ssim_threshold: float = 0.85) -> list[tuple[int, float, np.ndarray]]:
    """SSIM으로 슬라이드 전환 감지하여 고유 슬라이드만 반환"""
    print(f"\n🔍 슬라이드 전환 감지 중 (threshold: {ssim_threshold})...")

    if not frames:
        return []

    unique_slides = []
    prev_gray = None

    for idx, timestamp, frame in frames:
        # 그레이스케일 변환
        current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_gray is None:
            # 첫 프레임은 무조건 추가
            unique_slides.append((len(unique_slides), timestamp, frame))
            prev_gray = current_gray
            continue

        # 크기가 다른 경우 리사이즈
        if prev_gray.shape != current_gray.shape:
            current_gray = cv2.resize(current_gray, (prev_gray.shape[1], prev_gray.shape[0]))

        # SSIM 계산
        score, _ = ssim(prev_gray, current_gray, full=True)

        if score < ssim_threshold:
            # 새 슬라이드 감지
            unique_slides.append((len(unique_slides), timestamp, frame))
            prev_gray = current_gray

    print(f"✅ 고유 슬라이드 감지: {len(unique_slides)}개")
    return unique_slides


def save_slides(slides: list[tuple[int, float, np.ndarray]], slides_dir: Path) -> tuple[list[Path], list[tuple[str, float]]]:
    """슬라이드를 PNG 파일로 저장. (파일경로 리스트, (파일명, 타임스탬프) 리스트) 반환"""
    print(f"\n💾 슬라이드 저장 중... ({len(slides)}개)")

    slides_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    timestamps = []  # (filename, timestamp)

    for idx, timestamp, frame in slides:
        filename = f"{idx + 1:03d}.png"
        filepath = slides_dir / filename

        # frame 유효성 검사
        if frame is None or frame.size == 0:
            print(f"   ⚠️ 프레임 {idx+1} 무효 - 건너뜀")
            continue

        # 한글 경로 호환: cv2.imencode + 직접 저장
        success, encoded = cv2.imencode('.png', frame)
        if success:
            with open(filepath, 'wb') as f:
                f.write(encoded.tobytes())
            saved_paths.append(filepath)
            timestamps.append((filename, timestamp))
            print(f"   저장: {filename} (t={timestamp:.1f}s)")
        else:
            print(f"   ⚠️ 인코딩 실패: {filename}")

    print(f"✅ 슬라이드 저장 완료: {len(saved_paths)}개 -> {slides_dir}")
    return saved_paths, timestamps


def create_pdf(image_paths: list[Path], output_path: Path) -> Path:
    """이미지들을 PDF로 합치기"""
    print(f"\n📄 PDF 생성 중... ({len(image_paths)}개 이미지)")

    if not image_paths:
        print("   ⚠️ 이미지가 없어 PDF 생성 건너뜀")
        return output_path

    # 실제 존재하는 파일만 필터링
    existing_files = [str(p) for p in sorted(image_paths) if p.exists()]

    if not existing_files:
        print("   ⚠️ 유효한 이미지 파일이 없어 PDF 생성 건너뜀")
        return output_path

    print(f"   유효한 이미지: {len(existing_files)}개")

    # img2pdf로 변환
    pdf_bytes = img2pdf.convert(existing_files)
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"✅ PDF 생성 완료: {output_path.name}")
    return output_path


def process_video(url: str, output_base_dir: Path, frame_interval: float = 1.0,
                  ssim_threshold: float = 0.85, whisper_model: str = "base"):
    """전체 파이프라인 실행"""

    # 임시 다운로드 디렉토리
    temp_dir = output_base_dir / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 영상 다운로드
        video_path = download_video(url, temp_dir)

        # 출력 디렉토리 생성 (영상 제목 기반)
        video_title = sanitize_filename(video_path.stem)
        output_dir = output_base_dir / video_title
        output_dir.mkdir(parents=True, exist_ok=True)
        slides_dir = output_dir / "slides"

        print(f"\n📁 출력 디렉토리: {output_dir}")

        # 2. 오디오 추출 + STT
        extract_audio_and_stt(video_path, output_dir, whisper_model)

        # 3. 프레임 추출
        frames = extract_frames(video_path, frame_interval)

        # 4. 슬라이드 전환 감지
        unique_slides = detect_slide_changes(frames, ssim_threshold)

        # 5. 슬라이드 저장
        slide_paths, timestamps = save_slides(unique_slides, slides_dir)

        # 6. 타임스탬프 저장
        if timestamps:
            time_path = output_dir / "time.txt"
            with open(time_path, "w", encoding="utf-8") as f:
                for filename, ts in timestamps:
                    # timestamp를 mm:ss 또는 hh:mm:ss 형식으로 변환
                    hours = int(ts // 3600)
                    minutes = int((ts % 3600) // 60)
                    seconds = ts % 60
                    if hours > 0:
                        time_str = f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
                    else:
                        time_str = f"{minutes:02d}:{seconds:05.2f}"
                    f.write(f"{filename}\t{time_str}\n")
            print(f"✅ 타임스탬프 저장: {time_path.name}")

        # 7. PDF 생성
        if slide_paths:
            pdf_path = output_dir / "slides.pdf"
            create_pdf(slide_paths, pdf_path)

        # 7. 임시 영상 파일 정리 (선택)
        # video_path.unlink()

        print(f"\n🎉 모든 작업 완료!")
        print(f"   📁 출력 폴더: {output_dir}")
        print(f"   📝 STT 결과: audio.txt")
        print(f"   🖼️  슬라이드: slides/ ({len(slide_paths)}개)")
        print(f"   ⏱️  타임스탬프: time.txt")
        print(f"   📄 PDF: slides.pdf")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="YouTube 영상 자동 처리 (STT + 슬라이드 추출)")
    parser.add_argument("--url", type=str, help="YouTube URL (미지정시 url.txt 사용)")
    parser.add_argument("--output", type=str, default="output", help="출력 디렉토리 (기본: output)")
    parser.add_argument("--interval", type=float, default=1.0, help="프레임 추출 간격 (초, 기본: 1.0)")
    parser.add_argument("--threshold", type=float, default=0.85, help="SSIM 임계값 (기본: 0.85)")
    parser.add_argument("--whisper-model", type=str, default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 모델 (기본: base)")

    args = parser.parse_args()

    # URL 결정
    if args.url:
        urls = [args.url]
    else:
        url_file = Path("url.txt")
        if not url_file.exists():
            print("❌ url.txt 파일이 없습니다. --url 옵션으로 URL을 지정하거나 url.txt를 생성하세요.")
            sys.exit(1)

        with open(url_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        if not urls:
            print("❌ url.txt에 처리할 URL이 없습니다.")
            sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 각 URL 처리
    for i, url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"📹 [{i}/{len(urls)}] 처리 시작")
        print(f"{'='*60}")

        try:
            process_video(
                url=url,
                output_base_dir=output_dir,
                frame_interval=args.interval,
                ssim_threshold=args.threshold,
                whisper_model=args.whisper_model,
            )
        except Exception as e:
            print(f"⚠️ [{i}/{len(urls)}] 실패: {url}")
            print(f"   에러: {e}")
            continue

    print(f"\n{'='*60}")
    print(f"🎉 모든 작업 완료!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
