import moviepy as mp
import whisper
import os

def extract_audio_and_stt(video_path):
    # 1. 파일 경로 설정
    audio_path = video_path.replace(".mp4", ".mp3")
    result_path = video_path.replace(".mp4", ".txt")

    print(f"🎵 오디오 추출 중: {video_path}")
    
    # 2. 비디오에서 오디오 추출 (MoviePy 사용)
    try:
        video = mp.VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path, logger=None)
        video.close()
        print(f"✅ 오디오 추출 완료: {audio_path}")
    except Exception as e:
        print(f"❌ 오디오 추출 실패: {e}")
        return

    # 3. Whisper AI 모델 로드
    # 'base'는 빠르고, 'turbo'나 'large'는 정확하지만 무겁습니다.
    print("🤖 Whisper 모델 로드 중 (최초 실행 시 시간이 걸릴 수 있습니다)...")
    model = whisper.load_model("base") 

    # 4. 음성 인식 실행
    print("✍️ 음성 받아쓰기 시작 (시간이 다소 소요됩니다)...")
    result = model.transcribe(audio_path, language="ko") # 한국어 고정 또는 제거 시 자동인식

    # 5. 결과 저장
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(result["text"])

    print(f"🎉 모든 작업 완료! 결과 저장됨: {result_path}")
    
    # (선택) 임시 오디오 파일 삭제
    # os.remove(audio_path)

if __name__ == "__main__":
    # 다운로드 받은 파일명으로 실행 (예시)
    # 실제로는 yt-dlp가 저장한 파일 이름을 변수로 받아오게 연결하면 좋습니다.
    target_video = "pjt.mp4" 
    if os.path.exists(target_video):
        extract_audio_and_stt(target_video)