#!/usr/bin/env python3
"""gguf_tool.py find "<search words>"   list GGUF repos on the Hub (or the mirror in HF_ENDPOINT) with their Q4_K_M files
   gguf_tool.py get <repo> <filename>   download one file into models/
Needs `pip install huggingface_hub`. If huggingface.co is not reachable, export HF_ENDPOINT=https://hf-mirror.com first.
Always check the model card: the study needs BASE checkpoints, not instruct or chat models."""
import sys
from huggingface_hub import HfApi, hf_hub_download
api = HfApi()
if sys.argv[1] == "find":
    for m in api.list_models(search=sys.argv[2], filter="gguf", sort="downloads", limit=12):
        files = [f for f in api.list_repo_files(m.id) if "Q4_K_M" in f and f.endswith(".gguf")]
        print(f"{m.id}  downloads={m.downloads}  {files[:2]}")
elif sys.argv[1] == "get":
    print(hf_hub_download(sys.argv[2], sys.argv[3], local_dir="models"))
