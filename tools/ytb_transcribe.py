import os
import re
import subprocess
import tempfile
import shutil
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()
openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def ytb_transcribe(url) -> str:

    tmpdir_audio = None
    tmpdir_script = None

    try:
        if not url:
            return "Didn't find valid YouTube urls."
        
        download_script_task = download_youtube_subtitles(url)
        script_files, tmpdir_script = download_script_task
        print(f"Downloaded, transcription is saved at temprorary path: {tmpdir_script}")
        print(script_files, tmpdir_script)

        if(len(script_files)==0):
            download_task = download_youtube_audio(url)
            audio_files, tmpdir_audio = download_task
            print(f"Downloaded, audio is saved at temprorary path:: {tmpdir_audio}")
            print(audio_files, tmpdir_audio)

            for file_path in audio_files:
                print("Transcribing audio file:")
                with open(file_path, "rb") as audio_file:
                    transcription = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                transcription = transcription.text.strip()
        else:
            transcription = srt_to_plain_text(script_files[0])
        print(transcription)
        return(transcription)

    except Exception as e:
       return f"Sorry, error: {str(e)}"
    finally:
        if tmpdir_script:
            shutil.rmtree(tmpdir_script, ignore_errors=True)
        if tmpdir_audio:
            shutil.rmtree(tmpdir_audio, ignore_errors=True)
        print("Cleaned up temporary directories.")

def check_yt_dlp():
    try:
        subprocess.run(
            ["yt-dlp","--version"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        raise RuntimeError("Did not find yt-dlp, please install it first.\n")

def update_yt_dlp():
    p = subprocess.run(
        ["yt-dlp","-U"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    if p.returncode != 0:
        raise RuntimeError("Failed to update: yt-dlp \n" + p.stdout.strip())
    return p.stdout.strip()

def download_youtube_audio(url):

    check_yt_dlp()
    update_yt_dlp()

    tmpdir = tempfile.mkdtemp(prefix="yt_dl_")
    outtpl = os.path.join(tmpdir, "%(title).15s.%(ext)s")

    cmd = ["yt-dlp", url, "-t", "mp3","-o", outtpl]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError("Failed to Download\n" + p.stderr)
    files = [os.path.join(tmpdir,f) for f in os.listdir(tmpdir)]
    return files, tmpdir

def srt_to_plain_text(filepath: str, joiner: str = " ") -> str:
    """
    Read .srt file, remove sequence numbers and timestamps, keep only subtitle text, and return a plain text string.
    """
    lines = []
    time_pattern = re.compile(r"\d{2}:\d{2}:\d{2},\d{3}\s-->\s\d{2}:\d{2}:\d{2},\d{3}")
    with open(filepath, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue               
            if line.isdigit():
                continue               
            if time_pattern.match(line):
                continue               
            lines.append(line)
    return joiner.join(lines)

def download_youtube_subtitles(
    url: str,
    langs: str = "en,ja,zh-Hans,zh-Hant,zh-TW",
    write_sub: bool = True,
    write_auto_sub: bool = True,
    convert_srt: bool = True
) -> tuple[list[str], str]:  
    """
    Download YouTube subtitles, returning (subtitle file list, temporary directory path).
    """

    check_yt_dlp()
    update_yt_dlp()

    tmpdir = tempfile.mkdtemp(prefix="yt_subs_")
    outtpl = os.path.join(tmpdir, "%(title).15s.%(ext)s")

    cmd = [
        "yt-dlp",
        url,
        "--skip-download",         
        "-o", outtpl,             
    ]
    if write_sub:
        cmd.append("--write-sub")
    if write_auto_sub:
        cmd.append("--write-auto-sub")

    cmd += ["--sub-lang", langs]
    if convert_srt:
        cmd += ["--convert-subs", "srt"]

    print(cmd)
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if p.returncode != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"Fail to Download: \n{p.stderr.strip()}")

    files = []
    for fn in os.listdir(tmpdir):
        files.append(os.path.join(tmpdir, fn))

    return files, tmpdir

