import os
import subprocess
import csv
import json
from pathlib import Path

EXTENSIONS = {'.mp4', '.mkv', '.avi'}
CSV_NAME = "video_quality_report.csv"

def _run_process(cmd):
    result = subprocess.run(cmd, capture_output=True)
    stdout = result.stdout.decode('utf-8', errors='replace') if isinstance(result.stdout, bytes) else (result.stdout or '')
    stderr = result.stderr.decode('utf-8', errors='replace') if isinstance(result.stderr, bytes) else (result.stderr or '')
    return result.returncode, stdout, stderr


def get_video_metrics(file_path):
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', file_path
    ]
    returncode, stdout, stderr = _run_process(cmd)
    if returncode != 0 or not stdout:
        print(f"ffprobe failed for {file_path}: {stderr.strip() or 'No output'}")
        return None

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(f"Failed to parse ffprobe JSON for {file_path}: {exc}")
        return None
    
    v_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not v_stream:
        return None

    # Basic stats
    width = int(v_stream.get('width', 0))
    height = int(v_stream.get('height', 0))
    duration = float(data.get('format', {}).get('duration', 0) or 0)
    bitrate = int(data.get('format', {}).get('bitrate', 0) or 0)
    
    # If bitrate not available, calculate from file size
    if bitrate == 0 and duration > 0:
        file_size = os.path.getsize(file_path)
        bitrate = (file_size * 8) / duration  # bits per second
    
    # Calculate Bits Per Pixel (BPP)
    # Using 23.976 as a default if frame_rate is missing
    fps_raw = v_stream.get('avg_frame_rate', '24/1')
    try:
        num, den = map(int, fps_raw.split('/'))
        fps = num / den if den != 0 else 24
    except Exception:
        fps = 24

    bpp = bitrate / (width * height * fps) if (width * height * fps) > 0 else 0

    return {
        "File Name": Path(file_path).name,
        "Resolution": f"{width}x{height}",
        "Bitrate (kbps)": round(bitrate / 1000, 2),
        "FPS": round(fps, 2),
        "BPP Score": round(bpp, 4),
        "Efficiency": "Critical" if bpp < 0.012 else "Bad" if bpp < 0.025 else "Good" if bpp < 0.045 else  "Great" if bpp < 0.06 else "Inefficient",
        "Size (GB)": round(os.path.getsize(file_path) / (1024**3), 2)
    }


def check_for_corruption(file_path):
    """Quickly scans the first 30 seconds for decoding errors."""
    cmd = [
        'ffmpeg', '-v', 'error', '-t', '30', '-i', file_path, 
        '-f', 'null', '-'
    ]
    _, _, stderr = _run_process(cmd)
    return "Potential Error" if stderr else "Clean"

def main():
    folder_path = input("Enter movie folder path: ").strip()
    files = [f for f in Path(folder_path).rglob('*') if f.is_file() and f.suffix.lower() in EXTENSIONS]
    
    report = []
    for f in files:
        print(f"Analyzing Video: {f.name}...")
        metrics = get_video_metrics(str(f))
        if metrics:
            metrics["Integrity"] = check_for_corruption(str(f))
            report.append(metrics)

    if not report:
        print("No valid videos found to analyze.")
        return

    with open(CSV_NAME, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=report[0].keys())
        writer.writeheader()
        writer.writerows(report)
    print(f"Video Report Saved to {CSV_NAME}")

if __name__ == "__main__":
    main()