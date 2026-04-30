// background.js - Chrome extension service worker

// URL of the local FastAPI server (adjust if needed)
const SERVER_URL = "http://localhost:8000/process";

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "processImage") {
    // Forward image to backend for OCR, translation, and rendering
    fetch(SERVER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ imageBase64: request.imageBase64 })
    })
      .then(res => res.json())
      .then(data => {
        // Return processed image (base64) back to the caller
        sendResponse({ success: true, resultImageBase64: data.resultImageBase64 });
      })
      .catch(err => {
        console.error("Error contacting OCR server:", err);
        sendResponse({ success: false, error: err.message });
      });
    // Return true to indicate async response
    return true;
  }

  if (request.action === "saveOption") {
    chrome.storage.sync.set({ [request.key]: request.value }, () => {
      sendResponse({ success: true });
    });
    return true;
  }

  if (request.action === "loadOption") {
    chrome.storage.sync.get([request.key], (result) => {
      sendResponse({ success: true, value: result[request.key] });
    });
    return true;
  }
});
