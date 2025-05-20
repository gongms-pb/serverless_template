Template repository for serverless
================
ComfyUI workflow 를 Serverless endpoint 로 배포하기 위한 github repository 를 자동으로 생성하기 위한 템플릿

Requirements
----------------
- Workflow API JSON (ComfyUI to Python)
- 해당 Workflow 를 실행 가능한 ComfyUI (Custome nodes, models, conda environment 모두 포함)

How to run auto setup
----------------
1. Fork this repository and clone it
2. Put workflow JSON file in top directory
3. Edit variables in git_setup.sh
4. Run git_setup.sh

Todo after setup
----------------
1. Add and edit workflow python code
2. Edit rp_handler.py
3. Edit Dockerfile
4. Edit test_input.json
5. Add default input (images, ...) 

Cautions
----------------
- 기존 ComfyUI conda environment 이름은 "comfyui" 로 가정
- 모델 크기에 따라서 Huggingface repo upload 실패할 수도 있음. 이럴 땐 공식 모델 링크 찾아서 다운.