from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
import base64
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()
app = FastAPI()
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")
# ---- Detect words (not just symbols) ----
def detect_words_from_image(image_bytes: bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"
    body = {
        "requests": [
            {
                "image": {"content": base64_image},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
            }
        ]
    }
    result = []
    boundingBoxWords = []

    response = requests.post(url, json=body)
    response_data = response.json()
    full_text = response_data['responses'][0].get('fullTextAnnotation')
    for page in full_text['pages']:
        for block in page['blocks']:
            block_text = ''
            for paragraph in block['paragraphs']:
                for word in paragraph['words']:
                    word_text = ''.join(symbol['text'] for symbol in word['symbols'])
                    # boundingBoxWords.append(get_bounding_box(word['boundingBox']['vertices']))
                    block_text += (" " + word_text)
            result.append({
                'text': block_text,
                'boundingBox': get_bounding_box(block['boundingBox']['vertices'])
            })
            boundingBoxWords.append(get_bounding_box(block['boundingBox']['vertices']))
    return result, boundingBoxWords

def get_bounding_box(vertices):
    x_coords = [v.get('x', 0) for v in vertices]
    y_coords = [v.get('y', 0) for v in vertices]
    return {
        'min_x': min(x_coords),
        'max_x': max(x_coords),
        'min_y': min(y_coords),
        'max_y': max(y_coords)
    }

def remove_text(boundingBox, draw, padding=0):
    bbox = boundingBox[0]
    draw.rectangle([
            (bbox['min_x'] - padding, bbox['min_y'] - padding),
            (bbox['max_x'] + padding, bbox['max_y'] + padding)
        ], fill="white")

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        left, top, right, bottom = draw.textbbox((0, 0), test_line, font=font)
        if right - left <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines
    
@app.post("/upload/")   
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    words, boundingBoxWords = detect_words_from_image(contents)
    # Đọc ảnh từ bytes
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    draw = ImageDraw.Draw(image)

    remove_text(boundingBoxWords, draw)


    # try:
    #     font = ImageFont.truetype("./fonts/Nunito-Black.ttf", 20)
    # except:
    #     font = ImageFont.load_default()
    # for word in words:
    #     bbox = word['boundingBox']
    #     text = word['text'].strip()

    #     # Chèn lại text vào giữa vùng bounding box, tự động xuống dòng
    #     max_width = bbox['max_x'] - bbox['min_x']
    #     lines = wrap_text(text, font, max_width, draw)
    #     # Tính tổng chiều cao các dòng
    #     line_heights = []
    #     for line in lines:
    #         left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
    #         line_heights.append(bottom - top)
    #     total_text_height = sum(line_heights)
    #     # Bắt đầu vẽ từ vị trí căn giữa theo chiều dọc
    #     y = bbox['min_y'] + ((bbox['max_y'] - bbox['min_y']) - total_text_height) // 2
    #     for i, line in enumerate(lines):
    #         left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
    #         text_width = right - left
    #         x = bbox['min_x'] + (max_width - text_width) // 2
    #         draw.text((x, y), line, fill="black", font=font)
    #         y += line_heights[i]
    # Lưu ảnh ra buffer
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")



























def detect_words(image_bytes: bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"
    body = {
        "requests": [
            {
                "image": {"content": base64_image},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
            }
        ]
    }
    result = []
    response = requests.post(url, json=body)
    response_data = response.json()
    return response_data

@app.post("/upload-image/")   
async def detect_words_api(file: UploadFile = File(...)):
    contents = await file.read()
    response_data = detect_words(contents)
    return response_data
