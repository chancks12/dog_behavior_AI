"""
preprocessing/keypoint_preprocessor.py
=======================================
AI Hub 반려동물 행동 데이터셋 키포인트 전처리 모듈

V1 (0-padding) vs V2 (선형 보간) 비교 및 전처리 실행

배경:
    AI Hub 데이터셋의 키포인트 CSV에는 특정 프레임에서
    관절이 탐지되지 않은 경우 0.0으로 기록되어 있음.
    V1에서 0으로 그대로 학습 시, 실제 관절 좌표(ex: 0.45)에서
    갑자기 원점(0.0)으로 튀는 비물리적 노이즈가 발생 → 정확도 53.93%

    V2에서 0.0을 NaN으로 치환 후 선형 보간 적용 시,
    앞뒤 프레임의 관절 좌표 사이를 부드럽게 보간 → 정확도 78.71% (+24.78%p)

데이터 구조 (AI Hub 강아지 행동 데이터셋):
    CSV 컬럼: frame_id, kp_0_x, kp_0_y, kp_1_x, kp_1_y, ..., kp_14_x, kp_14_y, label
    키포인트 수: 15개 (강아지 전용 pose 모델 기준)
    행동 클래스: 13개 (BODYLOWER, BODYSCRATCH, BODYSHAKE, FEETUP, FOOTUP,
                       HEADING, LYING, MOUNTING, SIT, TAILING, TAILLOW, TURN, WALKRUN)
"""

import os
import numpy as np
import pandas as pd
from pathlib import Path


# 행동 클래스
CLASSES = [
    "BODYLOWER", "BODYSCRATCH", "BODYSHAKE", "FEETUP", "FOOTUP",
    "HEADING", "LYING", "MOUNTING", "SIT", "TAILING",
    "TAILLOW", "TURN", "WALKRUN"
]

# 키포인트 컬럼 수 (15관절 × x,y = 30)
KEYPOINT_DIM = 30


def load_csv(filepath: str) -> pd.DataFrame:
    """AI Hub 키포인트 CSV 로드"""
    df = pd.read_csv(filepath)
    return df


def preprocess_v1_zero_padding(df: pd.DataFrame) -> np.ndarray:
    """
    V1: 0-padding 방식
    결측(0.0)을 그대로 유지 → 비물리적 노이즈 발생
    정확도: 53.93%
    """
    kp_cols = [c for c in df.columns if c.startswith("kp_")]
    return df[kp_cols].values.astype(np.float32)


def preprocess_v2_linear_interpolation(df: pd.DataFrame) -> np.ndarray:
    """
    V2: 선형 보간 방식
    0.0을 NaN으로 치환 후 앞뒤 프레임 사이를 선형 보간
    → 비물리적 노이즈 제거, 정확도: 78.71% (+24.78%p)
    """
    kp_cols = [c for c in df.columns if c.startswith("kp_")]
    kp_df = df[kp_cols].copy()

    # 0.0을 결측값(NaN)으로 치환
    kp_df.replace(0.0, np.nan, inplace=True)

    # 선형 보간: 각 컬럼(관절 좌표)을 프레임 순서 기준으로 보간
    kp_df.interpolate(method="linear", axis=0, inplace=True)

    # 보간 후에도 남아있는 NaN(앞뒤 모두 결측인 경우)은 0으로 대체
    kp_df.fillna(0.0, inplace=True)

    return kp_df.values.astype(np.float32)


def build_dataset(data_dir: str, use_interpolation: bool = True):
    """
    데이터셋 전체 빌드

    Args:
        data_dir: 클래스별 CSV가 담긴 루트 디렉토리
                  구조: data_dir/{CLASS_NAME}/*.csv
        use_interpolation: True → V2(선형 보간), False → V1(0-padding)

    Returns:
        X: np.ndarray (N, KEYPOINT_DIM)
        y: np.ndarray (N,) — 클래스 인덱스
    """
    X_list, y_list = [], []

    for label_idx, class_name in enumerate(CLASSES):
        class_dir = Path(data_dir) / class_name
        if not class_dir.exists():
            print(f"[Warning] 폴더 없음: {class_dir}")
            continue

        csv_files = list(class_dir.glob("*.csv"))
        print(f"[{class_name}] CSV {len(csv_files)}개 처리 중...")

        for csv_path in csv_files:
            try:
                df = load_csv(str(csv_path))

                if use_interpolation:
                    features = preprocess_v2_linear_interpolation(df)
                else:
                    features = preprocess_v1_zero_padding(df)

                labels = np.full(len(features), label_idx, dtype=np.int32)

                X_list.append(features)
                y_list.append(labels)

            except Exception as e:
                print(f"[Error] {csv_path.name}: {e}")
                continue

    if not X_list:
        raise ValueError(f"데이터를 찾을 수 없습니다: {data_dir}")

    X = np.vstack(X_list)
    y = np.concatenate(y_list)

    print(f"\n[Dataset] 총 샘플 수: {len(X)}, 클래스 수: {len(CLASSES)}")
    print(f"[Dataset] 전처리 방식: {'선형 보간 (V2)' if use_interpolation else '0-padding (V1)'}")

    return X, y


def compare_preprocessing(csv_path: str):
    """
    V1 vs V2 전처리 결과 비교 출력 (디버그용)
    비물리적 노이즈 발생 여부를 수치로 확인
    """
    df = load_csv(csv_path)
    kp_cols = [c for c in df.columns if c.startswith("kp_")]

    v1 = preprocess_v1_zero_padding(df)
    v2 = preprocess_v2_linear_interpolation(df)

    zero_count_v1 = (v1 == 0.0).sum()
    zero_count_v2 = (v2 == 0.0).sum()

    print(f"[V1 0-padding]  0.0 값 개수: {zero_count_v1} / {v1.size}")
    print(f"[V2 선형 보간] 0.0 값 개수: {zero_count_v2} / {v2.size}")
    print(f"→ 보간으로 제거된 비물리적 0: {zero_count_v1 - zero_count_v2}개")

    # 최대 좌표 점프(노이즈) 비교
    diff_v1 = np.abs(np.diff(v1, axis=0)).max()
    diff_v2 = np.abs(np.diff(v2, axis=0)).max()
    print(f"\n[V1] 최대 프레임 간 좌표 변화량: {diff_v1:.4f}")
    print(f"[V2] 최대 프레임 간 좌표 변화량: {diff_v2:.4f}")
    print(f"→ 노이즈 감소율: {(1 - diff_v2 / diff_v1) * 100:.1f}%")


if __name__ == "__main__":
    # 사용 예시
    # build_dataset("data/aihub_keypoints", use_interpolation=True)
    pass
