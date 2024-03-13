"""Functions for reading and writing video files"""

from constants import RAW_THERMAL_SHAPE
import cv2

class Raw16Video:
	"""Takes a .tiff file and returns sequential frames similar to cv2.VideoCapture"""

	def __init__(self, filename):
		"""Load .tiff file. Lepton doesn't chunk files"""
		
		ret, self.frames = cv2.imreadmulti(
			filename=filename, 
			flags=cv2.IMREAD_UNCHANGED
		)
		assert ret, "Failed to read .tiff file"
		self.frames = iter(self.frames)

	def read(self):
		"""Try to return the next frame, otherwise return False"""
		try: return True, next(self.frames)
		except StopIteration: return False, None


class SaveVideo:
	"""Saves frames to video file"""
	
	def __init__(self, filename, color=False):
		"""Create VideoWriter object"""
		
		self.__vid = cv2.VideoWriter(
			filename=filename,
			apiPreference=cv2.CAP_FFMPEG,
			fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
			fps=9.0,
			frameSize=(RAW_THERMAL_SHAPE[1], RAW_THERMAL_SHAPE[0]),
			params=[cv2.VIDEOWRITER_PROP_IS_COLOR, int(color)],
		)
		assert self.__vid.isOpened()

	def __del__(self):
		"""Destructor"""
		self.close()

	def write(self, frame):
		"""Write a new frame to video"""
		assert self.__vid.isOpened()
		self.__vid.write(frame)

	def close(self):
		"""Close the video file"""
		if self.__vid.isOpened():
			self.__vid.release()
