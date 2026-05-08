import os
import subprocess
import csv
import json
import tempfile
import re
from pathlib import Path

# --- CONFIGURATION ---
EXTENSIONS = {'.mp4', '.mkv', '.avi'}
CSV_NAME = "audio_analysis_report.csv"

# INTERPRETATION GUIDE (Included in CSV Header)
# Integrated LUFS: Average perceived loudness. Target is -23. Below -28 is "Quiet".
# Loudness Range (LRA): Difference between quiet and loud parts. >15 is "High Dynamic Range".
# True Peak: The highest point of the audio. If below -10, the whole file is recorded too low.

def get_movie_info(file_path):
    """Get duration and audio stream info using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', file_path
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    if result.returncode != 0 or not result.stdout:
        print(f"Warning: ffprobe failed for {file_path}")
        if result.stderr:
            print(result.stderr.strip())
        return 0.0, []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Warning: Could not parse ffprobe output for {file_path}")
        print(result.stdout[:500])
        return 0.0, []

    duration = float(data.get('format', {}).get('duration', 0))
    audio_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
    
    return duration, audio_streams

def analyze_segment(file_path, start_time, duration_limit, temp_dir):
    """Analyzes a specific segment and returns LUFS/LRA/Peak stats."""
    # We create a temporary log file for FFmpeg output
    temp_log = tempfile.NamedTemporaryFile(dir=temp_dir, suffix='.txt', delete=False)
    temp_log_path = temp_log.name
    temp_log.close()

    # FFmpeg command:
    # 1. Seek to start_time (-ss)
    # 2. Take 5 minutes (-t)
    # 3. Downmix to stereo (pan=stereo...) to simulate standard TV listening
    # 4. Apply EBU R128 loudness filter
    filter_str = "pan=stereo|c0=c2+0.707*c0+0.707*c4|c1=c2+0.707*c1+0.707*c5,ebur128=peak=true"
    
    cmd = [
        'ffmpeg', '-nostats', '-ss', str(start_time), '-t', str(duration_limit),
        '-i', file_path, '-af', filter_str, '-f', 'null', '-'
    ]
    
    # Capture stderr because that's where the ebur128 stats are printed
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    output = result.stderr or ''

    # Parse the output for key values
    stats = {"I": 0, "LRA": 0, "Peak": 0}
    for line in output.split('\n'):
        if "I:" in line and "LUFS" in line:
            match = re.search(r'I:\s*(-?\d+\.?\d*)', line)
            if match:
                stats["I"] = float(match.group(1))
        if "LRA:" in line and "LU" in line:
            match = re.search(r'LRA:\s*(-?\d+\.?\d*)', line)
            if match:
                stats["LRA"] = float(match.group(1))
        if "Peak:" in line and "dBFS" in line:
            match = re.search(r'Peak:\s*(-?\d+\.?\d*)', line)
            if match:
                stats["Peak"] = float(match.group(1))
            
    return stats

def main():
    folder_path = input("Enter the path to your movie folder: ").strip()
    movies = [f for f in Path(folder_path).rglob('*') if f.is_file() and f.suffix.lower() in EXTENSIONS]
    
    report_data = []

    # Use a temporary directory for any intermediate processing
    with tempfile.TemporaryDirectory() as temp_dir:
        for movie in movies:
            print(f"Analyzing: {movie.name}...")
            dur, streams = get_movie_info(str(movie))
            
            if not streams or dur < 60: # Skip files with no audio or too short
                continue

            # Define 3 samples (5 mins each)
            # Start: skip first 2 mins. Mid: middle. End: skip last 2 mins.
            samples = [
                120,                  # Start
                (dur / 2) - 150,      # Middle
                dur - 450             # End
            ]

            sample_results = []
            for start in samples:
                # Ensure start time isn't negative or past duration
                actual_start = max(0, min(start, dur - 300))
                res = analyze_segment(str(movie), actual_start, 300, temp_dir)
                sample_results.append(res)

            # Average the results
            avg_lufs = sum(s['I'] for s in sample_results) / 3
            avg_lra = sum(s['LRA'] for s in sample_results) / 3
            max_peak = max(s['Peak'] for s in sample_results)

            report_data.append({
                "File Name": movie.name,
                "Duration (min)": round(dur / 60, 2),
                "Codec": streams[0].get('codec_name', 'unknown'),
                "Channels": streams[0].get('channels', 0),
                "Avg LUFS": round(avg_lufs, 2),
                "LRA": round(avg_lra, 2),
                "True Peak (dB)": round(max_peak, 2),
                "Status": "QUIET" if avg_lufs < -28 else "OK"
            })

    if not report_data:
        print("No valid movies found to analyze.")
        return

    # Write to CSV
    with open(CSV_NAME, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=report_data[0].keys())
        writer.writeheader()
        writer.writerows(report_data)

    print(f"\nDone! Report saved to {CSV_NAME}")

if __name__ == "__main__":
    main()