import os
import json
import shutil
from pathlib import Path
import argparse

MODEL_EXTENSIONS = {'.safetensors', '.pth', '.pt', '.bin', '.sft', '.ckpt', '.onnx'}

def extract_model_filenames(obj):
    filenames = set()
    if isinstance(obj, dict):
        for v in obj.values():
            filenames.update(extract_model_filenames(v))
    elif isinstance(obj, list):
        for item in obj:
            filenames.update(extract_model_filenames(item))
    elif isinstance(obj, str):
        ext = Path(obj).suffix
        if ext in MODEL_EXTENSIONS:
            filenames.add(obj)
    return filenames

def load_model_filenames(json_path):
    print(f"Loading model filenames from JSON: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    filenames = extract_model_filenames(data)
    print(f"Model filenames found in JSON ({len(filenames)}):")
    for name in sorted(filenames):
        print(f"  - {name}")
    return filenames

def find_files(root_dir, target_filenames):
    print(f"Searching for model files in: {root_dir}")
    found = []
    found_names = set()
    for dirpath, _, files in os.walk(root_dir):
        for fname in files:
            if fname in target_filenames and Path(fname).suffix in MODEL_EXTENSIONS:
                abs_path = os.path.join(dirpath, fname)
                found.append(abs_path)
                found_names.add(fname)
    print(f"Found {len(found)} matching files in source directory.")
    return found, found_names

def copy_files_to_output(found_files, source_dir, output_dir):
    print(f"Copying files to: {output_dir}")
    source_dir = os.path.abspath(source_dir)
    for src_path in found_files:
        rel_path = os.path.relpath(src_path, source_dir)
        dst_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        print(f"Copying: {src_path} -> {dst_path}")
        shutil.copy2(src_path, dst_path)
    print("Copying complete.")

def find_in_custom_nodes(custom_nodes_dir, target_filenames):
    print(f"Searching for missing model files in: {custom_nodes_dir}")
    found = []
    found_map = {}
    for dirpath, _, files in os.walk(custom_nodes_dir):
        for fname in files:
            if fname in target_filenames and Path(fname).suffix in MODEL_EXTENSIONS:
                abs_path = os.path.join(dirpath, fname)
                found.append(abs_path)
                # 경로는 custom_nodes 하위 경로로 기록
                rel_path = os.path.relpath(abs_path, custom_nodes_dir)
                found_map[fname] = rel_path
    print(f"Found {len(found)} missing files in custom_nodes.")
    return found, found_map

def main():
    parser = argparse.ArgumentParser(description="Copy model files listed in a JSON from source to target directory.")
    parser.add_argument("json_file", help="JSON file containing model filenames")
    parser.add_argument("--source_dir", default="/workspace/ComfyUI", help="Source ComfyUI directory")
    parser.add_argument("--target_dir", default="./ComfyUI", help="Target ComfyUI directory to copy models into")
    args = parser.parse_args()

    print("Starting model file copy process...")
    json_path = args.json_file
    source_dir = args.source_dir
    target_dir = args.target_dir
    print(f"Source directory: {source_dir}")
    print(f"Target directory: {target_dir}")
    source_models_dir = os.path.join(source_dir, "models")
    target_models_dir = os.path.join(target_dir, "models")

    model_filenames = load_model_filenames(json_path)
    found_files, found_names = find_files(source_models_dir, model_filenames)
    missing_files = sorted(model_filenames - found_names)
    if missing_files:
        print("\nFiles listed in JSON but NOT found in source directory:")
        for name in missing_files:
            print(f"  - {name}")

        # custom_nodes에서 추가로 찾기
        custom_nodes_dir = os.path.join(source_dir, "custom_nodes")
        custom_found_files, custom_found_map = find_in_custom_nodes(custom_nodes_dir, set(missing_files))
        if custom_found_files:
            # target/models에 복사
            for src_path in custom_found_files:
                dst_path = os.path.join(target_models_dir, os.path.basename(src_path))
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                print(f"Copying (custom_nodes): {src_path} -> {dst_path}")
                shutil.copy2(src_path, dst_path)
            # 매핑 정보 저장
            map_json_path = os.path.join(target_models_dir, "missing_models_map.json")
            with open(map_json_path, "w", encoding="utf-8") as f:
                json.dump(custom_found_map, f, indent=2, ensure_ascii=False)
            print(f"Saved missing models map to {map_json_path}")

        # custom_nodes에서도 못 찾은 파일 출력
        still_missing = sorted(set(missing_files) - set(custom_found_map.keys()))
        if still_missing:
            print("\nFiles NOT found in custom_nodes either:")
            for name in still_missing:
                print(f"  - {name}")

    if not found_files and not (missing_files and custom_found_files):
        print("No matching files found in source directory.")
        return

    copy_files_to_output(found_files, source_models_dir, target_models_dir)
    print("All done.")

if __name__ == "__main__":
    main()
