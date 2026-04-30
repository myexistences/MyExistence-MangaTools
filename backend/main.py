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
        
        translated_txts = []
        for res in result:
            box = np.array(res[0]).astype(np.int32)
            original_text = res[1]
            
            try:
                translated_text = translator.translate(original_text)
            except Exception as e:
                logger.error(f"Translation failed for '{original_text}': {e}")
                translated_text = original_text
                
            translated_txts.append(translated_text)
            
            # 1. Erase original text with matching background color
            x_min = max(0, np.min(box[:, 0]) - 3)
            y_min = max(0, np.min(box[:, 1]) - 3)
            x_max = min(img.shape[1], np.max(box[:, 0]) + 3)
            y_max = min(img.shape[0], np.max(box[:, 1]) + 3)
            
            # Sample background color from the very edge of the bounding box
            # We take a pixel from the top-left edge
            sample_y = max(0, y_min - 2)
            sample_x = max(0, x_min - 2)
            bg_color_bgr = img[sample_y, sample_x]
            bg_color = (bg_color_bgr[2], bg_color_bgr[1], bg_color_bgr[0]) # Convert BGR to RGB
            
            # Draw the box using the sampled background color instead of pure white!
            draw.rectangle([x_min, y_min, x_max, y_max], fill=bg_color)
            
            # 2. Draw translated text
            box_width = x_max - x_min
            box_height = y_max - y_min
            
            # Make font significantly larger
            # Assume text will take roughly sqrt(width * height / len(text)) pixels per char
            area = box_width * box_height
            char_len = len(translated_text) if len(translated_text) > 0 else 1
            estimated_font_size = int((area / char_len) ** 0.5) * 1.2
            
            # Clamp font size
            font_size = max(16, min(int(estimated_font_size), int(box_height * 0.8)))
            
            try:
                font = ImageFont.truetype(font_path, font_size)
            except IOError:
                font = ImageFont.load_default()
                
            avg_char_width = font_size * 0.55
            chars_per_line = max(1, int((box_width) / avg_char_width))
            
            wrapped_text = textwrap.fill(translated_text, width=chars_per_line)
            
            # Determine text color (black or white) based on background brightness
            brightness = (bg_color[0] * 299 + bg_color[1] * 587 + bg_color[2] * 114) / 1000
            text_color = (255, 255, 255) if brightness < 128 else (0, 0, 0)
            
            draw.multiline_text(
                ((x_min + x_max)/2, (y_min + y_max)/2), 
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
