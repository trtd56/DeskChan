const canvas = document.querySelector("#gameCanvas");
const ctx = canvas.getContext("2d");

const statusText = document.querySelector("#statusText");
const messageLayer = document.querySelector("#messageLayer");
const playerScoreEl = document.querySelector("#playerScore");
const cpuScoreEl = document.querySelector("#cpuScore");
const roundCountEl = document.querySelector("#roundCount");
const trailCountEl = document.querySelector("#trailCount");
const lastResultEl = document.querySelector("#lastResult");
const speedSelect = document.querySelector("#speedSelect");
const difficultySelect = document.querySelector("#difficultySelect");
const startButton = document.querySelector("#startButton");
const pauseButton = document.querySelector("#pauseButton");
const resetButton = document.querySelector("#resetButton");

const COLS = 60;
const ROWS = 40;
const CELL = canvas.width / COLS;
const EMPTY = 0;
const PLAYER = 1;
const CPU = 2;

const DIRS = {
  up: { x: 0, y: -1, name: "up" },
  down: { x: 0, y: 1, name: "down" },
  left: { x: -1, y: 0, name: "left" },
  right: { x: 1, y: 0, name: "right" },
};

const OPPOSITE = {
  up: "down",
  down: "up",
  left: "right",
  right: "left",
};

const keyMap = {
  ArrowUp: "up",
  KeyW: "up",
  ArrowDown: "down",
  KeyS: "down",
  ArrowLeft: "left",
  KeyA: "left",
  ArrowRight: "right",
  KeyD: "right",
};

let grid;
let player;
let cpu;
let playerScore = 0;
let cpuScore = 0;
let round = 1;
let running = false;
let paused = false;
let ended = false;
let lastTick = 0;
let trailCount = 0;
let animationId = null;

function makeGrid() {
  return Array.from({ length: ROWS }, () => Array(COLS).fill(EMPTY));
}

function newBike(x, y, dir, color, trailColor, id) {
  return {
    x,
    y,
    dir,
    nextDir: dir,
    color,
    trailColor,
    id,
    alive: true,
  };
}

function resetRound({ keepMessage = false } = {}) {
  grid = makeGrid();
  player = newBike(10, Math.floor(ROWS / 2), DIRS.right, "#e8fbff", "#22d3ee", PLAYER);
  cpu = newBike(COLS - 11, Math.floor(ROWS / 2), DIRS.left, "#fff0f4", "#ff4f79", CPU);
  markCell(player.x, player.y, PLAYER);
  markCell(cpu.x, cpu.y, CPU);
  trailCount = 2;
  running = false;
  paused = false;
  ended = false;
  lastTick = 0;
  pauseButton.textContent = "Pause";
  statusText.textContent = "Ready";
  if (!keepMessage) {
    showMessage("Press Start", "Arrow keys or WASD to steer");
  }
  updateStats();
  draw();
}

function resetMatch() {
  playerScore = 0;
  cpuScore = 0;
  round = 1;
  lastResultEl.textContent = "-";
  resetRound();
}

function startGame() {
  if (ended) {
    round += 1;
    resetRound({ keepMessage: true });
  }
  running = true;
  paused = false;
  ended = false;
  statusText.textContent = "Live";
  pauseButton.textContent = "Pause";
  hideMessage();
  if (!animationId) {
    animationId = requestAnimationFrame(loop);
  }
}

function togglePause() {
  if (!running || ended) return;
  paused = !paused;
  pauseButton.textContent = paused ? "Resume" : "Pause";
  statusText.textContent = paused ? "Paused" : "Live";
  if (paused) {
    showMessage("Paused", "Press Resume to continue");
  } else {
    hideMessage();
    lastTick = 0;
  }
}

function loop(timestamp) {
  animationId = requestAnimationFrame(loop);
  if (!running || paused || ended) return;
  const interval = Number(speedSelect.value);
  if (!lastTick) lastTick = timestamp;
  if (timestamp - lastTick < interval) return;
  lastTick = timestamp;
  tick();
}

