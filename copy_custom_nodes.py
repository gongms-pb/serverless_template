import os
import random
import sys
from typing import Sequence, Mapping, Any, Union
import argparse
import json
import shutil
import inspect

def get_value_at_index(obj: Union[Sequence, Mapping], index: int) -> Any:
    """Returns the value at the given index of a sequence or mapping.

    If the object is a sequence (like list or string), returns the value at the given index.
    If the object is a mapping (like a dictionary), returns the value at the index-th key.

    Some return a dictionary, in these cases, we look for the "results" key

    Args:
        obj (Union[Sequence, Mapping]): The object to retrieve the value from.
        index (int): The index of the value to retrieve.

    Returns:
        Any: The value at the given index.

    Raises:
        IndexError: If the index is out of bounds for the object and the object is not a mapping.
    """
    try:
        return obj[index]
    except KeyError:
        return obj["result"][index]

def add_comfyui_directory_to_sys_path(path: str) -> None:
    """
    Add 'ComfyUI' to the sys.path
    """
    comfyui_path = path
    if comfyui_path is not None and os.path.isdir(comfyui_path):
        sys.path.append(comfyui_path)
        print(f"'{comfyui_path}' added to sys.path")

def import_custom_nodes() -> None:
    """Find all custom nodes in the custom_nodes folder and add those node objects to NODE_CLASS_MAPPINGS

    This function sets up a new asyncio event loop, initializes the PromptServer,
    creates a PromptQueue, and initializes the custom nodes.
    """
    import asyncio
    import execution
    from nodes import init_extra_nodes
    import server

    # Creating a new event loop and setting it as the default loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Creating an instance of PromptServer with the loop
    server_instance = server.PromptServer(loop)
    execution.PromptQueue(server_instance)

    # Initializing custom nodes
    init_extra_nodes()

def find_custom_nodes(json_path: str) -> list:
    """Find custom nodes in the JSON file and their corresponding directories.

    Args:
        json_path (str): Path to the JSON file.

    Returns:
        list: A list of custom nodes
    """
    from nodes import NODE_CLASS_MAPPINGS
    # Load the JSON file
    print(f"Looking for custom nodes in JSON: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = []

    marker_dir = "custom_nodes"
    for key, value in data.items():
        if isinstance(value, dict) and "class_type" in value:
            if value["class_type"] in NODE_CLASS_MAPPINGS:
                node = NODE_CLASS_MAPPINGS[value["class_type"]]
                node_file_path = inspect.getfile(node)
                parts = node_file_path.split(os.sep)

                # If the node is custom node, add it to the result
                if marker_dir in parts:
                    index = parts.index(marker_dir)
                    custom_node_name = parts[index + 1]
                    if custom_node_name not in result:
                        result.append(custom_node_name)
            else:
                print(f"Class type '{value['class_type']}' not found in NODE_CLASS_MAPPINGS")
    print(f"Custom nodes found in JSON ({len(result)}):")
    for name in sorted(result):
        print(f"  - {name}")
        
    return result

def copy_custom_nodes(custom_nodes: list, source_dir: str, target_dir: str) -> None:
    """Copy custom nodes from the source directory to the target directory.

    Args:
        custom_nodes (list): List of custom nodes to copy.
        source_dir (str): Source directory containing the custom nodes.
        target_dir (str): Target directory to copy the custom nodes to.
    """
    source_custom_nodes_dir = os.path.join(source_dir, "custom_nodes")
    target_custom_nodes_dir = os.path.join(target_dir, "custom_nodes")

    # Create target directory if it doesn't exist
    os.makedirs(target_custom_nodes_dir, exist_ok=True)

    for node in custom_nodes:
        src_dir = os.path.join(source_custom_nodes_dir, node)
        dst_dir = os.path.join(target_custom_nodes_dir, node)
        print(f"Copying {src_dir} to {dst_dir}")
        # Copy the directory and its contents
        if os.path.exists(src_dir):
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        else:
            print(f"Source directory {src_dir} does not exist. Skipping.")
    print("Custom nodes copied successfully.")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Copy custom nodes to the specified directory.")
    parser.add_argument("json_file", type=str, default="super_render_last.json", help="JSON file containing custom nodes filenames")
    parser.add_argument("--source_dir", type=str, default="/workspace/ComfyUI", help="Source ComfyUI directory containing custom nodes.")
    parser.add_argument("--target_dir", type=str, default="./ComfyUI", help="Target ComfyUI directory to copy custom nodes to.")
    args = parser.parse_args()

    print("Starting custom node file copy process...")
    json_path = args.json_file
    source_dir = args.source_dir
    target_dir = args.target_dir
    print(f"Source directory: {source_dir}")
    print(f"Target directory: {target_dir}")

    # Add the source ComfyUI directory to sys.path
    add_comfyui_directory_to_sys_path(source_dir)

    # Import custom nodes
    import_custom_nodes()

    # Find custom nodes in the JSON file
    custom_nodes = find_custom_nodes(json_path)
    if not custom_nodes:
        print("No custom nodes found in the JSON file.")
        return
    # Copy custom nodes to the target directory
    copy_custom_nodes(custom_nodes, source_dir, target_dir)

if __name__ == "__main__":
    main()
