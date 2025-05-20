#!/bin/bash
# Script to set up Git repositories for Runpod Serverless Endpoint that runs ComfyUI with custom nodes and models

echo "Setting up Git repositories for Serverless Endpoint..."

############################################################
# Edit this section
# Set variables
SOURCE_COMFYUI_DIR="/workspace/ComfyUI"
WORKFLOW_JSON_FILE="super_render_last.json"
HUGGINGFACE_TOKEN=""
HUGGINGFACE_USERNAME=""
PROJECT_NAME="serverless_template"
############################################################

PROJECT_DIR=$(pwd)

# Print the variables
echo "Source ComfyUI directory: $SOURCE_COMFYUI_DIR"
echo "Workflow JSON path: $WORKFLOW_JSON_FILE"
echo "Hugging Face token: $HUGGINGFACE_TOKEN"
echo "Hugging Face username: $HUGGINGFACE_USERNAME"
echo "Project name: $PROJECT_NAME"

# Clone ComfyUI repository
echo "Cloning ComfyUI repository..."
git clone https://github.com/comfyanonymous/ComfyUI.git

# Check if conda is installed
if ! command -v conda &> /dev/null
then
    echo "Conda could not be found. Please install Anaconda or Miniconda."
    exit 1
fi

# Activate original comfyui environment
echo "Activating original ComfyUI environment..."
source /workspace/miniconda3/bin/activate "comfyui"

# Copy custom nodes from source ComfyUI directory
echo "Copying custom nodes..."
python copy_custom_nodes.py "$WORKFLOW_JSON_FILE" --source_dir "$SOURCE_COMFYUI_DIR" --target_dir "./ComfyUI"

# Merge requirements.txt files of ComfyUI and custom nodes
echo "Merging requirements.txt files..."
python merge_requirements.py

# Remove .git directory under ComfyUI and custom_nodes
echo "Removing .git directories..."
bash remove_git.sh

# Convert workflow JSON to python code
echo "Converting workflow JSON to python code..."
cp comfyui_to_python_sl.py "$SOURCE_COMFYUI_DIR/custom_nodes/ComfyUI-to-Python-Extension/comfyui_to_python_sl.py"
cd "$SOURCE_COMFYUI_DIR"/custom_nodes/ComfyUI-to-Python-Extension
python comfyui_to_python_sl.py --input_file "$PROJECT_DIR/$WORKFLOW_JSON_FILE" --output_file "$PROJECT_DIR/ComfyUI/workflow.py" --queue_size 1
rm comfyui_to_python_sl.py
cd "$PROJECT_DIR"

# Check if the conda environment already exists
if conda info --envs | grep -q "^$PROJECT_NAME"; then
    echo "Conda environment '$PROJECT_NAME' already exists."
else
    # Create a new conda environment with python 3.12
    echo "Creating conda environment '$PROJECT_NAME'..."
    conda create -n "$PROJECT_NAME" python=3.12 -y
fi

# Activate the new environment
echo "Activating conda environment '$PROJECT_NAME'..."
source /workspace/miniconda3/bin/activate "$PROJECT_NAME"
# Install git LFS
conda install git-lfs -y
# Initialize git LFS
git lfs install
# Install huggingface_hub
pip install huggingface_hub[hf_transfer] 

# Install torch and other dependencies
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install xformers --index-url https://download.pytorch.org/whl/cu124
pip install runpod requests

# Install requirements of ComfyUI and custom nodes
echo "Installing requirements of ComfyUI and custom nodes..."
pip install -r requirements.txt

# Copy models from source ComfyUI directory
python copy_models.py "$WORKFLOW_JSON_FILE" --source_dir "$SOURCE_COMFYUI_DIR" --target_dir "./ComfyUI"

# Create huggingface repository and push models
echo "Creating Hugging Face repository..."
huggingface-cli login --token "$HUGGINGFACE_TOKEN"
huggingface-cli repo create "$PROJECT_NAME" -y
echo "Pushing models to Hugging Face..."
HF_HUB_ENABLE_HF_TRANSFER=1 huggingface-cli upload-large-folder --repo-type=model "$HUGGINGFACE_USERNAME/$PROJECT_NAME" "./ComfyUI/models" --num-workers 16