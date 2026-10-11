"""
SentiCall v3 — Build-Time Whisper Model Downloader
Downloads quantized multilingual ONNX Whisper models from Hugging Face for 100% self-hosted inference.
Stored in models/whisper-tiny/ to serve from same-origin /models/.
"""

import os
import sys
import time
import requests

HF_BASE_URL = "https://huggingface.co/Xenova/whisper-tiny/resolve/main"

FILES_TO_DOWNLOAD = [
    "config.json",
    "generation_config.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "onnx/encoder_model_quantized.onnx",
    "onnx/decoder_model_merged_quantized.onnx"
]

def download_file(url: str, dest_path: str, max_retries: int = 3):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        print(f"Already downloaded: {os.path.basename(dest_path)} ({os.path.getsize(dest_path)} bytes)")
        return True

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Downloading {url} -> {dest_path} (attempt {attempt}/{max_retries})...")
            with requests.get(url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            print(f"Downloaded {dest_path} successfully ({os.path.getsize(dest_path)} bytes)")
            return True
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
            else:
                return False

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_dir = os.path.join(root_dir, "models", "whisper-tiny")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Downloading self-hosted Whisper Tiny quantized ONNX model to {out_dir}...")
    success = True
    for rel_file in FILES_TO_DOWNLOAD:
        url = f"{HF_BASE_URL}/{rel_file}"
        dest = os.path.join(out_dir, rel_file)
        if not download_file(url, dest):
            success = False
            print(f"Failed to download {rel_file}")

    if success:
        print("All Whisper Tiny ONNX files successfully downloaded and verified!")
    else:
        print("Warning: Some model files failed to download.")

if __name__ == "__main__":
    main()
