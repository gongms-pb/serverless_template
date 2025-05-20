import os
import json
import shutil
from pathlib import Path
import argparse

def move_models_from_models_to_custom_nodes(target_dir):
    models_dir = os.path.join(target_dir, "models")
    custom_nodes_dir = os.path.join(target_dir, "custom_nodes")
    map_json_path = os.path.join(models_dir, "missing_models_map.json")

    if not os.path.exists(map_json_path):
        print(f"No missing_models_map.json found at {map_json_path}. Nothing to move.")
        return

    with open(map_json_path, "r", encoding="utf-8") as f:
        missing_map = json.load(f)

    moved = []
    for fname, rel_custom_path in missing_map.items():
        src_path = os.path.join(models_dir, fname)
        dst_path = os.path.join(custom_nodes_dir, rel_custom_path)
        if os.path.exists(src_path):
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            print(f"Moving: {src_path} -> {dst_path}")
            shutil.move(src_path, dst_path)
            moved.append((src_path, dst_path))
        else:
            print(f"File not found in models dir, skipping: {src_path}")

    if moved:
        print(f"\nMoved {len(moved)} files from models to custom_nodes.")
        print("Moved files list:")
        for src, dst in moved:
            print(f"  {src} -> {dst}")
    else:
        print("No files moved.")

def main():
    parser = argparse.ArgumentParser(description="Move model files from models/ to custom_nodes/ based on missing_models_map.json")
    parser.add_argument("--target_dir", default="./ComfyUI", help="Target ComfyUI directory")
    args = parser.parse_args()
    move_models_from_models_to_custom_nodes(args.target_dir)

if __name__ == "__main__":
    main()
