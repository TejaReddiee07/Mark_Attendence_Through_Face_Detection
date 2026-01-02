// static/js/main.js

function animateCounter(element, target, duration = 1200) {
    if (!element) return;
    const start = 0;
    const startTime = performance.now();

    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const value = Math.floor(start + (target - start) * progress);
        element.textContent = value.toString();
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    requestAnimationFrame(update);
}

document.addEventListener('DOMContentLoaded', () => {
    // ----- Dashboard counters -----
    const totalStudentsEl = document.querySelector('[data-counter="total-students"]');
    const todayAttendanceEl = document.querySelector('[data-counter="today-attendance"]');
    const accuracyEl = document.querySelector('[data-counter="accuracy"]');

    if (totalStudentsEl) {
        const target = parseInt(totalStudentsEl.dataset.target || '0', 10);
        animateCounter(totalStudentsEl, target);
    }
    if (todayAttendanceEl) {
        const target = parseInt(todayAttendanceEl.dataset.target || '0', 10);
        animateCounter(todayAttendanceEl, target);
    }
    if (accuracyEl) {
        const target = parseInt(accuracyEl.dataset.target || '98', 10);
        animateCounter(accuracyEl, target);
    }

    // ----- Enroll face progress -----
    const enrollBtn = document.getElementById('enrollStartBtn');
    const progressBar = document.getElementById('enrollProgressBar');
    const statusText = document.getElementById('enrollStatus');

    if (enrollBtn && progressBar && statusText) {
        enrollBtn.addEventListener('click', async () => {
            if (enrollBtn.dataset.busy === '1') return;

            const studentId = enrollBtn.dataset.studentId;
            if (!studentId) {
                statusText.textContent = '❌ Missing student id.';
                return;
            }

            enrollBtn.dataset.busy = '1';
            enrollBtn.classList.add('loading');
            enrollBtn.textContent = 'Capturing...';
            progressBar.style.width = '0%';
            statusText.textContent = 'Opening camera...';

            try {
                const response = await fetch(`/enroll/capture/${studentId}`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                let data;
                try {
                    data = await response.json();
                } catch {
                    data = { success: false, msg: 'Server returned invalid response.' };
                }

                let current = 0;
                const interval = setInterval(() => {
                    current += 4;
                    const percent = Math.min(current, 100);
                    progressBar.style.width = percent + '%';
                    if (percent >= 100) {
                        clearInterval(interval);
                        statusText.textContent =
                            (data.success ? '✅ ' : '❌ ') + (data.msg || '');
                    }
                }, 70);
            } catch (err) {
                console.error(err);
                statusText.textContent = '❌ Error while contacting server.';
            } finally {
                setTimeout(() => {
                    enrollBtn.dataset.busy = '0';
                    enrollBtn.classList.remove('loading');
                    enrollBtn.textContent = '▶ Start Enrollment';
                }, 800);
            }
        });
    }

    // ----- Mark attendance (face) -----
    const takeBtn = document.getElementById('takeAttendanceBtn');
    const takeStatus = document.getElementById('takeAttendanceStatus');

    if (takeBtn && takeStatus) {
        takeBtn.addEventListener('click', async () => {
            takeBtn.disabled = true;
            takeStatus.textContent = 'Opening camera and recognizing...';

            try {
                const res = await fetch('/take-attendance', {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                const data = await res.json();
                takeStatus.textContent =
                    (data.success ? '✅ ' : '❌ ') + (data.msg || '');
            } catch (e) {
                takeStatus.textContent = '❌ Error contacting server.';
            } finally {
                takeBtn.disabled = false;
            }
        });
    }
});