function tick() {
  player.dir = player.nextDir;
  cpu.nextDir = chooseCpuDirection();
  cpu.dir = cpu.nextDir;

  const playerNext = nextPosition(player);
  const cpuNext = nextPosition(cpu);
  const headOn = playerNext.x === cpuNext.x && playerNext.y === cpuNext.y;
  const playerCrash = headOn || isBlocked(playerNext.x, playerNext.y);
  const cpuCrash = headOn || isBlocked(cpuNext.x, cpuNext.y);

  if (playerCrash || cpuCrash) {
    finishRound(playerCrash, cpuCrash);
    return;
  }

  player.x = playerNext.x;
  player.y = playerNext.y;
  cpu.x = cpuNext.x;
  cpu.y = cpuNext.y;
  markCell(player.x, player.y, PLAYER);
  markCell(cpu.x, cpu.y, CPU);
  trailCount += 2;
  updateStats();
  draw();
}

function finishRound(playerCrash, cpuCrash) {
  running = false;
  ended = true;
  player.alive = !playerCrash;
  cpu.alive = !cpuCrash;

  let title;
  let detail;
  if (playerCrash && cpuCrash) {
    title = "Draw";
    detail = "Both cycles collided";
    lastResultEl.textContent = "Draw";
  } else if (cpuCrash) {
    title = "You win";
    detail = "CPU ran out of space";
    playerScore += 1;
    lastResultEl.textContent = "You win";
  } else {
    title = "CPU wins";
    detail = "Your light trail hit first";
    cpuScore += 1;
    lastResultEl.textContent = "CPU wins";
  }

  statusText.textContent = "Round over";
  updateStats();
  draw();
  showMessage(title, `${detail}. Press Start for round ${round + 1}`);
}

function chooseCpuDirection() {
  const possible = legalDirections(cpu).filter((dir) => !wouldEnterPlayerHead(dir));
  const candidates = possible.length ? possible : legalDirections(cpu);
  if (!candidates.length) return cpu.dir;

  const skill = Number(difficultySelect.value);
  if (Math.random() > skill) {
    return candidates[Math.floor(Math.random() * candidates.length)];
  }

  let best = candidates[0];
  let bestScore = -Infinity;
  for (const dir of candidates) {
    const next = {
      x: cpu.x + dir.x,
      y: cpu.y + dir.y,
    };
    const area = floodFillArea(next.x, next.y, 420);
    const playerDistance = Math.abs(next.x - player.x) + Math.abs(next.y - player.y);
    const centerBias = 24 - Math.abs(next.x - COLS / 2) - Math.abs(next.y - ROWS / 2);
    const pressure = dir === cpu.dir ? 5 : 0;
    const chase = Math.max(0, 34 - playerDistance) * 0.42;
    const score = area * 2.4 + centerBias * 0.25 + pressure + chase;
    if (score > bestScore) {
      bestScore = score;
      best = dir;
    }
  }
  return best;
}

function legalDirections(bike) {
  return Object.values(DIRS).filter((dir) => {
    if (OPPOSITE[bike.dir.name] === dir.name) return false;
    const x = bike.x + dir.x;
    const y = bike.y + dir.y;
    return !isBlocked(x, y);
  });
}

function wouldEnterPlayerHead(dir) {
  const cpuNext = { x: cpu.x + dir.x, y: cpu.y + dir.y };
  const playerNext = nextPosition({ ...player, dir: player.nextDir });
  return cpuNext.x === playerNext.x && cpuNext.y === playerNext.y;
}

function floodFillArea(startX, startY, limit) {
  if (isBlocked(startX, startY)) return 0;
  const seen = new Set([`${startX},${startY}`]);
  const queue = [{ x: startX, y: startY }];
  let area = 0;
  while (queue.length && area < limit) {
    const point = queue.shift();
    area += 1;
    for (const dir of Object.values(DIRS)) {
      const x = point.x + dir.x;
      const y = point.y + dir.y;
      const key = `${x},${y}`;
      if (seen.has(key) || isBlocked(x, y)) continue;
      seen.add(key);
      queue.push({ x, y });
    }
  }
  return area;
}

