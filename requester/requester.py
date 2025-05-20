import time
import requests
import base64
from datetime import datetime
import threading
import os
import csv
import argparse
import json

# --- argparse 설정 ---
parser = argparse.ArgumentParser(description='RunPod 요청 자동화 도구')
parser.add_argument('--count', type=int, default=10, help='요청 횟수')
parser.add_argument('--interval', type=int, default=1, help='요청 간 간격(초)')
args = parser.parse_args()

# --- 실행 환경 설정 ---
timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
BASE_DIR = os.path.join('logs', timestamp_str)
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
LOG_FILE = os.path.join(BASE_DIR, 'results_log.csv')

# 폴더가 없으면 생성 (상위 폴더부터 모두 생성)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- RunPod 설정 ---
API_KEY = ''  # RunPod API 키 입력
ENDPOINT_ID = ''
CHECK_INTERVAL = 5

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {API_KEY}'
}

# --- test_input.json 읽어서 입력 데이터 설정 ---
with open('../test_input.json', 'r') as f:
    test_input = json.load(f)

pending_jobs = {}  # job_id를 key로 작업 정보를 저장

# 로그 파일 초기화 (새 파일로 저장)
with open(LOG_FILE, mode='w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['job_id', 'start_time', 'end_time', 'response_time_sec', 'status', 'image_path'])

def send_request():
    payload = test_input
    start_time = datetime.now()

    try:
        response = requests.post(
            f'https://api.runpod.ai/v2/{ENDPOINT_ID}/run',
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        job_id = response.json().get("id")
        if job_id:
            pending_jobs[job_id] = {
                "start_time": start_time,
                "status": "PENDING",
                "image_path": None,
                "response_time": None
            }
            print(f"[요청] 작업 전송 완료. ID: {job_id}")
        else:
            print("[요청] 응답에 작업 ID가 없습니다.")
    except requests.RequestException as e:
        print(f"[요청 오류] {e}")

def check_results():
    while True:
        time.sleep(CHECK_INTERVAL)
        for job_id in list(pending_jobs.keys()):
            job_info = pending_jobs[job_id]
            try:
                response = requests.get(
                    f'https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{job_id}',
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "COMPLETED":
                    end_time = datetime.now()
                    response_time = (end_time - job_info["start_time"]).total_seconds()

                    output = data.get("output", {})
                    if output.get("status") == "success":
                        base64_image = output.get("message")
                        image_data = base64.b64decode(base64_image)
                        filename = os.path.join(OUTPUT_DIR, f'{job_id}.jpg')

                        with open(filename, 'wb') as f:
                            f.write(image_data)

                        job_info.update({
                            "status": "COMPLETED",
                            "image_path": filename,
                            "response_time": response_time
                        })
                        print(f"[완료] 이미지 저장됨: {filename}")
                    else:
                        job_info["status"] = "FAILED"
                        print(f"[실패] 작업 실패: {output}")

                    log_job_result(job_id, job_info, end_time)
                    pending_jobs.pop(job_id)

                elif data.get("status") in ["FAILED", "CANCELLED"]:
                    job_info["status"] = data.get("status")
                    log_job_result(job_id, job_info, datetime.now())
                    print(f"[오류] 작업 실패 또는 취소됨: {job_id}")
                    pending_jobs.pop(job_id)

            except requests.RequestException as e:
                print(f"[상태 확인 오류] {e}")

def log_job_result(job_id, info, end_time):
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            job_id,
            info["start_time"].isoformat(),
            end_time.isoformat(),
            round(info["response_time"] or 0, 2),
            info["status"],
            info["image_path"] or ''
        ])

def start_request_loop(repeat):
    for _ in range(repeat):
        send_request()
        time.sleep(args.interval)

# 결과 확인 스레드 시작 (데몬 스레드로 백그라운드에서 실행)
threading.Thread(target=check_results, daemon=True).start()

if __name__ == '__main__':
    start_request_loop(repeat=args.count)
    # 모든 pending 작업이 완료될 때까지 메인 스레드 대기
    while len(pending_jobs) > 0:
        time.sleep(1)
