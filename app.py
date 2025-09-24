# app.py
from flask import Flask, render_template, request, jsonify
import numpy as np, cv2, base64, time
import mediapipe as mp
from joblib import load
import os

app = Flask(__name__)

# PARAMETERS - tune if needed
HOLD_SECONDS = 2.0    # how long to hold a sign before it's accepted
IDLE_SECONDS = 2.0    # how long without a hand before the server flags the word to be spoken

# Load model
MODEL_PATH = os.path.join("models", "gesture_model.joblib")
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Put gesture_model.joblib in models/")

model = load(MODEL_PATH)

# Mediapipe setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.6)

# State (kept in server memory)
buffered_word = ""
last_label = None
label_start_time = None
last_detect_time = time.time()

current_letter = ""  # last predicted letter for UI

def extract_landmarks(landmarks):
    coords = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark])
    coords -= coords[0]  # normalize to wrist
    return coords.flatten()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/predict", methods=["POST"])
def predict():
    """
    Receives a base64 JPEG image from the client, does MediaPipe -> model prediction,
    maintains server-side buffer, and when no-hand idle timeout occurs returns 'speak' text.
    Response JSON contains:
      - letter: current stable/predicted letter (or "")
      - word: current buffered word (after acceptance)
      - speak: non-empty string when the server considers the word complete and it should be spoken
    """
    global buffered_word, last_label, label_start_time, last_detect_time, current_letter

    data = request.json.get("image", "")
    if not data:
        return jsonify({"error": "no image"}), 400

    # Decode image
    try:
        image_bytes = base64.b64decode(data.split(',')[1])
    except Exception:
        return jsonify({"error": "bad image"}), 400
    npimg = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    now = time.time()
    speak_text = ""  # default empty

    # Process frame with MediaPipe
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)

    if results.multi_hand_landmarks:
        # Reset idle timer (hand present)
        last_detect_time = now

        hl = results.multi_hand_landmarks[0]
        features = extract_landmarks(hl).reshape(1, -1)

        # Model prediction
        try:
            pred_label = model.predict(features)[0]
        except Exception as e:
            pred_label = ""

        current_letter = pred_label

        # HOLD logic: user must keep same label for HOLD_SECONDS to accept it
        if pred_label == last_label:
            if label_start_time is not None and (now - label_start_time) >= HOLD_SECONDS:
                # Accept label and append once
                if pred_label.lower() == "space":
                    buffered_word += " "
                elif pred_label.lower() != "closed_hand" and pred_label != "":
                    buffered_word += pred_label
                # Reset label_start_time so this letter isn't appended repeatedly
                label_start_time = None
        else:
            # new candidate label - start hold timer
            last_label = pred_label
            label_start_time = now

    else:
        # No hand detected. If idle timeout exceeded, mark word to speak and reset buffers
        if buffered_word and (now - last_detect_time > IDLE_SECONDS):
            speak_text = buffered_word
            # clear buffer so new word can be formed
            buffered_word = ""
            last_label = None
            label_start_time = None
            current_letter = ""

    return jsonify({
        "letter": current_letter,
        "word": buffered_word,
        "speak": speak_text
    })

@app.route("/clear", methods=["POST"])
def clear_word():
    """Clear server-side buffer immediately (called by Clear button)"""
    global buffered_word, current_letter, last_label, label_start_time
    buffered_word = ""
    current_letter = ""
    last_label = None
    label_start_time = None
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
    app.run(debug=True)
