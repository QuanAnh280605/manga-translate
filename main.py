from fastapi import FastAPI, File, UploadFile
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

    response = requests.post(url, json=body)
    response.raise_for_status()
    annotations = response.json()

    words = []
    try:
        pages = annotations["responses"][0]["fullTextAnnotation"]["pages"]
        for page in pages:
            for block in page.get("blocks", []):
                for paragraph in block.get("paragraphs", []):
                    for word in paragraph.get("words", []):
                        word_text = "".join([s["text"] for s in word["symbols"]])
                        word_box = word["boundingBox"]["vertices"]
                        words.append({
                            "text": word_text,
                            "bounding_box": word_box
                        })
    except KeyError:
        return []

    return words


def wrap_text_to_width(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test_line = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines

# ---- Font size dựa vào bounding box ----
def get_font_size(box):
    if len(box) >= 2:
        y0 = box[0].get("y", 0)
        y1 = box[2].get("y", 0)
        height = abs(y1 - y0)
        return max(10, height)
    return 40

# ---- Translate danh sách text ----
def translate_texts(texts, target_lang="vi"):
    url = f"https://translation.googleapis.com/language/translate/v2?key={GOOGLE_TRANSLATE_API_KEY}"
    body = {
        "q": texts,
        "target": target_lang,
        "format": "text"
    }
    response = requests.post(url, json=body)
    response.raise_for_status()
    data = response.json()
    return [t["translatedText"] for t in data["data"]["translations"]]

def wrap_text_to_width(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test_line = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines


def wrap_text_to_width(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test_line = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines

def draw_translated_texts(image_bytes, words):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_path = Path("fonts/Nunito-Black.ttf")

    drawn_boxes = []

    for word in words:
        text = word["text"]
        box = word["bounding_box"]
        if len(box) >= 1:
            x = box[0].get("x", 0)
            y = box[0].get("y", 0)
            x2 = box[2].get("x", x + 100)  # lấy chiều rộng ước lượng
            max_width = abs(x2 - x)

            font_size = min(50, get_font_size(box))
            font = ImageFont.truetype(str(font_path), size=font_size)

            # Tự động xuống dòng nếu text dài
            lines = wrap_text_to_width(draw, text, font, max_width)
            text_height = sum(draw.textbbox((0, 0), line, font=font)[3] for line in lines)
            proposed_box = [x, y, x + max_width, y + text_height]

            # Dịch xuống nếu bị đè
            max_shift = 100
            shift = 0
            while shift < max_shift:
                overlap = False
                for db in drawn_boxes:
                    if boxes_overlap(proposed_box, db):
                        overlap = True
                        break
                if not overlap:
                    break
                y += 5
                proposed_box = [x, y, x + max_width, y + text_height]
                shift += 5

            # Vẽ từng dòng text
            for line in lines:
                draw.text((x, y), line, font=font, fill="blue")
                y += draw.textbbox((0, 0), line, font=font)[3]  # cách dòng

            drawn_boxes.append(proposed_box)

    return image


def boxes_overlap(box1, box2):
    # box = [x1, y1, x2, y2]
    x1, y1, x2, y2 = box1
    a1, b1, a2, b2 = box2
    return not (x2 < a1 or x1 > a2 or y2 < b1 or y1 > b2)


# ---- API dịch và in lên ảnh ----
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    words = detect_words_from_image(contents)
    original_texts = [w["text"] for w in words]
    translated_texts = translate_texts(original_texts)

    # Gán lại text tiếng Việt vào từng word
    for i, w in enumerate(words):
        w["text"] = translated_texts[i]

    image = draw_translated_texts(contents, words)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="image/png")
