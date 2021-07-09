import cv2
import numpy as np
from math import floor
from pose_utils.pipelines import get_user_config, AsyncPipeline
from pose_utils import models
from openvino.inference_engine import IECore


def draw_poses(poses, frame):
    for pose in poses:
        points = pose[:, :2].astype(np.int32)
        # Draw joints.
        for p in points:
            cv2.circle(frame, tuple(p), 1, (0, 255, 0), 2)


def launch_detection_on_capture(capture, args):
    plugin_config = get_user_config(args["device"], '', None)
    ie = IECore()

    # prepare model params
    ret, frame = capture.read()
    if not ret:
        raise IOError('Can not read frame!')

    aspect_ratio = frame.shape[1] / frame.shape[0]
    if aspect_ratio >= 1:
        target_size = floor(frame.shape[0] * args["net_input_width"] / frame.shape[1])
    else:
        target_size = args["net_input_width"]

    model = models.HpeAssociativeEmbedding(ie, args["model_path"],
                                           aspect_ratio=aspect_ratio,
                                           target_size=target_size, prob_threshold=0.1)
    hpe_pipeline = AsyncPipeline(ie, model, plugin_config, device=args["device"], max_num_requests=1)

    # cv2.resize() takes (width, height) as new size,
    # but img.shape has (height, width) format
    net_input_size = (model.w, model.h)
    show_frame_size = (1080, floor(model.h * 1080 / model.w))  # width height

    process_flag = True
    while True:
        ret, frame = capture.read()
        if not ret:
            break
        frame = cv2.resize(frame, net_input_size, interpolation=cv2.INTER_AREA)

        if process_flag:
            hpe_pipeline.submit_data(frame, 0, {'frame': frame, 'start_time': 0})
            hpe_pipeline.await_any()

        results = hpe_pipeline.get_result(0)
        if results:
            (poses, scores), frame_meta = results
            if len(poses) > 0:
                draw_poses(poses, frame)

        process_flag = not process_flag
        cv2.imshow("Show", cv2.resize(frame, show_frame_size, interpolation=cv2.INTER_AREA))

        if cv2.waitKey(30) == ord("q"):
            break


def launch_detection_on_webcam(args):
    capture = cv2.VideoCapture(args["cap_source"])
    if not capture.isOpened():
        raise IOError('Camera is not accessible')

    launch_detection_on_capture(capture, args)

    cv2.destroyAllWindows()
    capture.release()


if __name__ == "__main__":
    launch_detection_on_webcam({"cap_source": 0,
                                "model_path": "pose_utils/human-pose-estimation-0007.xml",
                                "device": "CPU",
                                "net_input_width": 256})