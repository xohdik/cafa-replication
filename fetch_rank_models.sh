#!/bin/bash
# downloads the ten new Q4_K_M files into models/ (needs huggingface_hub; export HF_ENDPOINT=https://hf-mirror.com if the Hub is unreachable)
cd "$(dirname "$0")"
python3 gguf_tool.py get TheBloke/deepseek-coder-1.3b-base-GGUF deepseek-coder-1.3b-base.Q4_K_M.gguf
python3 gguf_tool.py get mradermacher/Qwen2.5-Coder-1.5B-GGUF Qwen2.5-Coder-1.5B.Q4_K_M.gguf
python3 gguf_tool.py get mradermacher/Qwen2.5-Coder-3B-GGUF Qwen2.5-Coder-3B.Q4_K_M.gguf
python3 gguf_tool.py get second-state/StarCoder2-3B-GGUF starcoder2-3b-Q4_K_M.gguf
python3 gguf_tool.py get second-state/StarCoder2-15B-GGUF starcoder2-15b-Q4_K_M.gguf
python3 gguf_tool.py get TheBloke/CodeLlama-13B-GGUF codellama-13b.Q4_K_M.gguf
python3 gguf_tool.py get mradermacher/codegemma-7b-GGUF codegemma-7b.Q4_K_M.gguf
python3 gguf_tool.py get mradermacher/granite-3b-code-base-128k-GGUF granite-3b-code-base-128k.Q4_K_M.gguf
python3 gguf_tool.py get mradermacher/granite-8b-code-base-128k-GGUF granite-8b-code-base-128k.Q4_K_M.gguf
python3 gguf_tool.py get mradermacher/Yi-Coder-9B-GGUF Yi-Coder-9B.Q4_K_M.gguf
