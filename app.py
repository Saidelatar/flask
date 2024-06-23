from flask import Flask, Response, render_template
from flask.json import jsonify
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import random

app = Flask(_name_)
CORS(app)

class HandTracker:
    def _init_(self, mode=False, maxHands=2, detectionCon=0.5, trackCon=0.5):
        self.mode = mode
        self.maxHands = maxHands
        self.detectionCon = detectionCon
        self.trackCon = trackCon
        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(self.mode, self.maxHands, self.detectionCon, self.trackCon)
        self.mpDraw = mp.solutions.drawing_utils

    def findHands(self, img, draw=True):
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(imgRGB)
        if self.results.multi_hand_landmarks:
            for handLm in self.results.multi_hand_landmarks:
                if draw:
                    self.mpDraw.draw_landmarks(img, handLm, self.mpHands.HAND_CONNECTIONS)
        return img

    def getPosition(self, img, handNo=0, draw=True):
        lmList = []
        if self.results.multi_hand_landmarks:
            myHand = self.results.multi_hand_landmarks[handNo]
            for lm in myHand.landmark:
                h, w, _ = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                lmList.append((cx, cy))
                if draw:
                    cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)
        return lmList

    def getUpFingers(self, img):
        pos = self.getPosition(img, draw=False)
        upfingers = []
        if pos:
            # thumb
            upfingers.append(pos[4][1] < pos[3][1] and (pos[5][0] - pos[4][0] > 10))
            # index
            upfingers.append(pos[8][1] < pos[7][1] and pos[7][1] < pos[6][1])
            # middle
            upfingers.append(pos[12][1] < pos[11][1] and pos[11][1] < pos[10][1])
            # ring
            upfingers.append(pos[16][1] < pos[15][1] and pos[15][1] < pos[14][1])
            # pinky
            upfingers.append(pos[20][1] < pos[19][1] and pos[19][1] < pos[18][1])
        return upfingers

class ColorRect:
    def _init_(self, x, y, w, h, color, text='', alpha=0.5):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.color = color
        self.text = text
        self.alpha = alpha

    def drawRect(self, img, text_color=(255, 255, 255), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.8, thickness=2):
        alpha = self.alpha
        bg_rec = img[self.y: self.y + self.h, self.x: self.x + self.w]
        white_rect = np.ones(bg_rec.shape, dtype=np.uint8)
        white_rect[:] = self.color
        res = cv2.addWeighted(bg_rec, alpha, white_rect, 1 - alpha, 1.0)
        img[self.y: self.y + self.h, self.x: self.x + self.w] = res
        text_size = cv2.getTextSize(self.text, fontFace, fontScale, thickness)
        text_pos = (int(self.x + self.w / 2 - text_size[0][0] / 2), int(self.y + self.h / 2 + text_size[0][1] / 2))
        cv2.putText(img, self.text, text_pos, fontFace, fontScale, text_color, thickness)

    def isOver(self, x, y):
        return (self.x + self.w > x > self.x) and (self.y + self.h > y > self.y)

