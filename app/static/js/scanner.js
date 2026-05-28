/**
 * PokéScan — scanner.js
 * Handles camera access, image capture, Roboflow inference calls,
 * bounding box drawing, and result rendering.
 */

// ── DOM references ─────────────────────────────────────────────────
const video           = document.getElementById('videoFeed');
const overlayCanvas   = document.getElementById('overlayCanvas');
const ctx             = overlayCanvas.getContext('2d');
const scanBadge       = document.getElementById('scanBadge');
const badgeDot        = document.getElementById('badgeDot');
const badgeText       = document.getElementById('badgeText');
const confidenceWrap  = document.getElementById('confidenceWrap');
const confidenceFill  = document.getElementById('confidenceFill');
const confidencePct   = document.getElementById('confidencePct');
const resultPanel     = document.getElementById('resultPanel');
const resultCards     = document.getElementById('resultCards');
const errorPanel      = document.getElementById('errorPanel');
const errorMessage    = document.getElementById('errorMessage');
const errorTip        = document.getElementById('errorTip');
const btnScan         = document.getElementById('btnScan');
const btnUpload       = document.getElementById('btnUpload');
const btnDismiss      = document.getElementById('btnDismiss');
const fileInput       = document.getElementById('fileInput');

// ── State ──────────────────────────────────────────────────────────
let stream        = null;   // MediaStream from getUserMedia
let isScanning    = false;  // Prevents concurrent scan requests
let autoScanTimer = null;   // Auto-scan interval ID

// ── Camera initialisation ──────────────────────────────────────────
async function startCamera() {
    setBadge('Requesting camera…', 'dot');
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: 'environment' }, // Back camera on phones
                width:  { ideal: 1280 },
                height: { ideal: 960 }
            }
        });
        video.srcObject = stream;
        video.addEventListener('loadedmetadata', () => {
            syncCanvasSize();
            setBadge('Camera ready — press Scan', 'ready');
            startAutoScan();
        });
    } catch (err) {
        // Camera not available — show file upload fallback
        setBadge('Camera unavailable — use Upload', 'error');
        document.querySelector('.camera-frame').style.background = '#1a1a2a';
        console.warn('Camera error:', err);
    }
}

// Keep overlay canvas in sync with video dimensions
function syncCanvasSize() {
    overlayCanvas.width  = video.videoWidth;
    overlayCanvas.height = video.videoHeight;
}

// ── Auto-scan (every 3 seconds while camera is live) ──────────────
function startAutoScan() {
    // Auto-scan only fires if user hasn't manually dismissed a result
    autoScanTimer = setInterval(() => {
        if (!isScanning && resultPanel.style.display === 'none') {
            captureAndSend();
        }
    }, 3000);
}

// ── Capture a frame and send to Flask ─────────────────────────────
async function captureAndSend(imageData = null) {
    if (isScanning) return;
    isScanning = true;
    setBadge('Scanning…', 'scanning');
    hideResult();
    hideError();

    try {
        let base64;

        if (imageData) {
            // Uploaded file — already a data URL
            base64 = imageData.split(',')[1];
        } else {
            // Live video frame
            const capture = document.createElement('canvas');
            capture.width  = video.videoWidth;
            capture.height = video.videoHeight;
            capture.getContext('2d').drawImage(video, 0, 0);
            base64 = capture.toDataURL('image/jpeg', 0.85).split(',')[1];
        }

        const response = await fetch('/scanner/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: base64 })
        });

        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const data = await response.json();
        handleResult(data);

    } catch (err) {
        console.error('Scan error:', err);
        showError('Connection error — check your internet connection.', '');
        setBadge('Error', 'error');
    } finally {
        isScanning = false;
    }
}

// ── Handle inference result ────────────────────────────────────────
function handleResult(data) {
    if (data.success && data.detections && data.detections.length > 0) {
        // Show highest confidence in the bar
        const topConf = Math.max(...data.detections.map(d => d.confidence));
        updateConfidenceBar(topConf);

        // Draw bounding boxes for all detections
        clearOverlay();
        data.detections.forEach(det => drawBBox(det.bbox, det.card.name, det.confidence));

        // Render result cards
        showResult(data.detections);
        setBadge(`${data.detections.length} card${data.detections.length > 1 ? 's' : ''} detected!`, 'ready');
        // Stop auto-scan so result stays visible
        clearInterval(autoScanTimer);

    } else {
        // Low confidence or no detection — show confidence bar if data available
        clearOverlay();
        if (data.confidence !== undefined) {
            updateConfidenceBar(data.confidence * 100);
        } else {
            hideConfidenceBar();
        }
        showError(data.message || 'No card detected.', data.tip || '');
        setBadge('No match — try again', 'error');
    }
}

