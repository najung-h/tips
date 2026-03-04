import yt_dlp
import os

# conda install -c conda-forge ffmpeg

def download_from_file(file_path='url.txt'):
    # 1. 파일 존재 여부 확인
    if not os.path.exists(file_path):
        print(f"[오류] '{file_path}' 파일을 찾을 수 없습니다.")
        print("같은 폴더에 url.txt 파일을 만들고 링크를 넣어주세요.")
        return

    # 2. URL 읽어오기 (공백 제거 및 빈 줄 제외)
    with open(file_path, 'r', encoding='utf-8') as f:
        # '#'으로 시작하는 주석 줄은 제외하고 URL을 읽어옵니다.
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    if not urls:
        print(f"[정보] '{file_path}'에 처리할 URL이 없습니다. 다운로드할 URL을 추가해주세요.")
        return

    total_count = len(urls)
    print(f"📄 총 {total_count}개의 링크를 다운로드합니다.\n")

    # 3. 다운로드 옵션 설정
    # 최고 화질 mp4 영상 + 최고 음질 m4a 음성 -> 병합하여 mp4로 저장
    # 위 조합이 불가능하면, 단일 파일 중 가장 좋은 화질의 mp4 선택
    # 그것도 안 되면, yt-dlp가 선택하는 최적의 단일 파일(best)로 다운
    ydl_opts = {
        # 1. 포맷 설정 (라이브 구간 추출 시에는 'best'가 가장 안정적입니다)
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'outtmpl': '%(title)s_clip.%(ext)s',
        'noplaylist': True,

        # 2. 과거 시점으로 돌아가게 만드는 핵심 옵션들
        'live_from_start': True,       # 방송 시작 지점부터 트래킹 허용
        'wait_for_video': (1, 15),     # 영상 조각이 확인될 때까지 대기
        
        # 3. 구간 지정 (방법 1에서 제안한 최신 방식)
        # 시작-종료 시간을 방송 시작 후 경과 시간 기준으로 작성하세요.
        'download_sections': '[*]05:30:00-06:00:00', 
        'force_keyframes_at_cuts': True,
        
        # 4. ffmpeg가 데이터를 읽을 때 라이브 끝이 아닌 ss 지점부터 읽도록 강제
        'external_downloader': 'ffmpeg',
        'external_downloader_args': {
            'ffmpeg_i': ['-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5']
        },
    }


    # 4. 반복 다운로드 수행
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, url in enumerate(urls, 1):
            try:
                print(f"--- [{i}/{total_count}] 다운로드 시작 ---")
                print(f"URL: {url}")
                
                # 다운로드 실행
                ydl.download([url])
                print(f"✅ [{i}/{total_count}] 다운로드 완료\n")
                
            except Exception as e:
                print(f"⚠️ [{i}/{total_count}] 실패: {url}")
                print(f"   에러 내용: {e}\n")

    print("\n[🎉 작업 종료] 모든 다운로드가 완료되었습니다.")

if __name__ == "__main__":
    # url.txt 파일이 없으면 생성
    if not os.path.exists('url.txt'):
        with open('url.txt', 'w', encoding='utf-8') as f:
            f.write("# 이 파일에 다운로드할 YouTube 영상 URL을 한 줄에 하나씩 입력하세요.\n")
            f.write("# 예: https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")
        print("[안내] 'url.txt' 파일이 생성되었습니다. 다운로드할 URL을 입력하고 다시 실행해주세요.")
    else:
        download_from_file()