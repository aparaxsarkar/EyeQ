from __future__ import annotations

import math
import time
from itertools import combinations
from typing import Any

import numpy as np
from ultralytics import YOLO

from config import get_settings


class PoseDetector:
    NOSE = 0
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    RAPID_MOTION_KEYPOINTS = (NOSE, LEFT_ELBOW, RIGHT_ELBOW, LEFT_WRIST, RIGHT_WRIST)

    def __init__(self, model_name: str = "yolov8n-pose.pt") -> None:
        self.settings = get_settings()
        self.model = YOLO(model_name)
        self.next_person_id = 1
        self.previous_centroids: dict[int, tuple[float, float]] = {}
        self.previous_keypoints: dict[int, np.ndarray] = {}
        self.last_interaction_timestamp: float | None = None
        self.single_person_started_at: float | None = None
        self.last_flag_reason: str = "monitoring"
        self.last_primary_person_id: int | None = None
        self.last_aggressor_candidate_id: int | None = None

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        results = self.model(frame, verbose=False)
        if not results:
            self.previous_centroids = {}
            self.last_primary_person_id = None
            self.last_aggressor_candidate_id = None
            return []

        result = results[0]
        boxes = result.boxes
        keypoints = result.keypoints
        if boxes is None or keypoints is None or boxes.xyxy is None or keypoints.xy is None:
            self.previous_centroids = {}
            return []

        boxes_xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones(len(boxes_xyxy))
        keypoints_xy = keypoints.xy.cpu().numpy()

        persons: list[dict[str, Any]] = []
        for bbox, confidence, kp in zip(boxes_xyxy, confidences, keypoints_xy):
            centroid = self._bbox_centroid(bbox)
            persons.append(
                {
                    "id": None,
                    "bbox": bbox.astype(float).tolist(),
                    "centroid": centroid,
                    "keypoints": kp.astype(float).tolist(),
                    "confidence": float(confidence),
                }
            )

        persons = self._assign_ids(persons)
        self._assign_roles(persons, frame.shape[:2])
        return persons

    def is_interaction_flagged(
        self,
        persons: list[dict[str, Any]],
        prev_persons: list[dict[str, Any]] | None = None,
        global_motion_vector: tuple[float, float] = (0.0, 0.0),
    ) -> bool:
        now = time.time()
        self.last_flag_reason = "monitoring"

        if len(persons) >= 2:
            self.last_interaction_timestamp = now
            self.single_person_started_at = None
            interaction_reason = self._interaction_reason(
                persons,
                prev_persons or [],
                global_motion_vector=global_motion_vector,
            )
            if interaction_reason:
                self.last_flag_reason = interaction_reason
                self._update_previous_keypoints(persons)
                return True
        elif len(persons) == 1:
            if self.single_person_started_at is None:
                self.single_person_started_at = now
            if now - self.single_person_started_at > self.settings.neglect_timeout_seconds:
                self.last_flag_reason = "possible_neglect_caretaker_absent"
                self._update_previous_keypoints(persons)
                return True
        else:
            self.single_person_started_at = None

        self._update_previous_keypoints(persons)
        return False

    def _assign_ids(self, persons: list[dict[str, Any]]) -> list[dict[str, Any]]:
        matched_previous: set[int] = set()
        new_centroids: dict[int, tuple[float, float]] = {}

        for person in persons:
            centroid = person["centroid"]
            best_id: int | None = None
            best_distance = float("inf")
            for person_id, previous_centroid in self.previous_centroids.items():
                if person_id in matched_previous:
                    continue
                distance = self._distance(centroid, previous_centroid)
                if distance < best_distance and distance < 120:
                    best_id = person_id
                    best_distance = distance

            if best_id is None:
                best_id = self.next_person_id
                self.next_person_id += 1

            person["id"] = best_id
            matched_previous.add(best_id)
            new_centroids[best_id] = centroid

        self.previous_centroids = new_centroids
        return persons

    def _interaction_reason(
        self,
        persons: list[dict[str, Any]],
        prev_persons: list[dict[str, Any]],
        *,
        global_motion_vector: tuple[float, float],
    ) -> str | None:
        prev_keypoint_map = self._build_prev_keypoint_map(prev_persons)
        max_area = max((self._bbox_area(person["bbox"]) for person in persons), default=0.0)
        viable_persons = [
            person
            for person in persons
            if self._person_is_viable_interaction_target(person, max_area=max_area)
        ]
        if len(viable_persons) < 2:
            return None

        primary_person = self._select_primary_person(viable_persons)
        if primary_person is None:
            return None
        candidate_people = self._select_candidate_people(primary_person, viable_persons)
        if not candidate_people:
            return None

        for first, second in ((primary_person, candidate) for candidate in candidate_people):
            if not self._pair_is_viable_interaction(first, second, max_area=max_area):
                continue
            if self._bbox_gap_distance(first["bbox"], second["bbox"]) > self.settings.proximity_threshold_px:
                continue

            strike_reason = self._strike_contact_reason(
                first,
                second,
                prev_keypoint_map,
                global_motion_vector=global_motion_vector,
            )
            if strike_reason:
                return strike_reason

            for candidate in (first, second):
                previous_keypoints = self.previous_keypoints.get(candidate["id"])
                if previous_keypoints is None:
                    previous_keypoints = prev_keypoint_map.get(candidate["id"])
                if previous_keypoints is None:
                    continue

                current_keypoints = np.asarray(candidate["keypoints"], dtype=float)
                motion_offset = np.asarray(global_motion_vector, dtype=float)
                speeds = np.linalg.norm(current_keypoints - previous_keypoints - motion_offset, axis=1)
                rapid_joint_count = sum(
                    1
                    for index in self.RAPID_MOTION_KEYPOINTS
                    if index < len(speeds) and speeds[index] > self.settings.keypoint_velocity_threshold
                )
                if rapid_joint_count >= self.settings.rapid_motion_joint_count_threshold:
                    return "rapid_motion_near_dependent"
        return None

    def _strike_contact_reason(
        self,
        first: dict[str, Any],
        second: dict[str, Any],
        prev_keypoint_map: dict[int, np.ndarray],
        *,
        global_motion_vector: tuple[float, float],
    ) -> str | None:
        for aggressor, target in ((first, second), (second, first)):
            previous_keypoints = self.previous_keypoints.get(aggressor["id"])
            if previous_keypoints is None:
                previous_keypoints = prev_keypoint_map.get(aggressor["id"])
            if previous_keypoints is None:
                continue

            current_keypoints = np.asarray(aggressor["keypoints"], dtype=float)
            wrist_indices = (self.LEFT_WRIST, self.RIGHT_WRIST)
            elbow_indices = (self.LEFT_ELBOW, self.RIGHT_ELBOW)
            target_points = self._target_contact_points(target)

            for wrist_index, elbow_index in zip(wrist_indices, elbow_indices):
                previous_wrist_point = previous_keypoints[wrist_index]
                wrist_speed = self._point_speed(
                    current_keypoints,
                    previous_keypoints,
                    wrist_index,
                    motion_offset=global_motion_vector,
                )
                elbow_speed = self._point_speed(
                    current_keypoints,
                    previous_keypoints,
                    elbow_index,
                    motion_offset=global_motion_vector,
                )
                if wrist_speed < self.settings.strike_velocity_threshold and elbow_speed < self.settings.keypoint_velocity_threshold:
                    continue

                wrist_point = current_keypoints[wrist_index]
                if not self._is_point_valid(wrist_point):
                    continue
                if not self._is_point_valid(previous_wrist_point):
                    continue

                previous_distance = self._min_distance_to_targets(previous_wrist_point, target_points)
                current_distance = self._min_distance_to_targets(wrist_point, target_points)
                if previous_distance - current_distance < self.settings.strike_approach_delta_px:
                    continue

                if self._point_hits_target(wrist_point, target["bbox"], target_points):
                    return "possible_strike_contact"
        return None

    def _target_contact_points(self, person: dict[str, Any]) -> list[np.ndarray]:
        keypoints = np.asarray(person["keypoints"], dtype=float)
        bbox = person["bbox"]
        x1, y1, x2, y2 = bbox
        mid_x = (x1 + x2) / 2
        upper_torso_y = y1 + (y2 - y1) * 0.35
        torso_y = y1 + (y2 - y1) * 0.5

        points = [np.array([mid_x, upper_torso_y]), np.array([mid_x, torso_y])]
        for index in (self.NOSE, self.LEFT_HIP, self.RIGHT_HIP):
            point = keypoints[index]
            if self._is_point_valid(point):
                points.append(point)
        return points

    def _point_hits_target(
        self,
        point: np.ndarray,
        target_bbox: list[float],
        target_points: list[np.ndarray],
    ) -> bool:
        x1, y1, x2, y2 = target_bbox
        padding = self.settings.strike_contact_threshold_px * 0.25
        if x1 - padding <= point[0] <= x2 + padding and y1 - padding <= point[1] <= y2 + padding:
            return True
        return any(
            np.linalg.norm(point - target_point) <= self.settings.strike_contact_threshold_px
            for target_point in target_points
        )

    def _pair_is_viable_interaction(self, first: dict[str, Any], second: dict[str, Any], *, max_area: float) -> bool:
        if not self._person_is_viable_interaction_target(first, max_area=max_area):
            return False
        if not self._person_is_viable_interaction_target(second, max_area=max_area):
            return False

        first_area = self._bbox_area(first["bbox"])
        second_area = self._bbox_area(second["bbox"])
        smaller_area = max(min(first_area, second_area), 1.0)
        larger_area = max(first_area, second_area)
        if larger_area / smaller_area > self.settings.interaction_max_area_ratio:
            return False

        if self._vertical_overlap(first["bbox"], second["bbox"]) < self.settings.interaction_min_vertical_overlap_px:
            return False
        return True

    def _assign_roles(self, persons: list[dict[str, Any]], frame_shape: tuple[int, int]) -> None:
        if not persons:
            self.last_primary_person_id = None
            self.last_aggressor_candidate_id = None
            return

        frame_height, frame_width = frame_shape
        max_area = max((self._bbox_area(person["bbox"]) for person in persons), default=0.0)
        viable_persons = [
            person
            for person in persons
            if self._person_is_viable_interaction_target(person, max_area=max_area)
        ]
        primary_person = self._select_primary_person(viable_persons, frame_width=frame_width, frame_height=frame_height)
        candidate_people = (
            self._select_candidate_people(primary_person, viable_persons, frame_width=frame_width)
            if primary_person is not None
            else []
        )
        candidate_person = candidate_people[0] if candidate_people else None

        self.last_primary_person_id = primary_person["id"] if primary_person else None
        self.last_aggressor_candidate_id = candidate_person["id"] if candidate_person else None

        for person in persons:
            role = "bystander"
            if primary_person and person["id"] == primary_person["id"]:
                role = "subject"
            elif candidate_person and person["id"] == candidate_person["id"]:
                role = "candidate"
            person["role"] = role

    def _select_primary_person(
        self,
        viable_persons: list[dict[str, Any]],
        *,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> dict[str, Any] | None:
        if not viable_persons:
            return None

        max_area = max((self._bbox_area(person["bbox"]) for person in viable_persons), default=1.0)

        def score(person: dict[str, Any]) -> float:
            bbox = person["bbox"]
            area_score = self._bbox_area(bbox) / max_area
            center_score = 0.0
            if frame_width and frame_height:
                centroid_x, centroid_y = person["centroid"]
                dx = abs(centroid_x - frame_width / 2) / max(frame_width / 2, 1)
                dy = abs(centroid_y - frame_height / 2) / max(frame_height / 2, 1)
                center_score = max(0.0, 1.0 - (dx * 0.7 + dy * 0.3))
            persistence_bonus = 0.22 if person.get("id") == self.last_primary_person_id else 0.0
            return area_score * 0.6 + center_score * 0.4 + persistence_bonus

        return max(viable_persons, key=score)

    def _select_candidate_people(
        self,
        primary_person: dict[str, Any] | None,
        viable_persons: list[dict[str, Any]],
        *,
        frame_width: int | None = None,
    ) -> list[dict[str, Any]]:
        if primary_person is None:
            return []

        candidates = [person for person in viable_persons if person["id"] != primary_person["id"]]
        if not candidates:
            return []

        primary_bbox = primary_person["bbox"]
        primary_area = max(self._bbox_area(primary_bbox), 1.0)

        def score(person: dict[str, Any]) -> float:
            gap = self._bbox_gap_distance(primary_bbox, person["bbox"])
            gap_score = max(0.0, 1.0 - gap / max(self.settings.proximity_threshold_px * 1.5, 1))
            area_ratio = min(self._bbox_area(person["bbox"]) / primary_area, primary_area / max(self._bbox_area(person["bbox"]), 1.0))
            overlap_score = min(
                self._vertical_overlap(primary_bbox, person["bbox"]) / max(self._bbox_height(primary_bbox), 1.0),
                1.0,
            )
            lateral_score = 0.0
            if frame_width:
                primary_cx, _ = primary_person["centroid"]
                candidate_cx, _ = person["centroid"]
                lateral_score = min(abs(candidate_cx - primary_cx) / max(frame_width * 0.28, 1.0), 1.0)
            persistence_bonus = 0.18 if person.get("id") == self.last_aggressor_candidate_id else 0.0
            return gap_score * 0.45 + area_ratio * 0.2 + overlap_score * 0.2 + lateral_score * 0.15 + persistence_bonus

        ranked_candidates = sorted(candidates, key=score, reverse=True)
        limit = max(self.settings.interaction_top_person_count - 1, 1)
        return ranked_candidates[:limit]

    def _person_is_viable_interaction_target(self, person: dict[str, Any], *, max_area: float) -> bool:
        bbox = person["bbox"]
        if float(person.get("confidence", 0.0)) < self.settings.detection_confidence_threshold:
            return False
        person_area = self._bbox_area(bbox)
        if max_area > 0:
            relative_area_percent = (person_area / max_area) * 100.0
            if relative_area_percent < self.settings.interaction_min_relative_area_percent:
                return False
        return (
            self._bbox_height(bbox) >= self.settings.interaction_min_bbox_height_px
            and person_area >= self.settings.interaction_min_bbox_area_px
        )

    @staticmethod
    def _min_distance_to_targets(point: np.ndarray, target_points: list[np.ndarray]) -> float:
        if not target_points:
            return float("inf")
        return min(float(np.linalg.norm(point - target_point)) for target_point in target_points)

    @staticmethod
    def _point_speed(
        current_keypoints: np.ndarray,
        previous_keypoints: np.ndarray,
        index: int,
        motion_offset: tuple[float, float] = (0.0, 0.0),
    ) -> float:
        current_point = current_keypoints[index]
        previous_point = previous_keypoints[index]
        if not PoseDetector._is_point_valid(current_point) or not PoseDetector._is_point_valid(previous_point):
            return 0.0
        return float(np.linalg.norm(current_point - previous_point - np.asarray(motion_offset, dtype=float)))

    @staticmethod
    def _is_point_valid(point: np.ndarray) -> bool:
        return bool(point.shape[0] >= 2 and point[0] > 0 and point[1] > 0)

    @staticmethod
    def _build_prev_keypoint_map(prev_persons: list[dict[str, Any]]) -> dict[int, np.ndarray]:
        mapped: dict[int, np.ndarray] = {}
        for person in prev_persons:
            person_id = person.get("id")
            if person_id is None:
                continue
            mapped[person_id] = np.asarray(person.get("keypoints", []), dtype=float)
        return mapped

    def _update_previous_keypoints(self, persons: list[dict[str, Any]]) -> None:
        self.previous_keypoints = {
            int(person["id"]): np.asarray(person["keypoints"], dtype=float)
            for person in persons
            if person.get("id") is not None
        }

    @staticmethod
    def _bbox_centroid(bbox: np.ndarray) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @staticmethod
    def _bbox_height(bbox: list[float] | np.ndarray) -> float:
        return float(max(float(bbox[3]) - float(bbox[1]), 0.0))

    @staticmethod
    def _bbox_area(bbox: list[float] | np.ndarray) -> float:
        width = max(float(bbox[2]) - float(bbox[0]), 0.0)
        height = max(float(bbox[3]) - float(bbox[1]), 0.0)
        return width * height

    @staticmethod
    def _bbox_gap_distance(first_bbox: list[float] | np.ndarray, second_bbox: list[float] | np.ndarray) -> float:
        first_x1, first_y1, first_x2, first_y2 = map(float, first_bbox)
        second_x1, second_y1, second_x2, second_y2 = map(float, second_bbox)

        horizontal_gap = max(second_x1 - first_x2, first_x1 - second_x2, 0.0)
        vertical_gap = max(second_y1 - first_y2, first_y1 - second_y2, 0.0)
        return math.hypot(horizontal_gap, vertical_gap)

    @staticmethod
    def _vertical_overlap(first_bbox: list[float] | np.ndarray, second_bbox: list[float] | np.ndarray) -> float:
        top = max(float(first_bbox[1]), float(second_bbox[1]))
        bottom = min(float(first_bbox[3]), float(second_bbox[3]))
        return max(bottom - top, 0.0)

    @staticmethod
    def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.dist(a, b)
