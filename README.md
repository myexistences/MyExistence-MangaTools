# Manhua OCR Translator 🚀

A high-performance Chrome Extension and Python AI Backend that seamlessly translates Manhua/Manga panels directly in your browser.

## Architecture

This project is divided into two distinct parts:
1. **Frontend (Chrome Extension):** Actively monitors your web pages, automatically detects Manhua panels, and queues them for processing. It uses a dynamic Gallery to preview successful spoofings.
2. **Backend (Python FastAPI):** A powerful local server that runs EasyOCR, groups textual bounding boxes into paragraphs, translates them via Google Translate, uses OpenCV for seamless inpainting (erasing), and dynamically renders Comic typography.

---

## Installation & Usage

### 1. Start the Python AI Backend
You must have Python installed on your system.
```powershell
cd backend
pip install -r requirements.txt
python main.py
```
*Wait for it to say `Uvicorn running on http://127.0.0.1:8000`.*

### 2. Load the Chrome Extension
1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (top right corner).
3. Click **Load unpacked** and select the `extension` folder from this repository.
4. Pin the extension to your toolbar.

### 3. Usage
1. Go to any Manhua/Manga reading site (e.g., Mangadex).
2. Click the extension icon to open the popup.
3. Check the **Debug Mode** box.
4. Scroll down! The images will automatically be detected, sent to the local server, seamlessly erased, and translated into English.

---

## 🔮 Future Improvement Plan (Roadmap)

While the current pipeline (EasyOCR + Telea Inpainting + Deep Translator) works incredibly well, here is a roadmap to transform this into an industry-grade scanlation tool:

### 1. Artificial Intelligence & Vision
* **MangaOCR Integration:** Replace EasyOCR with `manga-ocr` (a specialized model trained specifically on Japanese manga and Chinese manhua) to drastically reduce misread characters and handle vertical text natively.
* **YOLO Bubble Detection:** Currently, the AI detects *text* and draws inpainted masks over the text. A YOLOv8 model trained on speech bubbles could perfectly mask the entire bubble, allowing for completely clean bubble wipes regardless of text size.
* **LaMa Inpainting:** Upgrade from OpenCV's `cv2.inpaint` to a Neural Network inpainter like **LaMa (Resolution-robust Large Mask Inpainting)** for flawlessly erasing text over complex, high-detail character art where OpenCV leaves smudges.

### 2. Translation Context
* **Local LLM Translation:** Replace `deep-translator` with a local LLM (like Ollama running `Llama-3` or `Gemma`) instructed specifically on Manhua context. This provides highly accurate, localized dialogue instead of literal machine translations, without requiring API keys.

### 3. Frontend & Performance Optimizations
* **Intersection Observer:** Upgrade the Chrome Extension's DOM monitoring to use `IntersectionObserver`. Instead of queueing all images on the page immediately, it will prioritize sending images to the backend *right before* you scroll to them.
* **WebSockets:** Upgrade the communication from standard HTTP `fetch` to WebSockets for true bi-directional real-time streaming, lowering the latency between the browser and the Python server.

### 4. Typography
* **Diamond/Oval Text Wrapping:** Standard `textwrap` shapes text into a square block. Real manga typography uses a diamond or oval shape to naturally fit inside rounded speech bubbles. We will implement an algorithm to dynamically adjust line-widths based on vertical position to create perfect comic balloons.
