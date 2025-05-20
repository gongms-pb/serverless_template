#!/usr/bin/env python3
import glob
import os
import re
from collections import defaultdict
from packaging import version, requirements
from packaging.utils import canonicalize_name

def parse_requirement_line(line):
    """
    주석이나 빈 줄을 건너뛰고, 패키지 이름과 버전 제약 조건(존재할 경우)을 추출합니다.
    패키지 이름은 canonicalize_name() 함수를 사용하여 정규화합니다.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # VCS/git 링크는 병합하지 않고 원본 라인 그대로 반환
    vcs_prefixes = ("git+", "http://", "https://", "svn+", "hg+", "bzr+")
    if line.startswith(vcs_prefixes):
        return (line, None)
    try:
        req = requirements.Requirement(line)
        # canonicalize_name()을 사용하면 "huggingface_hub"와 "huggingface-hub"가 동일하게 처리됩니다.
        return canonicalize_name(req.name), str(req.specifier)
    except Exception:
        # packaging을 통한 파싱이 안 될 경우 단순 정규 표현식 사용
        m = re.match(r"([\w\-]+)(.*)", line)
        if m:
            name = canonicalize_name(m.group(1))
            spec = m.group(2).strip()
            return name, spec
    return None

def compute_upper_bound_for_tilde(spec_str):
    """
    "~=" 연산자의 upper bound 를 계산합니다.
    예:
      - "~=1.4.5" → upper bound: "1.5.0"
      - "~=1.4"   → upper bound: "2.0"
    """
    ver = spec_str[2:].strip()
    parts = ver.split(".")
    if len(parts) == 1:
        upper = str(int(parts[0]) + 1)
    else:
        if len(parts) == 2:
            major = int(parts[0])
            upper = f"{major+1}.0"
        else:
            major = int(parts[0])
            minor = int(parts[1])
            upper = f"{major}.{minor+1}.0"
    return upper

def combine_specifiers(spec_list, package_name):
    """
    같은 패키지에 대한 여러 제약 조건(spec_list)을 하나로 병합합니다.
    
    [처리 순서]
    1. 빈 문자열 및 쉼표로 연결된 조건들을 개별 요소로 분리합니다.
    2. equality 제약 (==, ===)가 있다면,
       - 모두 같은 버전을 요구하면 해당 조건을 사용
       - 다르면 충돌 메시지를 출력하고 가장 최신 equality 제약을 선택
    3. equality 제약이 없으면 inequality (>=, >, <=, <, ~=) 조건을 각각 lower bound, upper bound로 분리하여
       - 모든 lower bound 중 최댓값과 upper bound 중 최솟값을 구한 뒤, 교집합이 가능하면 그 조건을 사용
       - 교집합이 불가능하면 충돌 메시지를 출력한 후 조건들 중 숫자상 최신 버전 조건을 선택합니다.
    4. 그 외 파싱되지 않는 조건들도 추가합니다.
    """
    # 빈 문자열 제거
    specs = [s.strip() for s in spec_list if s.strip()]
    if not specs:
        return ""
    
    # 쉼표로 연결된 조건들을 분리
    constraints = []
    for s in specs:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        constraints.extend(parts)
    
    # 1. equality 조건 처리 (==, ===)
    eq_specs = [s for s in constraints if s.startswith("==") or s.startswith("===")]
    if eq_specs:
        eq_versions = [s.lstrip("===").lstrip("==").strip() for s in eq_specs]
        if all(v == eq_versions[0] for v in eq_versions):
            return "==" + eq_versions[0]
        else:
            print(f"[Warning] {package_name}에 대해 equality 제약 조건이 충돌합니다: {eq_specs}. 가장 최신 조건으로 결정합니다.")
            highest = max(eq_versions, key=lambda x: version.parse(x))
            return "==" + highest

    # 2. inequality 조건 처리
    lower_bounds = []  # (operator, version)
    upper_bounds = []  # (operator, version)
    other_constraints = []  # 위 패턴에 맞지 않는 경우

    pattern = r"(>=|>|<=|<|~=)\s*(\S+)"
    for constraint in constraints:
        match = re.match(pattern, constraint)
        if match:
            op = match.group(1)
            ver = match.group(2)
            if op == "~=":
                lower_bounds.append((">=", ver))
                upper = compute_upper_bound_for_tilde(constraint)
                upper_bounds.append(("<", upper))
            elif op in (">", ">="):
                lower_bounds.append((op, ver))
            elif op in ("<", "<="):
                upper_bounds.append((op, ver))
            else:
                other_constraints.append(constraint)
        else:
            other_constraints.append(constraint)
    
    # 최적의 lower bound 결정 (가장 높은 버전)
    effective_lower = None
    effective_lower_op = None
    for op, ver in lower_bounds:
        if effective_lower is None or version.parse(ver) > version.parse(effective_lower):
            effective_lower = ver
            effective_lower_op = op
        elif version.parse(ver) == version.parse(effective_lower):
            if effective_lower_op == ">=" and op == ">":
                effective_lower_op = ">"
    
    # 최적의 upper bound 결정 (가장 낮은 버전)
    effective_upper = None
    effective_upper_op = None
    for op, ver in upper_bounds:
        if effective_upper is None or version.parse(ver) < version.parse(effective_upper):
            effective_upper = ver
            effective_upper_op = op
        elif version.parse(ver) == version.parse(effective_upper):
            if effective_upper_op == "<=" and op == "<":
                effective_upper_op = "<"
    
    # 2-1. lower와 upper bound 간의 충돌 여부 확인
    conflict = False
    if effective_lower and effective_upper:
        lower_val = version.parse(effective_lower)
        upper_val = version.parse(effective_upper)
        if lower_val > upper_val:
            conflict = True
        elif lower_val == upper_val:
            if effective_lower_op in (">") or effective_upper_op in ("<"):
                conflict = True

    if not conflict:
        combined = []
        if effective_lower:
            combined.append(f"{effective_lower_op}{effective_lower}")
        if effective_upper:
            combined.append(f"{effective_upper_op}{effective_upper}")
        combined.extend(other_constraints)
        return ",".join(combined)
    else:
        # 3. 충돌이 발생한 경우 – 모든 조건 중 숫자상 가장 최신 버전 조건 선택
        all_versions = []
        for s in constraints:
            m = re.search(r"(\d+(?:\.\d+)+)", s)
            if m:
                all_versions.append((s, version.parse(m.group(1))))
        if all_versions:
            best_spec, best_ver = max(all_versions, key=lambda x: x[1])
            print(f"[Warning] {package_name}에 대해 조건들이 충돌합니다: {constraints}. '{best_spec}'로 결정합니다.")
            return best_spec
        else:
            return ""

def main():
    # glob을 사용하여 병합할 requirements.txt 파일들을 모두 찾습니다.
    files = glob.glob("./ComfyUI/requirements.txt")
    files += glob.glob("./ComfyUI/custom_nodes/*/requirements.txt")
    print("병합할 파일 목록:")
    for f in files:
        print("  ", f)
    
    # 패키지별 제약 조건을 모읍니다.
    req_dict = defaultdict(list)
    vcs_lines = []
    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    parsed = parse_requirement_line(line)
                    if parsed:
                        pkg, spec = parsed
                        if spec is None:
                            # VCS/git 링크는 별도 저장
                            vcs_lines.append(pkg)
                        else:
                            req_dict[pkg].append(spec)
        except Exception as e:
            print(f"파일 {filepath} 처리 중 에러 발생: {e}")
    
    # 각 패키지별 조건 병합
    merged_lines = []
    for pkg, spec_list in sorted(req_dict.items()):
        combined_spec = combine_specifiers(spec_list, pkg)
        if combined_spec:
            line = f"{pkg}{combined_spec}"
        else:
            line = pkg
        merged_lines.append(line)
    # VCS/git 라인은 마지막에 추가
    merged_lines.extend(vcs_lines)
    
    # 최종 결과를 ./requirements.txt에 기록
    output_file = "./requirements.txt"
    try:
        with open(output_file, "w", encoding="utf-8") as out:
            out.write("\n".join(merged_lines))
        print(f"병합된 requirements.txt가 {output_file}에 생성되었습니다.")
    except Exception as e:
        print(f"출력 파일 작성 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
