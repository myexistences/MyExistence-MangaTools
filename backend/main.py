from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import base64
import numpy as np
import cv2
import io
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Manhua OCR Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    import easyocr
    from PIL import Image, ImageDraw, ImageFont
    logger.info("Initializing EasyOCR...")
    # lang='ch_sim' is for simplified chinese, 'en' for english. 
    # Add 'ch_tra' if you want traditional chinese
    ocr = easyocr.Reader(['ch_sim', 'en']) 
    logger.info("EasyOCR initialized successfully.")
    OCR_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import EasyOCR or related libraries: {e}")
    OCR_AVAILABLE = False


def is_manhua_panel(img: np.ndarray) -> bool:
    height, width = img.shape[:2]
    if height < 200 or width < 200:
        return False
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    edge_density = np.sum(edges > 0) / (height * width)
    if edge_density < 0.01:
        return False
    return True

@app.post("/process")
async def process_image(request: Request):
    data = await request.json()
    image_base64 = data.get("imageBase64")
    
    if not image_base64:
        return {"success": False, "error": "No imageBase64 provided"}
        
    if not OCR_AVAILABLE:
        return {"success": False, "error": "OCR engine not available on backend"}
        
    try:
        img_data = base64.b64decode(image_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {"success": False, "error": "Failed to decode image"}
            
        if not is_manhua_panel(img):
            return {"success": False, "error": "Image does not appear to be a manhua panel"}
        
        logger.info("Running OCR on image...")
        # EasyOCR returns a list of (bbox, text, prob)
        raw_result = ocr.readtext(img)
        
        import string
        result = []
        for res in raw_result:
            bbox, text, prob = res
            text = text.strip()
            
            # Lowered threshold to 0.15 because handwritten manhua text can have low confidence
            if prob < 0.15:
                continue
                
            # Filter 2: Pure punctuation or empty
            text_no_punct = text.translate(str.maketrans('', '', string.punctuation + " \n\t。，！？（）《》“”‘’"))
            if len(text_no_punct) == 0:
                continue
                
            result.append(res)
        
        if not result:
            return {"success": False, "error": "No valid text detected"}
            
        txts = [res[1] for res in result]
        
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='en')
        
        # Keep original img for color sampling
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        font_path = r"e:\Workspace\Manhua OCR\assets\fonts\CC Wild Words Roman.ttf"
        import textwrap
        
        # Group nearby bounding boxes to form full sentences!
        boxes_data = []
        for res in result:
            bbox, text, _ = res
            arr = np.array(bbox)
            x_min, y_min = np.min(arr[:, 0]), np.min(arr[:, 1])
            x_max, y_max = np.max(arr[:, 0]), np.max(arr[:, 1])
            boxes_data.append([x_min, y_min, x_max, y_max, text])
            
        # Sort by Y-coordinate first
        boxes_data.sort(key=lambda x: x[1])
        
        merged_groups = []
        for box in boxes_data:
            if not merged_groups:
                merged_groups.append(box)
                continue
                
            last = merged_groups[-1]
            
            # Check if they are close vertically and overlap horizontally
            # Manhua text is usually stacked vertically.
            x_overlap = not (box[0] > last[2] + 40 or box[2] < last[0] - 40)
            y_dist = box[1] - last[3]
            
            if x_overlap and y_dist < 50:
                # Merge into the last group
                last[0] = min(last[0], box[0])
                last[1] = min(last[1], box[1])
                last[2] = max(last[2], box[2])
                last[3] = max(last[3], box[3])
                # Manhua is often read top-to-bottom, no space needed in Chinese, but space for english
                last[4] += " " + box[4]
            else:
                merged_groups.append(box)
        
        translated_txts = []
        
        # 1. SEAMLESS INPAINTING (Erase all text without breaking bubbles!)
        # Create a mask for all detected text
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        for box in boxes_data:
            x_min = max(0, int(box[0]) - 5)
            y_min = max(0, int(box[1]) - 5)
            x_max = min(img.shape[1], int(box[2]) + 5)
            y_max = min(img.shape[0], int(box[3]) + 5)
            cv2.rectangle(mask, (x_min, y_min), (x_max, y_max), 255, -1)
            
        # Magically erase the text while keeping bubble borders and gradients intact!
        inpainted_img = cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)
        
        pil_img = Image.fromarray(cv2.cvtColor(inpainted_img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        # 2. Translate and draw text
        for group in merged_groups:
            gx_min, gy_min, gx_max, gy_max, full_text = group
            
            if len(full_text) < 2 and full_text.isascii():
                continue
                
            try:
                translated_text = translator.translate(full_text)
            except Exception as e:
                logger.error(f"Translation failed for '{full_text}': {e}")
                translated_text = full_text
                
            translated_txts.append(translated_text)
            
            box_width = gx_max - gx_min
            box_height = gy_max - gy_min
            center_x, center_y = int((gx_min + gx_max)/2), int((gy_min + gy_max)/2)
            
            # Sample background color directly from the beautifully inpainted center!
            sample_y = min(inpainted_img.shape[0]-1, max(0, center_y))
            sample_x = min(inpainted_img.shape[1]-1, max(0, center_x))
            bg_color_bgr = inpainted_img[sample_y, sample_x]
            bg_color = (int(bg_color_bgr[2]), int(bg_color_bgr[1]), int(bg_color_bgr[0]))
            
            area = box_width * box_height
            char_len = len(translated_text) if len(translated_text) > 0 else 1
            estimated_font_size = int((area / char_len) ** 0.5) * 1.3
            font_size = max(16, min(int(estimated_font_size), int(box_height * 0.8)))
            
            try:
                font = ImageFont.truetype(font_path, font_size)
            except IOError:
                font = ImageFont.load_default()
                
            avg_char_width = font_size * 0.55
            chars_per_line = max(1, int((box_width * 0.95) / avg_char_width))
            wrapped_text = textwrap.fill(translated_text, width=chars_per_line)
            
            brightness = (bg_color[0] * 299 + bg_color[1] * 587 + bg_color[2] * 114) / 1000
            text_color = (255, 255, 255) if brightness < 128 else (0, 0, 0)
            
            draw.multiline_text(
                (center_x, center_y), 
                wrapped_text, 
                font=font, 
                fill=text_color, 
                anchor="mm", 
                align="center"
            )
            
        buffered = io.BytesIO()
        pil_img.save(buffered, format="PNG")
        result_image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        logger.info(f"Processed and translated image successfully. Handled {len(txts)} text blocks.")
        
        return {
            "success": True, 
            "resultImageBase64": result_image_base64,
            "texts": translated_txts
        }
        
    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