class AirDrawingApp:
    def _init_(self):
        self.detector = HandTracker(detectionCon=1)
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280)
        self.cap.set(4, 720)
        self.canvas = np.zeros((720, 1280, 3), np.uint8)
        self.px, self.py = 0, 0
        self.color = (255, 0, 0)
        self.brushSize = 5
        self.eraserSize = 20
        self.colorsBtn = ColorRect(200, 0, 100, 100, (120, 255, 0), 'Colors')
        self.colors = [ColorRect(300, 0, 100, 100, (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))),
                       ColorRect(400, 0, 100, 100, (0, 0, 255)),
                       ColorRect(500, 0, 100, 100, (255, 0, 0)),
                       ColorRect(600, 0, 100, 100, (0, 255, 0)),
                       ColorRect(700, 0, 100, 100, (0, 255, 255)),
                       ColorRect(800, 0, 100, 100, (0, 0, 0), "Eraser")]
        self.clear = ColorRect(900, 0, 100, 100, (100, 100, 100), "Clear")
        self.pens = [ColorRect(1100, 50 + 100 * i, 100, 100, (50, 50, 50), str(size)) for i, size in enumerate(range(5, 25, 5))]
        self.penBtn = ColorRect(1100, 0, 100, 50, self.color, 'Pen')
        self.boardBtn = ColorRect(50, 0, 100, 100, (255, 255, 0), 'Board')
        self.whiteBoard = ColorRect(50, 120, 1020, 580, (255, 255, 255), alpha=0.9)
        self.coolingCounter = 20
        self.hideBoard = True
        self.hideColors = True
        self.hidePenSizes = True

    def process_frame(self):
        if self.coolingCounter:
            self.coolingCounter -= 1
        ret, frame = self.cap.read()
        if not ret:
            return None
        frame = cv2.resize(frame, (1280, 720))
        frame = cv2.flip(frame, 1)
        self.detector.findHands(frame)
        positions = self.detector.getPosition(frame, draw=False)
        upFingers = self.detector.getUpFingers(frame)
        if upFingers:
            x, y = positions[8][0], positions[8][1]
            if upFingers[1] and not self.whiteBoard.isOver(x, y):
                self.px, self.py = 0, 0
                if not self.hidePenSizes:
                    for pen in self.pens:
                        if pen.isOver(x, y):
                            self.brushSize = int(pen.text)
                            pen.alpha = 0
                        else:
                            pen.alpha = 0.5
                if not self.hideColors:
                    for cb in self.colors:
                        if cb.isOver(x, y):
                            self.color = cb.color
                            cb.alpha = 0
                        else:
                            cb.alpha = 0.5
                    if self.clear.isOver(x, y):
                        self.clear.alpha = 0
                        self.canvas = np.zeros((720, 1280, 3), np.uint8)
                    else:
                        self.clear.alpha = 0.5
                if self.colorsBtn.isOver(x, y) and not self.coolingCounter:
                    self.coolingCounter = 10
                    self.colorsBtn.alpha = 0
                    self.hideColors = not self.hideColors
                    self.colorsBtn.text = 'Colors' if self.hideColors else 'Hide'
                else:
                    self.colorsBtn.alpha = 0.5
                if self.penBtn.isOver(x, y) and not self.coolingCounter:
                    self.coolingCounter = 10
                    self.penBtn.alpha = 0
                    self.hidePenSizes = not self.hidePenSizes
                    self.penBtn.text = 'Pen' if self.hidePenSizes else 'Hide'
                else:
                    self.penBtn.alpha = 0.5
                if self.boardBtn.isOver(x, y) and not self.coolingCounter:
                    self.coolingCounter = 10
                    self.hideBoard = not self.hideBoard
                if self.whiteBoard.isOver(x, y):
                    self.px, self.py = 0, 0
            elif not self.hideBoard:
                cv2.rectangle(frame, (50, 120), (1070, 700), (255, 255, 255), cv2.FILLED)
            elif upFingers[1] and upFingers[2]:
                self.px, self.py = 0, 0
                if self.hideBoard and not self.hideColors and self.colorsBtn.isOver(x, y):
                    self.px, self.py = x, y
            elif upFingers[1] and not upFingers[2]:
                if self.px == 0 and self.py == 0:
                    self.px, self.py = x, y
                if self.color == (0, 0, 0):
                    if self.hideBoard or self.whiteBoard.isOver(x, y):
                        cv2.line(frame, (self.px, self.py), (x, y), self.color, self.eraserSize)
                        cv2.line(self.canvas, (self.px, self.py), (x, y), self.color, self.eraserSize)
                else:
                    if self.hideBoard or self.whiteBoard.isOver(x, y):
                        cv2.line(frame, (self.px, self.py), (x, y), self.color, self.brushSize)
                        cv2.line(self.canvas, (self.px, self.py), (x, y), self.color, self.brushSize)
                self.px, self.py = x, y
        imgGray = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
        _, imgInv = cv2.threshold(imgGray, 50, 255, cv2.THRESH_BINARY_INV)
        imgInv = cv2.cvtColor(imgInv, cv2.COLOR_GRAY2BGR)
        frame = cv2.bitwise_and(frame, imgInv)
        frame = cv2.bitwise_or(frame, self.canvas)
        self.penBtn.drawRect(frame)
        self.colorsBtn.drawRect(frame)
        if not self.hideColors:
            for cbtn in self.colors:
                cbtn.drawRect(frame)
            self.clear.drawRect(frame)
        if not self.hidePenSizes:
            for pen in self.pens:
                pen.drawRect(frame)
        self.boardBtn.drawRect(frame)
        if not self.hideBoard:
            self.whiteBoard.drawRect(frame, text_color=(0, 0, 0), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=4, thickness=7)
        return frame

drawing_app = AirDrawingApp()

@app.route('/')
def index():
    try:
        return jsonify({'message': 'Success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def gen():
    while True:
        frame = drawing_app.process_frame()
        if frame is None:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

if _name_ == '_main_':
    app.run(debug=True, host='0.0.0.0', port=5000)