import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
import cv2
import math

# 모델 경로 지정
model_path_1 = '../models/selfie_multiclass_256x256.tflite'
model_path_2 = '../models/face_landmarker.task'

# Mediapipe 모델 옵션 설정
BaseOptions = mp.tasks.BaseOptions
ImageSegmenter = mp.tasks.vision.ImageSegmenter
ImageSegmenterOptions = mp.tasks.vision.ImageSegmenterOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# ImageSegmenter 옵션 정의
is_options = ImageSegmenterOptions(
    base_options=BaseOptions(model_asset_path=model_path_1),
    running_mode=VisionRunningMode.IMAGE,
    output_category_mask=True)

# face_landmarker 옵션 정의
fl_options = FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=model_path_2),
    running_mode=VisionRunningMode.IMAGE)


# 카테고리 정의
category = ["background", "hair", "body-skin", "face-skin", "clothes", "others"]

# 랜드마크 인덱스 정의
IRIS_LANDMARKS = {
    'left': [468, 469, 470, 471, 472],
    'right': [473, 474, 475, 476, 477]
}
EYEBROW_LANDMARKS = {
    'left':[70, 63, 105, 66, 107, 55, 65, 52, 53, 46],
    'right':[336, 296, 334, 293, 300, 276, 283, 282, 295, 285]
}
LIPS_LANDMARKS = {
    'upper' : [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308],
    'lower' : [375, 321, 405, 314, 17, 84, 181, 91, 146, 61, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]
}

# 평균 색상 추출 함수
def extract_average_color(image, mask):
    masked_image = cv2.bitwise_and(image, image, mask=mask)
    mean_color = cv2.mean(masked_image, mask=mask)[:3]
    return tuple(int(round(c)) for c in mean_color)

#다각형 마스크 생성 함수
def create_polygon_mask(image, landmark_indices):
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    pts = np.array([(int(landmark.x * image.shape[1]), int(landmark.y * image.shape[0])) for landmark in landmark_indices], dtype=np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask

#홍채 반지름 계산 함수
def calculate_iris_radius(iris_landmarks, image_shape):
    image_width, image_height = image_shape[1], image_shape[0]
    center = iris_landmarks[0]
    radii = [
        math.hypot((center.x - point.x) * image_width, (center.y - point.y) * image_height)
        for point in iris_landmarks[1:]
    ]
    return np.mean(radii)

#홍채 마스크 생성 함수
def create_iris_mask(image, iris_landmarks):
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    iris_radius = calculate_iris_radius(iris_landmarks, image.shape)
    iris_center = (int(iris_landmarks[0].x * image.shape[1]), int(iris_landmarks[0].y * image.shape[0]))
    cv2.circle(mask, iris_center, int(iris_radius), color=(255), thickness=-1)
    return mask


with ImageSegmenter.create_from_options(is_options) as segmenter, FaceLandmarker.create_from_options(fl_options) as landmarker:

    # 이미지 불러오기
    mp_image = mp.Image.create_from_file('../image/sample2.png')
    numpy_image = mp_image.numpy_view()

    # 이미지 분할 및 랜드마크 검출
    segmented_masks = segmenter.segment(mp_image)
    face_landmarker_result = landmarker.detect(mp_image)

    # category_mask 속성
    category_mask = segmented_masks.category_mask
    category_mask_np = category_mask.numpy_view()

    # 카테고리 별 마스크 생성
    hair_mask = np.where(category_mask_np == 1, 255, 0).astype(np.uint8)
    body_skin_mask = np.where(category_mask_np == 2, 255, 0).astype(np.uint8)
    face_skin_mask = np.where(category_mask_np == 3, 255, 0).astype(np.uint8)
    clothes_mask = np.where(category_mask_np == 4, 255, 0).astype(np.uint8)

    # body + face 마스크
    skin_mask = cv2.bitwise_or(body_skin_mask, face_skin_mask)

    # 평균 색상 추출
    average_hair_color = extract_average_color(numpy_image, hair_mask)
    average_skin_color_sum = extract_average_color(numpy_image, skin_mask)
    average_clothes_color = extract_average_color(numpy_image, clothes_mask)

    # 예외처리 -> 검출 결과 확인
    if face_landmarker_result.face_landmarks:
        # 첫번째 얼굴의 랜드마크
        face_landmarks = face_landmarker_result.face_landmarks[0]

        # 랜드마크 포인트 리스트 생성
        left_iris_points = [face_landmarks[i] for i in IRIS_LANDMARKS['left']]
        right_iris_points = [face_landmarks[i] for i in IRIS_LANDMARKS['right']]
        left_eyebrow_points = [face_landmarks[i] for i in EYEBROW_LANDMARKS['left']]
        right_eyebrow_points = [face_landmarks[i] for i in EYEBROW_LANDMARKS['right']]
        upper_lip_points = [face_landmarks[i] for i in LIPS_LANDMARKS['upper']]
        lower_lip_points = [face_landmarks[i] for i in LIPS_LANDMARKS['lower']]

        # 마스크 생성
        left_iris_mask = create_iris_mask(numpy_image, left_iris_points)
        right_iris_mask = create_iris_mask(numpy_image, right_iris_points)
        left_eyebrow_mask = create_polygon_mask(numpy_image, left_eyebrow_points)
        right_eyebrow_mask = create_polygon_mask(numpy_image, right_eyebrow_points)
        upper_lip_mask = create_polygon_mask(numpy_image, upper_lip_points)
        lower_lip_mask = create_polygon_mask(numpy_image, lower_lip_points)

        iris_mask = cv2.bitwise_or(left_iris_mask, right_iris_mask)
        eyebrows_mask = cv2.bitwise_or(left_eyebrow_mask, right_eyebrow_mask)
        lips_mask = cv2.bitwise_or(upper_lip_mask, lower_lip_mask)

        # 평균 색상 추출
        average_iris_color = extract_average_color(numpy_image, iris_mask)
        average_eyebrows_color = extract_average_color(numpy_image, eyebrows_mask)
        average_lips_color = extract_average_color(numpy_image, lips_mask)

        # 추출된 색상 값 출력
        print(f"Hair: {average_hair_color}")
        print(f"Skin_sum:{average_skin_color_sum}")
        print(f"clothes: {average_clothes_color}")
        print(f"Iris Color: {average_iris_color}")
        print(f"Eyebrows Average Color: {average_eyebrows_color}")
        print(f"Lips Average Color: {average_lips_color}")

    else:
        print("No face landmarks detected.")