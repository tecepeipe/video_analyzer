# Video Analyzer
Video/Audio analysis for Movies

audio.py scans a folder for movie files, uses `ffprobe` to read duration and audio streams, then runs `ffmpeg` loudness analysis on three 5-minute segments to calculate average LUFS, LRA, and peak level before writing a CSV report. `video.py` also scans a folder for video files, uses `ffprobe` to extract video stream metrics like resolution, bitrate, FPS, and bits-per-pixel, estimates efficiency, checks the first 30 seconds for decoding errors with `ffmpeg`, and saves the results to a separate CSV.

Once ran, it will generate a .csv output

# Video

Report based in bits per pixel rating based in Bitrate versus Resolution

# Audio

# INTERPRETATION GUIDE (Included in CSV Header)
# Integrated LUFS: Average perceived loudness. Target is -23. Below -28 is "Quiet".
# Loudness Range (LRA): Difference between quiet and loud parts. >15 is "High Dynamic Range".
# True Peak: The highest point of the audio. If below -10, the whole file is recorded too low.

