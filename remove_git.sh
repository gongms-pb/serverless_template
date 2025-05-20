#!/bin/bash
# 삭제할 .git 디렉토리 확인하기
find ./ComfyUI/ -type d -name ".git"  
# .git 디렉토리 삭제하기
find ./ComfyUI/ -type d -name ".git" -exec rm -rf {} +
# .gitignore 파일 확인하기
find ./ComfyUI/ -type f -name ".gitignore"
# .gitignore 파일 삭제하기
find ./ComfyUI/ -type f -name ".gitignore" -exec rm -rf {} +