// ── Bounding box drawing ───────────────────────────────────────────
function drawBBox(bbox, label, confidencePct) {
    // Roboflow returns centre x, y — convert to top-left
    const x = bbox.x - bbox.width  / 2;
    const y = bbox.y - bbox.height / 2;
    const w = bbox.width;
    const h = bbox.height;

    // Glowing box
    ctx.save();
    ctx.shadowColor  = '#FFD700';
    ctx.shadowBlur   = 16;
    ctx.strokeStyle  = '#FFD700';
    ctx.lineWidth    = 3;
    ctx.strokeRect(x, y, w, h);

    // Corner brackets (more stylish than a full box)
    const cs = 20; // Corner size
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth   = 4;
    ctx.shadowBlur  = 0;
    // Top-left
    ctx.beginPath(); ctx.moveTo(x, y + cs); ctx.lineTo(x, y); ctx.lineTo(x + cs, y); ctx.stroke();
    // Top-right
    ctx.beginPath(); ctx.moveTo(x + w - cs, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + cs); ctx.stroke();
    // Bottom-left
    ctx.beginPath(); ctx.moveTo(x, y + h - cs); ctx.lineTo(x, y + h); ctx.lineTo(x + cs, y + h); ctx.stroke();
    // Bottom-right
    ctx.beginPath(); ctx.moveTo(x + w - cs, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - cs); ctx.stroke();
    ctx.restore();

    // Label pill
    const labelText = `${label}  ${confidencePct}%`;
    ctx.font        = 'bold 14px Rajdhani, sans-serif';
    const textW     = ctx.measureText(labelText).width;
    const pillX     = x;
    const pillY     = y - 28;
    const pillH     = 22;
    const pillW     = textW + 16;

    ctx.fillStyle   = '#FFD700';
    ctx.beginPath();
    ctx.roundRect(pillX, pillY, pillW, pillH, 4);
    ctx.fill();
    ctx.fillStyle = '#0e0e14';
    ctx.fillText(labelText, pillX + 8, pillY + 15);
}

function clearOverlay() {
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
}

// ── Confidence bar ─────────────────────────────────────────────────
function updateConfidenceBar(pct) {
    confidenceWrap.style.display = 'flex';
    confidenceFill.style.width   = `${Math.min(pct, 100)}%`;
    confidencePct.textContent    = `${Math.round(pct)}%`;
}
function hideConfidenceBar() {
    confidenceWrap.style.display = 'none';
}

// ── Result panel ───────────────────────────────────────────────────
function showResult(detections) {
    resultCards.innerHTML = '';
    detections.forEach(det => {
        const c = det.card;
        const el = document.createElement('div');
        el.className = 'result-card-item';
        el.innerHTML = `
            ${c.image_url
                ? `<img src="${c.image_url}" alt="${c.name}" class="result-card-img">`
                : '<div class="result-card-img" style="background:#1e1e2a;display:flex;align-items:center;justify-content:center;font-size:2rem;color:#4a4a6a;">◉</div>'
            }
            <div class="result-card-info">
                <div class="result-card-name">${c.name}</div>
                <div class="result-card-meta">
                    ${c.set_name}${c.set_number ? ' · ' + c.set_number : ''}
                    ${c.rarity ? `<br><span class="badge badge-rarity">${c.rarity}</span>` : ''}
                    ${c.pokemon_type ? `<span class="badge badge-type" style="margin-left:4px">${c.pokemon_type}</span>` : ''}
                </div>
                ${c.hp ? `<div style="font-size:0.8rem;color:#E3350D;font-weight:700">HP ${c.hp}</div>` : ''}
                <div class="result-card-value">$${c.market_value.toFixed(2)} AUD</div>
                ${det.already_owned ? '<div class="result-already-owned">⚠ Already in your library</div>' : ''}
                ${det.wishlist_cleared ? '<div class="result-wishlist-cleared">★ Removed from your wishlist!</div>' : ''}
                <div style="font-size:0.75rem;color:#7a7a9a;margin-top:0.3rem">Confidence: ${det.confidence}%</div>
            </div>`;
        resultCards.appendChild(el);
    });
    resultPanel.style.display = 'block';
    errorPanel.style.display  = 'none';
    resultPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideResult() {
    resultPanel.style.display = 'none';
}

// ── Error panel ────────────────────────────────────────────────────
function showError(msg, tip) {
    errorMessage.textContent    = msg;
    errorTip.textContent        = tip;
    errorPanel.style.display    = 'block';
    resultPanel.style.display   = 'none';
}
function hideError() {
    errorPanel.style.display = 'none';
}

// ── Badge helper ───────────────────────────────────────────────────
function setBadge(text, state) {
    badgeText.textContent = text;
    badgeDot.className    = 'badge-dot ' + (state || '');
}

// ── Event listeners ────────────────────────────────────────────────

// Manual scan button
btnScan.addEventListener('click', () => {
    clearInterval(autoScanTimer);
    captureAndSend().then(() => startAutoScan());
});

// Upload image button
btnUpload.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
        clearInterval(autoScanTimer);
        captureAndSend(ev.target.result);
    };
    reader.readAsDataURL(file);
    fileInput.value = ''; // Reset so same file can be re-uploaded
});

// Dismiss result — restart auto-scan
btnDismiss.addEventListener('click', () => {
    hideResult();
    hideError();
    clearOverlay();
    hideConfidenceBar();
    setBadge('Camera ready — press Scan', 'ready');
    startAutoScan();
});

// Resize handling — keep canvas in sync
window.addEventListener('resize', syncCanvasSize);

// ── Boot ───────────────────────────────────────────────────────────
startCamera();
