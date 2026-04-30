// content_script.js - Injected into pages to find and process manhua panels automatically

let processedImages = new Set();
let manhuaPanels = []; 
let debugModeEnabled = false;
let isProcessing = false;
const imageQueue = [];
let observer = null;
let intersectionObserver = null;

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getState") {
    // Return the current state of THIS tab
    sendResponse({ 
      success: true, 
      isDebugActive: debugModeEnabled, 
      panels: manhuaPanels 
    });
    return true;
  }

  if (request.action === "toggleDebug") {
    const wasEnabled = debugModeEnabled;
    debugModeEnabled = request.enabled;
    console.log("Manhua OCR: Debug mode " + (debugModeEnabled ? "enabled" : "disabled"));
    
    if (debugModeEnabled && !wasEnabled) {
      // User turned it OFF then ON -> Restart everything for this tab
      processedImages.clear();
      manhuaPanels = [];
      imageQueue.length = 0; // clear queue
      isProcessing = false;
      
      // Remove all old visual borders
      document.querySelectorAll('img').forEach(img => {
        img.style.border = '';
      });
      
      // Restart observer and queue all current images
      startObserving();
    } else if (!debugModeEnabled) {
      // User turned it OFF -> stop processing
      stopObserving();
      imageQueue.length = 0;
      isProcessing = false;
      
      // Optionally remove borders when turned off
      document.querySelectorAll('img').forEach(img => {
        img.style.border = '';
      });
    }
    
    sendResponse({ success: true });
    return true;
  }
});

function startObserving() {
  if (observer) stopObserving();
  
  // Intersection Observer: Only process images when they are near the viewport
  // rootMargin '800px' means it will start processing when the image is 800 pixels below the screen.
  intersectionObserver = new IntersectionObserver((entries, obs) => {
    let newImages = false;
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        queueImage(img);
        obs.unobserve(img); // Only process it once
        newImages = true;
      }
    });
    if (newImages && !isProcessing && debugModeEnabled) {
      processQueue();
    }
  }, { rootMargin: "800px" });

  observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.addedNodes.length) {
        mutation.addedNodes.forEach(node => {
          if (node.tagName === 'IMG') {
            intersectionObserver.observe(node);
          } else if (node.querySelectorAll) {
            node.querySelectorAll('img').forEach(img => intersectionObserver.observe(img));
          }
        });
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Observe existing images
  document.querySelectorAll('img').forEach(img => intersectionObserver.observe(img));
}

function stopObserving() {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
  if (typeof intersectionObserver !== 'undefined' && intersectionObserver) {
    intersectionObserver.disconnect();
    intersectionObserver = null;
  }
}

function queueImage(img) {
  if (!debugModeEnabled || !img.src || processedImages.has(img.src)) return;
  
  if (img.complete) {
    checkAndEnqueue(img);
  } else {
    img.addEventListener('load', () => checkAndEnqueue(img));
  }
}

function checkAndEnqueue(img) {
  if (!debugModeEnabled || processedImages.has(img.src)) return;
  
  if (img.width < 250 || img.height < 250) {
    processedImages.add(img.src); 
    return;
  }
  
  processedImages.add(img.src);
  imageQueue.push(img);
  
  if (!isProcessing) {
    processQueue();
  }
}

async function processQueue() {
  if (imageQueue.length === 0 || !debugModeEnabled) {
    isProcessing = false;
    return;
  }
  
  isProcessing = true;
  const imgElement = imageQueue.shift();
  
  const panelObj = {
    id: Date.now() + Math.random().toString(),
    src: imgElement.src,
    status: 'analyzing',
    resultSrc: null
  };
  manhuaPanels.push(panelObj);
  
  if (debugModeEnabled) {
    imgElement.style.border = "4px solid yellow";
  }
  
  try {
    const base64 = await getBase64ImageFromUrl(imgElement.src);
    
    const response = await new Promise(resolve => {
      chrome.runtime.sendMessage({
        action: 'processImage',
        imageBase64: base64
      }, resolve);
    });

    if (response && response.success && debugModeEnabled) {
      panelObj.status = 'success';
      imgElement.style.border = "4px solid green";
      if (response.resultImageBase64) {
        panelObj.resultSrc = 'data:image/png;base64,' + response.resultImageBase64;
        imgElement.src = panelObj.resultSrc;
      }
    } else if (debugModeEnabled) {
      panelObj.status = 'ignored';
      imgElement.style.border = "4px solid gray";
    }
  } catch (e) {
    console.error("Failed to process image:", imgElement.src, e);
    if (debugModeEnabled) {
      panelObj.status = 'error';
      imgElement.style.border = "4px solid red";
    }
  }
  
  // Process the next image immediately
  setTimeout(processQueue, 0);
}

async function getBase64ImageFromUrl(imageUrl) {
  const response = await fetch(imageUrl);
  const blob = await response.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = reader.result.replace(/^data:image\/(png|jpeg|jpg|webp);base64,/, '');
      resolve(base64String);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
