import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

try:
    import yt_dlp
except ImportError:
    print("yt-dlp is not installed.")
    print("Install it with: python -m pip install -U yt-dlp")
    sys.exit(1)


DOWNLOAD_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DOWNLOAD_DIR / "downloads"
TEMP_DIR = OUTPUT_DIR / ".downloader-temp"

AUDIO_FORMATS = {
    "1": "m4a",
    "2": "mp3",
    "3": "opus",
    "4": "flac",
    "5": "wav",
    "6": "aac",
}


def clear_screen() -> None:
    if os.name == "nt":
        command = ["cmd", "/c", "cls"]
    else:
        command = ["clear"]

    subprocess.run(
        command,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def clean_temp_files() -> None:
    """Remove temporary files created by yt-dlp and recreate the temp directory."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(exist_ok=True)


def ensure_dependencies() -> bool:
    """Check required external tools and print installation guidance if missing."""
    missing: list[str] = []

    if shutil.which("ffmpeg") is None:
        missing.append("FFmpeg")

    if shutil.which("ffprobe") is None:
        missing.append("ffprobe")

    if not missing:
        return True

    print("Missing dependency:", ", ".join(missing) + ".")
    print("Download and install FFmpeg from https://www.ffmpeg.org/download.html")
    print("Then restart the downloader.")
    return False


def yt_dlp_options() -> dict[str, Any]:
    """Return options shared by metadata and download operations."""
    return {
        "noplaylist": True,
        "paths": {
            "home": str(OUTPUT_DIR),
            "temp": str(TEMP_DIR),
        },
    }


def get_source_info(url: str) -> dict[str, Any]:
    options: dict[str, Any] = yt_dlp_options()
    options.update({
        "quiet": True,
        "no_warnings": True,
    })

    with yt_dlp.YoutubeDL(cast(Any, options)) as ydl:
        info = ydl.extract_info(url, download=False)
        return cast(dict[str, Any], info)


def get_available_qualities(formats: list[dict[str, Any]]) -> list[int]:
    qualities: set[int] = set()

    for fmt in formats:
        height = fmt.get("height")
        if fmt.get("vcodec") == "none" or not isinstance(height, int) or height <= 0:
            continue
        qualities.add(height)

    return sorted(qualities, reverse=True)


def get_default_quality(qualities: list[int]) -> int:
    """Prefer 1080p, otherwise choose the highest available quality below it."""
    suitable = [quality for quality in qualities if quality <= 1080]
    return max(suitable) if suitable else max(qualities)


def choose_download_mode():
    print("1. Video")
    print("2. Audio only")
    print()

    while True:
        choice = input("Choose [1]: ").strip()

        if not choice or choice == "1":
            return "video"

        if choice == "2":
            return "audio"

        print("Enter 1 or 2.")


def choose_audio_format():
    print()
    print("Audio format:")
    print("1. m4a")
    print("2. mp3")
    print("3. opus")
    print("4. flac")
    print("5. wav")
    print("6. aac")
    print()

    while True:
        choice = input("Choose [1 - m4a]: ").strip()

        if not choice:
            return "m4a"

        audio_format = AUDIO_FORMATS.get(choice)
        if audio_format:
            return audio_format

        print("Enter a number from 1 to 6.")


def choose_video_quality(qualities: list[int]) -> int:
    default_quality = get_default_quality(qualities)

    print()
    print("Available qualities:")
    print()

    for index, quality in enumerate(qualities, start=1):
        suffix = "  <- default" if quality == default_quality else ""
        print(f"{index}. {quality}p{suffix}")

    print()

    while True:
        choice = input(f"Choose [Enter = {default_quality}p]: ").strip()

        if not choice:
            return default_quality

        if choice.isdigit():
            index = int(choice)

            if 1 <= index <= len(qualities):
                return qualities[index - 1]

        print("Enter one of the numbers above.")


def download_audio(url: str, audio_format: str) -> None:
    options: dict[str, Any] = yt_dlp_options()
    options.update({
        "format": "bestaudio/best",
        "outtmpl": str(OUTPUT_DIR / "%(title)s.%(ext)s"),
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": "0",
            },
            {
                "key": "EmbedThumbnail",
            },
        ],
    })

    with yt_dlp.YoutubeDL(cast(Any, options)) as ydl:
        ydl.download([url])


def download_video(url: str, quality: int) -> None:
    format_selector = (
        f"bestvideo[height={quality}]+bestaudio/"
        f"bestvideo[height<={quality}]+bestaudio/"
        f"best[height<={quality}]/best"
    )

    options: dict[str, Any] = yt_dlp_options()
    options.update({
        "format": format_selector,
        "outtmpl": str(
            OUTPUT_DIR / "%(title)s [%(height)sp].%(ext)s"
        ),
        "merge_output_format": "mp4",
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "EmbedThumbnail",
            },
        ],
    })

    with yt_dlp.YoutubeDL(cast(Any, options)) as ydl:
        ydl.download([url])


def download(url: str) -> None:
    clean_temp_files()

    print("Checking source...")
    print()

    try:
        info = get_source_info(url)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return
    except Exception as error:
        print(f"Could not read source: {error}")
        return

    title = info.get("title") or "Unknown title"

    print(title)
    print()

    try:
        mode = choose_download_mode()

        if not ensure_dependencies():
            return

        if mode == "audio":
            audio_format = choose_audio_format()

            print()
            print(f"Downloading best available audio as {audio_format}...")
            print()

            download_audio(url, audio_format)
        else:
            qualities = get_available_qualities(info.get("formats", []))

            if not qualities:
                print("No video qualities were found.")
                return

            quality = choose_video_quality(qualities)

            print()
            print(f"Downloading {quality}p with best available audio...")
            print()

            download_video(url, quality)

        print()
        print("Download finished.")

    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as error:
        message = str(error).lower()
        if "ffmpeg" in message or "ffprobe" in message or "not found" in message:
            print("\nMissing dependency: FFmpeg is not installed or not available on PATH.")
            print("Download and install FFmpeg from https://www.ffmpeg.org/download.html")
        else:
            print(f"\nDownload failed: {error}")
    finally:
        clean_temp_files()


def main() -> None:
    clean_temp_files()

    if not ensure_dependencies():
        print()
        input("Press Enter to exit...")
        return

    while True:
        clear_screen()

        print("Video Downloader")
        print()

        url = input("URL (q to quit): ").strip()

        if url.lower() in {"q", "quit", "exit"}:
            break

        if not url:
            continue

        download(url)

        print()
        input("Press Enter for next download...")

    clean_temp_files()


if __name__ == "__main__":
    main()
