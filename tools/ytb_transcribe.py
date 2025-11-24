import os
import re
import subprocess
import tempfile
import shutil
from typing import List, Tuple
import time
import random
from openai import OpenAI
from tools.decorator import tool

from dotenv import load_dotenv
load_dotenv()
openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@tool(
    name = "ytb_transcribe",
    description = "From YouTube video to extract transcription or audio and transcript it to text.",
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"}
        },
        "required": ["url"],
        "additionalProperties": False
        },
    strict = True,
    display_name = "📺 Youtube Transcribe"
)
def ytb_transcribe(url) -> str:

    check_yt_dlp()
    update_yt_dlp()

    tmpdir_audio = None
    tmpdir_script = None

    try:
        if not url:
            return "Didn't find valid YouTube urls."
        
        download_script_task = download_youtube_subtitles(url)
        script_files, tmpdir_script = download_script_task
        print(f"Downloaded, transcription is saved at temprorary path: {tmpdir_script}")
        print(script_files, tmpdir_script)

        if(len(script_files) == 0):
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
            print("understanding")
            transcription = srt_to_plain_text(script_files)
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

def list_subs(url: str) -> Tuple[bool, str]:

    p = subprocess.run(
        ["yt-dlp", "--list-subs", url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if p.returncode != 0:
        return None, None

    lines = (p.stdout or p.stderr).splitlines()
    manual, auto = set(), set()
    section = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        # 切换区块
        if line.startswith("[info] Available automatic captions"):
            section = "auto"
            continue
        if line.startswith("[info] Available subtitles"):
            section = "manual"
            continue
        # 跳过表头
        if section is None or line.lower().startswith(("language", "name", "formats")):
            continue
        # 取语言码
        code = line.split()[0]
        if section == "manual":
            manual.add(code)
        else:  # auto
            auto.add(code)

    priority = ["en", "ja", "zh", "zh-CN", "zh-TW"]

    if manual != []:
        for lang in priority:
            if lang in manual:
                return True, lang
    if auto != []:
        for lang in auto:
            if lang.endswith("-orig"):
                return False, lang
    return None, ""


def download_youtube_subtitles(
    url: str,
) -> Tuple[str, str]:

    is_manual_sub, sub = list_subs(url)
    if is_manual_sub is None:
        return "", None
    print(f"Subtitles found: {sub}, is_manual_sub: {is_manual_sub}")

    tmpdir = tempfile.mkdtemp(prefix="yt_sub_")
    outtpl = os.path.join(tmpdir, "%(title).15s.%(ext)s")


    cmd = [
        "yt-dlp", url,
        "--skip-download",
        "--sub-lang", sub,
        "-o", outtpl,
    ]
    if is_manual_sub:
        cmd.append("--write-sub")
    else:
        cmd.append("--write-auto-sub")
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
        raise RuntimeError(f"Subtitles download failed:\n{p.stderr.strip()}")

    files = []
    for fn in os.listdir(tmpdir):
        files.append(os.path.join(tmpdir, fn))
    print(f"Downloaded subtitles: {files}")
    return files[0], tmpdir

