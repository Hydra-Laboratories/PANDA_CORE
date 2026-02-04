const btnConnect = document.getElementById('btn-connect');
const btnMove = document.getElementById('btn-move');
const statusBadge = document.getElementById('status-badge');
const connectionLog = document.getElementById('connection-log');
const moveLog = document.getElementById('move-log');
const serverStatus = document.getElementById('server-status');

const inputX = document.getElementById('input-x');
const inputY = document.getElementById('input-y');
const inputZ = document.getElementById('input-z');

let isConnected = false;
let isMoving = false;

// Poll status
setInterval(async () => {
    try {
        const res = await fetch('/status');
        const data = await res.json();

        if (data.connected) {
            isConnected = true;
            statusBadge.textContent = "Connected";
            statusBadge.className = "badge connected";
            btnConnect.disabled = true;
            btnConnect.textContent = "Machine Connected";
        } else {
            isConnected = false;
            statusBadge.textContent = "Disconnected";
            statusBadge.className = "badge disconnected";
            btnConnect.disabled = false;
            btnConnect.textContent = "Connect Machine";
        }

        serverStatus.textContent = "Online";
        serverStatus.style.color = "#00e676";

        updateUIState();
    } catch (e) {
        serverStatus.textContent = "Offline";
        serverStatus.style.color = "#ff5252";
        isConnected = false;
        updateUIState();
    }
}, 2000);

function updateUIState() {
    if (isConnected && !isMoving) {
        btnMove.disabled = false;
    } else {
        btnMove.disabled = true;
    }
}

btnConnect.addEventListener('click', async () => {
    connectionLog.textContent = "Connecting...";
    try {
        const res = await fetch('/connect', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            connectionLog.textContent = "Success.";
            isConnected = true;
        } else {
            connectionLog.textContent = `Error: ${data.detail}`;
        }
    } catch (e) {
        connectionLog.textContent = `Network Error: ${e}`;
    }
});

btnMove.addEventListener('click', async () => {
    const x = parseFloat(inputX.value);
    const y = parseFloat(inputY.value);
    const z = parseFloat(inputZ.value);

    isMoving = true;
    btnMove.disabled = true;
    btnMove.textContent = "Moving...";
    moveLog.textContent = `Sending: X${x} Y${y} Z${z}`;

    try {
        const res = await fetch('/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x, y, z })
        });

        const data = await res.json();

        if (res.ok) {
            moveLog.textContent = "Move Complete.";
            moveLog.style.color = "#00e676";
        } else {
            moveLog.textContent = `Failed: ${data.detail}`;
            moveLog.style.color = "#ff5252";
        }
    } catch (e) {
        moveLog.textContent = `Error: ${e}`;
    } finally {
        isMoving = false;
        btnMove.textContent = "MOVE TO TARGET";
        updateUIState();
    }
});
