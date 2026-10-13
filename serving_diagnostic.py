"""
Phase 0 diagnostic: confirm the model-serving stack actually works on the
R740's Tesla P40s (Pascal, compute capability 6.1) before scheduling the
full 16-condition factorial sweep.

Usage:
    python3 serving_diagnostic.py                  # defaults to gpt2, tiny smoke test
    python3 serving_diagnostic.py --gguf <path>     # test llama.cpp on a local GGUF

Checks, in order:
  1. nvidia-smi / driver sanity
  2. torch CUDA visibility + compute capability report
  3. llama.cpp / GGUF smoke test (the supported path on Pascal -- vLLM is not attempted)
  4. transformers fallback generate() call, as the safe baseline
Prints PASS/FAIL/FALLBACK per stack plus rough tokens/sec, so the compute
budget in RESEARCH_PLAN.md (Sections 5.5, 10) can be re-estimated from real
numbers instead of a placeholder guess.
"""
import argparse
import subprocess
import sys
import time


def check_nvidia_smi() -> bool:
    print("=" * 60)
    print("1. nvidia-smi / driver check")
    print("=" * 60)
    try:
        out = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=15)
        if out.returncode != 0:
            print("FAIL: nvidia-smi returned non-zero.")
            print(out.stderr)
            return False
        print(out.stdout)
        return True
    except FileNotFoundError:
        print("FAIL: nvidia-smi not found on PATH. Driver not installed or not in PATH.")
        return False
    except Exception as e:
        print(f"FAIL: {e}")
        return False


def check_torch_cuda() -> bool:
    print("=" * 60)
    print("2. torch CUDA visibility")
    print("=" * 60)
    try:
        import torch
    except ImportError:
        print("FAIL: torch not installed. pip install torch first.")
        return False

    print(f"torch version: {torch.__version__}")
    available = torch.cuda.is_available()
    print(f"CUDA available: {available}")
    if not available:
        print("FAIL: torch does not see any CUDA device. Check driver / "
              "CUDA toolkit / torch build (cu118 vs cu121 vs cpu-only wheel).")
        return False

    n = torch.cuda.device_count()
    print(f"Device count: {n}")
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        cap = torch.cuda.get_device_capability(i)
        mem = torch.cuda.get_device_properties(i).total_memory / 1e9
        print(f"  cuda:{i}  {name}  compute capability {cap}  {mem:.1f} GB")
        if cap[0] < 7:
            print(f"  NOTE: compute capability {cap} is Pascal-generation. "
                  "Some vLLM attention kernels and newer torch features "
                  "assume >=7.0 (Volta+, tensor cores). This is exactly the "
                  "thing step 3 below is checking for -- don't assume it "
                  "works from this check alone.")
    return True


def check_llama_cpp(model_path: str) -> tuple[bool, float]:
    print("=" * 60)
    print(f"3. llama.cpp / GGUF smoke test  (model={model_path})")
    print("=" * 60)
    print("NOTE: vLLM is not attempted here. Confirmed against current "
          "upstream: vLLM's documented minimum compute capability is 7.0+, "
          "a Pascal-support PR was closed unmerged, and the P40 (sm_61) "
          "will not initialize regardless of the torch/transformers "
          "version underneath it. llama.cpp + GGUF is the supported path "
          "on this hardware -- see RESEARCH_PLAN.md 5.4.")
    try:
        from llama_cpp import Llama
    except ImportError:
        print("FAIL: llama-cpp-python not installed.")
        return False, 0.0

    import os
    if not os.path.exists(model_path):
        print(f"FAIL: no GGUF file at {model_path}.")
        return False, 0.0

    try:
        t0 = time.time()
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=2048,
            verbose=False,
        )
        load_time = time.time() - t0
        print(f"Model loaded in {load_time:.1f}s")

        prompt = "def add(a, b):\n    return"
        t0 = time.time()
        out = llm(prompt, max_tokens=32, temperature=0.0)
        gen_time = time.time() - t0

        text = out["choices"][0]["text"]
        n_tokens = out["usage"]["completion_tokens"]
        tok_per_sec = n_tokens / gen_time if gen_time > 0 else 0.0

        print(f"Generated {n_tokens} tokens in {gen_time:.2f}s "
              f"({tok_per_sec:.1f} tok/s)")
        print(f"Output: {text!r}")
        print("PASS: llama.cpp works on this hardware.")
        print("If tok/s looks low, confirm GGML_CUDA_FORCE_MMQ was set at "
              "build/run time -- the default FP16 path is ~64x slower on "
              "Pascal than the INT8/DP4A MMQ path.")
        return True, tok_per_sec

    except Exception as e:
        print(f"FAIL: llama.cpp raised an exception during load/generate: {e}")
        return False, 0.0


def check_transformers_fallback(model_name: str) -> tuple[bool, float]:
    print("=" * 60)
    print(f"4. transformers fallback smoke test  (model={model_name})")
    print("=" * 60)
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("FAIL: transformers not installed.")
        return False, 0.0

    try:
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16, device_map="cuda:0"
        )
        load_time = time.time() - t0
        print(f"Model loaded in {load_time:.1f}s")

        prompt = "def add(a, b):\n    return"
        inputs = tok(prompt, return_tensors="pt").to("cuda:0")

        t0 = time.time()
        out = model.generate(**inputs, max_new_tokens=32, do_sample=False)
        gen_time = time.time() - t0

        n_tokens = out.shape[1] - inputs["input_ids"].shape[1]
        tok_per_sec = n_tokens / gen_time if gen_time > 0 else 0.0

        text = tok.decode(out[0], skip_special_tokens=True)
        print(f"Generated {n_tokens} tokens in {gen_time:.2f}s "
              f"({tok_per_sec:.1f} tok/s)")
        print(f"Output: {text!r}")
        print("PASS: transformers fallback works on this hardware.")
        return True, tok_per_sec

    except Exception as e:
        print(f"FAIL: transformers raised an exception: {e}")
        return False, 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt2")
    parser.add_argument("--gguf", default=None)
    args = parser.parse_args()

    smi_ok = check_nvidia_smi()
    if not smi_ok:
        print("\nSTOP: fix the driver/nvidia-smi issue before proceeding further.")
        sys.exit(1)

    cuda_ok = check_torch_cuda()
    if not cuda_ok:
        print("\nSTOP: fix torch/CUDA visibility before proceeding further.")
        sys.exit(1)

    if args.gguf:
        llama_ok, llama_tps = check_llama_cpp(args.gguf)
    else:
        print("=" * 60)
        print("3. llama.cpp / GGUF smoke test  -- SKIPPED (no --gguf path given)")
        print("=" * 60)
        llama_ok, llama_tps = False, 0.0

    hf_ok, hf_tps = check_transformers_fallback(args.model)

    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    if llama_ok:
        print(f"Use llama.cpp/GGUF. ~{llama_tps:.1f} tok/s. Re-estimate "
              "the sweep timeline with this throughput.")
    elif hf_ok:
        print(f"llama.cpp not tested/available -- transformers fallback "
              f"works at ~{hf_tps:.1f} tok/s on {args.model}.")
    else:
        print("Neither stack worked. Debug step 3/4 output above.")


if __name__ == "__main__":
    main()
