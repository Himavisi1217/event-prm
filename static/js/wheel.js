// --- API endpoints used by the front‑end ---
const EVENT_ID = window.CURRENT_EVENT_ID || "";
const API_PARTICIPANTS = `/api/participants/${EVENT_ID}`;

// In‑memory list of participants loaded from the backend.
let participants = [];
// Current active winners to prevent duplicates in local pick
let selectedWinners = [];

let spinning = false;

const canvas = document.getElementById("wheelCanvas");
const ctx = canvas.getContext("2d");
const spinButton = document.getElementById("spinButton");
const clearButton = document.getElementById("clearButton");
const winnersList = document.getElementById("winnersList");
const wheelSelectedName = document.getElementById("wheelSelectedName");
const participantCountBadge = document.getElementById("participantCountBadge");
const winnerCountBadge = document.getElementById("winnerCountBadge");
const numWinnersInput = document.getElementById("numWinners");

/**
 * Fisher‑Yates shuffle to randomize an array in place.
 */
function shuffle(array) {
  for (let i = array.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
}

/**
 * Fetch all participants from the backend and draw the wheel.
 */
async function loadParticipants() {
  try {
    const res = await fetch(API_PARTICIPANTS);
    const data = await res.json();
    participants = data;
    participantCountBadge.textContent = `${participants.length} registered participants`;
    // Disable buttons if we have nobody to draw from.
    spinButton.disabled = participants.length === 0;

    // Default max to participants available
    if (participants.length > 0) {
      numWinnersInput.max = participants.length;
    }

    drawWheel();
  } catch (e) {
    participantCountBadge.textContent = "Error loading participants";
    spinButton.disabled = true;
  }
}

/**
 * Draw the wheel segments on the canvas based on the participants list.
 */
function drawWheel() {
  if (!participants.length) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8fafc";
    ctx.beginPath();
    ctx.arc(160, 160, 150, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#64748b";
    ctx.font = "16px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No participants yet", 160, 165);
    return;
  }

  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  const radius = 150;

  // Only draw participants not already selected
  const availableParticipants = participants.filter(
    (p) => !selectedWinners.some((w) => w.id === p.id),
  );

  if (availableParticipants.length === 0) {
    // Draw empty wheel
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8fafc";
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();
    return;
  }

  const sliceAngle = (2 * Math.PI) / availableParticipants.length;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  availableParticipants.forEach((p, index) => {
    const startAngle = index * sliceAngle;
    const endAngle = startAngle + sliceAngle;

    // Use lovely pastel hues
    const hue = (index * (360 / availableParticipants.length)) % 360;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, startAngle, endAngle);
    ctx.closePath();
    ctx.fillStyle = `hsl(${hue}, 80%, 85%)`;
    ctx.fill();

    // Dark sleek text
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(startAngle + sliceAngle / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#1e293b";
    ctx.font = "12px Inter, system-ui, sans-serif";
    ctx.fillText(p.name, radius - 15, 4);
    ctx.restore();
  });
}

function updateWinnersUI() {
  winnersList.innerHTML = "";
  selectedWinners.forEach((w, index) => {
    const li = document.createElement("li");
    li.className =
      "list-group-item d-flex justify-content-between align-items-start";
    li.style.animation = "fadeIn 0.5s ease-in-out";
    li.innerHTML = `
      <div class="me-2">
        <div class="fw-semibold text-primary">${index + 1}. ${w.name}</div>
        <div class="text-muted small">${w.company_name} · ${w.position}</div>
      </div>
    `;
    // Add custom keyframes locally
    if (!document.getElementById("fadeInKeyframes")) {
      const style = document.createElement("style");
      style.id = "fadeInKeyframes";
      style.innerHTML = `@keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }`;
      document.head.appendChild(style);
    }
    winnersList.appendChild(li);
  });

  if (winnerCountBadge) {
    winnerCountBadge.textContent = `${selectedWinners.length} selected`;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Handle multiple local spins one by one
 */
async function spinAndPickLocal() {
  if (spinning || !participants.length) return;

  const numWinners = parseInt(numWinnersInput.value, 10) || 1;

  spinning = true;
  spinButton.disabled = true;
  clearButton.disabled = true;

  for (let i = 0; i < numWinners; i++) {
    // Find available participants
    const availableParticipants = participants.filter(
      (p) => !selectedWinners.some((w) => w.id === p.id),
    );
    if (availableParticipants.length === 0) {
      wheelSelectedName.textContent = "All Picked!";
      break;
    }

    wheelSelectedName.textContent = "Spinning...";

    // Pick one at random
    const randomIndex = Math.floor(
      Math.random() * availableParticipants.length,
    );
    const thisWinner = availableParticipants[randomIndex];

    // Animate Spin Segment for roughly 2.5 seconds
    const duration = 2500;
    const start = performance.now();

    // Wait till animation completes
    await new Promise((resolve) => {
      function animate(now) {
        const elapsed = now - start;
        const t = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        // Spin random extra rotations to look real + land on the slice
        const randomExtraSpins = Math.PI * 8; // 4 full turns

        // Calculate the final angle offset to ensure winner is exactly at the top (indicator position)
        const sliceAngle = (2 * Math.PI) / availableParticipants.length;
        const targetAngleForTop = -Math.PI / 2; // top of canvas where indicator is

        const winnerCenterAngle = randomIndex * sliceAngle + sliceAngle / 2;

        // The total rotation we want to hit by the end
        const endRotation =
          randomExtraSpins + (targetAngleForTop - winnerCenterAngle);

        const currentAngle = eased * endRotation;

        ctx.save();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate(currentAngle);
        ctx.translate(-canvas.width / 2, -canvas.height / 2);
        drawWheel();
        ctx.restore();

        if (t < 1) {
          requestAnimationFrame(animate);
        } else {
          resolve();
        }
      }
      requestAnimationFrame(animate);
    });

    // Add to active lists immediately after the spin completes
    selectedWinners.push(thisWinner);
    updateWinnersUI();

    wheelSelectedName.textContent = thisWinner.name;

    // Wait briefly for suspense if there are more spins left
    if (i < numWinners - 1 && availableParticipants.length > 1) {
      await sleep(1500);
    }
  }

  // Draw the final state of the wheel with remaining users
  drawWheel();

  spinning = false;
  spinButton.disabled = selectedWinners.length >= participants.length;
  clearButton.disabled = false;

  if (selectedWinners.length > 0) {
    wheelSelectedName.textContent = "Draw Complete";
  }
}

/**
 * Clear the current winners list and reset the wheel label.
 */
function clearWinners() {
  selectedWinners = [];
  updateWinnersUI();
  wheelSelectedName.textContent = "Ready";
  drawWheel();
  spinButton.disabled = participants.length === 0;
}

if (spinButton) {
  spinButton.addEventListener("click", spinAndPickLocal);
}

if (clearButton) {
  clearButton.addEventListener("click", clearWinners);
}

if (canvas) {
  loadParticipants();
}
