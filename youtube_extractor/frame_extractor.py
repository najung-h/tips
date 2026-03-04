"""Frame Extractor - 비디오에서 프레임 추출"""

from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np


@dataclass
class ExtractedFrame:
    """추출된 프레임 정보"""

    frame_number: int
    timestamp_sec: float
    image_path: Path | None = None
    image_bytes: bytes | None = None


class FrameExtractor:
    """
    비디오에서 프레임을 추출하는 서비스

    OpenCV를 사용하여 N초 간격으로 프레임 추출
    """

    def __init__(self, interval_sec: float = 1.0):
        """
        Args:
            interval_sec: 프레임 추출 간격 (초)
        """
        self.interval_sec = interval_sec

    async def extract_frames(
        self,
        video_path: str | Path,
        output_dir: str | Path | None = None,
    ) -> list[ExtractedFrame]:
        """
        비디오에서 프레임 추출

        Args:
            video_path: 비디오 파일 경로
            output_dir: 프레임 이미지 저장 경로 (None이면 bytes로 반환)

        Returns:
            추출된 프레임 목록
        """
        video_path = str(video_path)
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise ValueError(f"Failed to open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # Fallback FPS
        
        frame_interval = int(fps * self.interval_sec)
        if frame_interval == 0:
            frame_interval = 1

        frames = []
        frame_count = 0
        saved_count = 0
        
        # 비디오 정보 로깅
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frames / fps if fps > 0 else 0
        print(f"[FrameExtractor] Start extracting. Total frames: {total_frames}, Duration: {duration_sec:.2f}s, Interval: {self.interval_sec}s")

        # 출력 디렉토리 생성
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 지정된 간격마다 프레임 추출
            if frame_count % frame_interval == 0:
                timestamp = frame_count / fps
                
                # 진행 상황 로깅 (약 60초 분량 처리할 때마다 로그 출력)
                log_step = int(60 / self.interval_sec * frame_interval) if self.interval_sec > 0 else frame_interval * 60
                if log_step > 0 and frame_count % log_step == 0:
                    progress = (timestamp / duration_sec * 100) if duration_sec > 0 else 0
                    print(f"[FrameExtractor] Progress: {timestamp:.1f}s / {duration_sec:.1f}s ({progress:.1f}%)")

                extracted_frame = ExtractedFrame(
                    frame_number=saved_count + 1,
                    timestamp_sec=timestamp,
                )

                if output_dir:
                    # 이미지 파일로 저장
                    image_filename = f"frame_{saved_count + 1:04d}.jpg"
                    image_path = output_dir / image_filename
                    cv2.imwrite(str(image_path), frame)
                    extracted_frame.image_path = image_path
                else:
                    # 메모리에 바이트로 저장 (압축)
                    ret_enc, buffer = cv2.imencode(".jpg", frame)
                    if ret_enc:
                        extracted_frame.image_bytes = buffer.tobytes()

                frames.append(extracted_frame)
                saved_count += 1

            frame_count += 1

        cap.release()
        return frames

    async def extract_frames_from_bytes(
        self,
        video_bytes: bytes,
    ) -> list[ExtractedFrame]:
        """
        바이트 데이터에서 프레임 추출
        """
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
            temp_video.write(video_bytes)
            temp_video_path = temp_video.name

        try:
            return await self.extract_frames(temp_video_path)
        finally:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)