// popup.js - UI logic for the extension popup

const debugCheckbox = document.getElementById('debugMode');
const statusDiv = document.getElementById('status');
const statsDiv = document.getElementById('statsDiv');
const galleryDiv = document.getElementById('galleryDiv');
const previewImage = document.getElementById('previewImage');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const galleryCounter = document.getElementById('galleryCounter');

let panels = [];
let currentIndex = 0;
let refreshInterval = null;

// Initialize popup by getting the state from the ACTIVE TAB
async function initPopup() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;
    
    // Inject the content script if it's not already there (optional safety)
    // Send message to get state
    chrome.tabs.sendMessage(tab.id, { action: 'getState' }, (response) => {
      if (chrome.runtime.lastError || !response) {
        statusDiv.textContent = 'Active: Page cannot be monitored (reload tab).';
        debugCheckbox.disabled = true;
        return;
      }
      
      // Load current state from the tab
      debugCheckbox.checked = response.isDebugActive;
      updateUIWithPanels(response.panels);
      
      if (response.isDebugActive) {
        startAutoRefresh();
      }
    });
  } catch (e) {
    console.error("Init Error:", e);
  }
}

// When user toggles the checkbox, tell the ACTIVE TAB to toggle its state
debugCheckbox.addEventListener('change', async () => {
  const isEnabled = debugCheckbox.checked;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (tab) {
    chrome.tabs.sendMessage(tab.id, {
      action: 'toggleDebug',
      enabled: isEnabled
    }, (response) => {
      if (isEnabled) {
        // Restarted -> clear UI and start refreshing
        panels = [];
        currentIndex = 0;
        updateUIWithPanels([]);
        startAutoRefresh();
      } else {
        // Stopped -> keep UI as is, but stop auto-refreshing
        stopAutoRefresh();
      }
    });
  }
});

// Fetch panels from the content script (polling)
async function fetchPanels() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url && !tab.url.startsWith('chrome://')) {
      chrome.tabs.sendMessage(tab.id, { action: 'getState' }, (response) => {
        // Ignore the "Receiving end does not exist" error silently during auto-refresh
        if (chrome.runtime.lastError) return;
        
        if (response && response.success) {
          updateUIWithPanels(response.panels);
        }
      });
    }
  } catch (e) {
    console.error(e);
  }
}

function updateUIWithPanels(newPanels) {
  // Filter to show analyzing, success, or error panels
  panels = newPanels.filter(p => p.status === 'success' || p.status === 'analyzing' || p.status === 'error');
  
  statsDiv.textContent = `Manhua panels found: ${panels.length}`;
  
  if (panels.length > 0) {
    galleryDiv.style.display = 'block';
    // If the currently viewed index is now out of bounds (due to reset), fix it
    if (currentIndex >= panels.length) {
      currentIndex = panels.length - 1;
    }
    updateGallery();
  } else {
    galleryDiv.style.display = 'none';
  }
}

function updateGallery() {
  if (panels.length === 0) return;
  
  const currentPanel = panels[currentIndex];
  previewImage.src = currentPanel.resultSrc || currentPanel.src;
  
  galleryCounter.textContent = `${currentIndex + 1} / ${panels.length}`;
  
  prevBtn.disabled = currentIndex === 0;
  nextBtn.disabled = currentIndex === panels.length - 1;
}

prevBtn.addEventListener('click', () => {
  if (currentIndex > 0) {
    currentIndex--;
    updateGallery();
  }
});

nextBtn.addEventListener('click', () => {
  if (currentIndex < panels.length - 1) {
    currentIndex++;
    updateGallery();
  }
});

function startAutoRefresh() {
  if (!refreshInterval) {
    refreshInterval = setInterval(fetchPanels, 500);
  }
}

function stopAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
}

// Start
initPopup();