function changePlayerDirection(name) {
  const next = DIRS[name];
  if (!next || OPPOSITE[player.dir.name] === next.name) return;
  player.nextDir = next;
  if (!running && !ended) {
    statusText.textContent = `Queued ${next.name}`;
  }
}

function nextPosition(bike) {
  return {
    x: bike.x + bike.dir.x,
    y: bike.y + bike.dir.y,
  };
}

function isBlocked(x, y) {
  return x < 0 || y < 0 || x >= COLS || y >= ROWS || grid[y][x] !== EMPTY;
}

function markCell(x, y, id) {
  grid[y][x] = id;
}

function updateStats() {
  playerScoreEl.textContent = String(playerScore);
  cpuScoreEl.textContent = String(cpuScore);
  roundCountEl.textContent = String(round);
  trailCountEl.textContent = String(trailCount);
}

function showMessage(title, detail) {
  messageLayer.querySelector("strong").textContent = title;
  messageLayer.querySelector("span").textContent = detail;
  messageLayer.classList.remove("hidden");
}

function hideMessage() {
  messageLayer.classList.add("hidden");
}

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawGrid();
  drawTrails();
  drawBike(player);
  drawBike(cpu);
}

function drawGrid() {
  ctx.fillStyle = "#061013";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "rgba(84, 148, 160, 0.13)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= COLS; x += 4) {
    ctx.beginPath();
    ctx.moveTo(x * CELL, 0);
    ctx.lineTo(x * CELL, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y <= ROWS; y += 4) {
    ctx.beginPath();
    ctx.moveTo(0, y * CELL);
    ctx.lineTo(canvas.width, y * CELL);
    ctx.stroke();
  }
}

function drawTrails() {
  for (let y = 0; y < ROWS; y += 1) {
    for (let x = 0; x < COLS; x += 1) {
      const cell = grid[y][x];
      if (cell === EMPTY) continue;
      const color = cell === PLAYER ? player.trailColor : cpu.trailColor;
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 10;
      ctx.fillRect(x * CELL + 1, y * CELL + 1, CELL - 2, CELL - 2);
    }
  }
  ctx.shadowBlur = 0;
}

function drawBike(bike) {
  const px = bike.x * CELL;
  const py = bike.y * CELL;
  ctx.fillStyle = bike.alive ? bike.color : "#6f7d80";
  ctx.shadowColor = bike.trailColor;
  ctx.shadowBlur = bike.alive ? 24 : 0;
  ctx.fillRect(px + 2, py + 2, CELL - 4, CELL - 4);

  ctx.fillStyle = bike.trailColor;
  const noseX = px + CELL / 2 + bike.dir.x * CELL * 0.23;
  const noseY = py + CELL / 2 + bike.dir.y * CELL * 0.23;
  ctx.beginPath();
  ctx.arc(noseX, noseY, Math.max(2, CELL * 0.14), 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
}

document.addEventListener("keydown", (event) => {
  const dir = keyMap[event.code];
  if (!dir) return;
  event.preventDefault();
  changePlayerDirection(dir);
});

for (const [id, dir] of [
  ["upButton", "up"],
  ["leftButton", "left"],
  ["downButton", "down"],
  ["rightButton", "right"],
]) {
  document.querySelector(`#${id}`).addEventListener("click", () => changePlayerDirection(dir));
}

startButton.addEventListener("click", startGame);
pauseButton.addEventListener("click", togglePause);
resetButton.addEventListener("click", resetMatch);

speedSelect.addEventListener("change", () => {
  lastTick = 0;
});

difficultySelect.addEventListener("change", () => {
  statusText.textContent = `CPU ${difficultySelect.selectedOptions[0].textContent}`;
});

resetRound();
