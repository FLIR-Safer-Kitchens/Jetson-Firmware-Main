"""
Wrapper for the YoloV7 TensorRT engine

Slightly modified version of https://github.com/mailrocketsystems/JetsonYoloV7-TensorRT

Licensed under GPL-3, see build_engine/
"""

import pycuda.driver as cuda
import pycuda.autoinit
import tensorrt as trt
import numpy as np
import ctypes
import time
import cv2


EXPLICIT_BATCH = 1 << (int)(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
host_inputs  = []
cuda_inputs  = []
host_outputs = []
cuda_outputs = []
bindings = []


class YoloEngine():
    def __init__(self, library, engine, conf_thresh=0.5, nms_thresh=0.4, classes=None):
        self.CONF_THRESH   = conf_thresh
        self.IOU_THRESHOLD = nms_thresh
        self.CLASS_FILTER  = set(classes)

        self.LEN_ALL_RESULT = 38001
        self.LEN_ONE_RESULT = 38
        self.categories = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
            "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
            "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
            "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
            "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
            "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
            "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
            "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
            "hair drier", "toothbrush"]

        # Create logger
        TRT_LOGGER = trt.Logger(trt.Logger.ERROR)

        # Load DLL
        ctypes.CDLL(library)

        # Load engine
        with open(engine, 'rb') as f:
            serialized_engine = f.read()

        # Initialize engine
        cuda.init()
        self.cuda_ctx = cuda.Device(0).make_context()
        runtime = trt.Runtime(TRT_LOGGER)
        self.engine = runtime.deserialize_cuda_engine(serialized_engine)
        self.batch_size = self.engine.max_batch_size

        for binding in self.engine:
            size = trt.volume(self.engine.get_binding_shape(binding)) * self.batch_size
            dtype = trt.nptype(self.engine.get_binding_dtype(binding))
            host_mem = cuda.pagelocked_empty(size, dtype)
            cuda_mem = cuda.mem_alloc(host_mem.nbytes)

            bindings.append(int(cuda_mem))
            if self.engine.binding_is_input(binding):
                self.input_w = self.engine.get_binding_shape(binding)[-1]
                self.input_h = self.engine.get_binding_shape(binding)[-2]
                host_inputs.append(host_mem)
                cuda_inputs.append(cuda_mem)
            else:
                host_outputs.append(host_mem)
                cuda_outputs.append(cuda_mem)


    def __del__(self):
        # Context cleanup
        if hasattr(self, "cuda_ctx"):
            self.cuda_ctx.pop()


    def inference(self, img):
        """
        Performs YoloV7 inference on an image

        Parameters:
        - img (numpy.ndarray): The image to be processed

        Returns (tuple)
        - (list, dict): Result dictionary with class, confidence, and xyxy bounding box
        - (float): Inference time in seconds
        """

        # Pre-process image
        input_image, origin_h, origin_w = self._pre_process(img)

        # Send image to GPU shared memory
        np.copyto(host_inputs[0], input_image.ravel())
        stream = cuda.Stream()
        self.context = self.engine.create_execution_context()
        cuda.memcpy_htod_async(cuda_inputs[0], host_inputs[0], stream)

        # Run inference
        t1 = time.time()
        self.context.execute_async(self.batch_size, bindings, stream_handle=stream.handle)
        cuda.memcpy_dtoh_async(host_outputs[0], cuda_outputs[0], stream)
        stream.synchronize()
        t2 = time.time()

        # Post-process results
        # TODO: Is the result supposed to get overwritten every iteration?
        output = host_outputs[0]
        for i in range(self.batch_size):
            out = output[i * self.LEN_ALL_RESULT: (i + 1) * self.LEN_ALL_RESULT]
            result_boxes, result_scores, result_classid = self._post_process(out, origin_h, origin_w)

        # Format output
        det_res = []
        for j in range(len(result_boxes)):
            det = dict()
            det["class"] = self.categories[int(result_classid[j])]
            det["conf"]  = result_scores[j]
            det["box"]   = result_boxes[j]
            det_res.append(det)

        return det_res, t2-t1


    def _pre_process(self, img):
        """
        Pre-processes a regular BGR image before passing to engine

        Parameters:
        - img (numpy.ndarray): The image to be processed

        Returns (numpy.ndarray): The pre-processed image
        """
        # Convert image to RGB
        image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Resize image
        h, w, c = image.shape
        r_w = self.input_w / w
        r_h = self.input_h / h
        if r_h > r_w:
            tw = self.input_w
            th = int(r_w * h)
            tx1 = tx2 = 0
            ty1 = int((self.input_h - th) / 2)
            ty2 = self.input_h - th - ty1
        else:
            tw = int(r_h * w)
            th = self.input_h
            tx1 = int((self.input_w - tw) / 2)
            tx2 = self.input_w - tw - tx1
            ty1 = ty2 = 0
        image = cv2.resize(image, (tw, th))
        image = cv2.copyMakeBorder(image, ty1, ty2, tx1, tx2, cv2.BORDER_CONSTANT, None, (128, 128, 128))

        # Convert to floating point
        image = image.astype(np.float32)
        image /= 255.0

        # Re-arrange channels
        image = np.transpose(image, [2, 0, 1])
        image = np.expand_dims(image, axis=0)
        image = np.ascontiguousarray(image)
        return image, h, w


    def _post_process(self, output, origin_h, origin_w):
        """
        Post processes the detection results. Including filtering, NMS, and formatting

        Parameters:
        - output (numpy.ndarray): The raw results from the YoloV7 engine
        - origin_h (int): Height of source image
        - origin_w (int): Width of source image

        Returns (tuple):
        - list (list (int)): Bounding boxes in xyxy format
        - list (float): Confidence scores
        - list (int): Detection classes
        """

        # Format predictions
        num = int(output[0])
        pred = np.reshape(output[1:], (-1, 6))[:num, :]

        # Filter results with low confidence
        confs = pred[:, 4]
        boxes = pred[confs >= self.CONF_THRESH]

        # Filter results by class
        if (self.CLASS_FILTER != None):
            classes = [int(b[5]) for b in boxes]
            idx = [i for i, c in enumerate(classes) if c in self.CLASS_FILTER]

            boxes = boxes[idx]
            confs = confs[idx]

        # Format and clip bounding boxes
        boxes[:, :4] = self._xywh2xyxy(origin_h, origin_w, boxes[:, :4])
        boxes[:,  0] = np.clip(boxes[:, 0], 0, origin_w-1)
        boxes[:,  2] = np.clip(boxes[:, 2], 0, origin_w-1)
        boxes[:,  1] = np.clip(boxes[:, 1], 0, origin_h-1)
        boxes[:,  3] = np.clip(boxes[:, 3], 0, origin_h-1)

        # Perform non-maximum suppression
        # Remove boxes with lower confidence scores, large IOUs, and matching labels
        boxes = boxes[np.argsort(-confs)]
        keep_boxes = []
        while boxes.shape[0]:
            large_overlap = self._bbox_iou(np.expand_dims(boxes[0, :4], 0), boxes[:, :4]) > self.IOU_THRESHOLD
            label_match = boxes[0, -1] == boxes[:, -1]
            invalid = large_overlap & label_match
            keep_boxes += [boxes[0]]
            boxes = boxes[~invalid]

        # Return good boxes and their scores/classes
        boxes = np.stack(keep_boxes, 0) if len(keep_boxes) else np.array([])
        result_boxes   = boxes[:, :4] if len(boxes) else np.array([])
        result_scores  = boxes[:,  4] if len(boxes) else np.array([])
        result_classid = boxes[:,  5] if len(boxes) else np.array([])
        return result_boxes, result_scores, result_classid


    def _xywh2xyxy(self, origin_h, origin_w, bbox):
        """
        Converts a bounding box from xywh format to xyxy format

        Parameters:
        - origin_h (int): Height of source image
        - origin_w (int): Width of source image
        - bbox (list): Bounding box coordinates in xywh format

        Returns (list): Bounding box coordinates in xyxy format
        """

        y = np.zeros_like(bbox)
        r_w = self.input_w / origin_w
        r_h = self.input_h / origin_h
        if r_h > r_w:
            y[:, 0] = bbox[:, 0] - bbox[:, 2] / 2
            y[:, 2] = bbox[:, 0] + bbox[:, 2] / 2
            y[:, 1] = bbox[:, 1] - bbox[:, 3] / 2 - (self.input_h - r_w * origin_h) / 2
            y[:, 3] = bbox[:, 1] + bbox[:, 3] / 2 - (self.input_h - r_w * origin_h) / 2
            y /= r_w
        else:
            y[:, 0] = bbox[:, 0] - bbox[:, 2] / 2 - (self.input_w - r_h * origin_w) / 2
            y[:, 2] = bbox[:, 0] + bbox[:, 2] / 2 - (self.input_w - r_h * origin_w) / 2
            y[:, 1] = bbox[:, 1] - bbox[:, 3] / 2
            y[:, 3] = bbox[:, 1] + bbox[:, 3] / 2
            y /= r_h

        return y


    def _bbox_iou(self, box1, box2):
        """
        Computes intersection over union (IOU) for two bounding boxes

        Parameters:
        - box1 (list): xyxy coordinates for the first box
        - box2 (list): xyxy coordinates for the second box

        Returns (float): Intersection over union for the pair of boxes
        """

        # Get the coordinates of bounding boxes
        b1_x1, b1_y1, b1_x2, b1_y2 = box1[:, 0], box1[:, 1], box1[:, 2], box1[:, 3]
        b2_x1, b2_y1, b2_x2, b2_y2 = box2[:, 0], box2[:, 1], box2[:, 2], box2[:, 3]

        # Get intersection area
        inter_rect_x1 = np.maximum(b1_x1, b2_x1)
        inter_rect_y1 = np.maximum(b1_y1, b2_y1)
        inter_rect_x2 = np.minimum(b1_x2, b2_x2)
        inter_rect_y2 = np.minimum(b1_y2, b2_y2)
        inter_area = np.clip(inter_rect_x2 - inter_rect_x1 + 1, 0, None) * \
                     np.clip(inter_rect_y2 - inter_rect_y1 + 1, 0, None)

        # Get total areas
        b1_area = (b1_x2 - b1_x1 + 1) * (b1_y2 - b1_y1 + 1)
        b2_area = (b2_x2 - b2_x1 + 1) * (b2_y2 - b2_y1 + 1)

        # Return IOU
        return inter_area / (b1_area + b2_area - inter_area + 1e-16)
