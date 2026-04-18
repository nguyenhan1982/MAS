document.addEventListener('DOMContentLoaded', () => {
    // THAY THE URL DUOI DAY BANG URL RENDER CUA BAN (Vi du: https://mas-backend.onrender.com)
    const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? '' : 'https://your-api-server.onrender.com';

    const taskInput = document.getElementById('taskInput');
    const assignBtn = document.getElementById('assignBtn');
    const taskList = document.getElementById('taskList');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const refreshBoard = document.getElementById('refreshBoard');
    
    // ... (cac bien khac)
    const resultModal = document.getElementById('resultModal');
    const closeModal = document.getElementById('closeModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalContent = document.getElementById('modalContent');
    const copyResultBtn = document.getElementById('copyResultBtn');
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');

    const fetchBoard = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/board`);
            const data = await response.json();
            currentMissions = data.missions || [];
            updateUIStatus(data.status);
            renderBoard(currentMissions);
        } catch (error) {
            console.error('Lỗi tải board:', error);
        }
    };

    window.deleteMission = async (missionId) => {
        if (!confirm(`Bạn có chắc muốn xóa toàn bộ Mission #${missionId}?`)) return;
        try {
            const response = await fetch(`${API_BASE_URL}/api/mission/${missionId}`, { method: 'DELETE' });
            const result = await response.json();
            if (result.success) await fetchBoard();
        } catch (error) {
            alert('Lỗi kết nối server');
        }
    };

    window.synthesizeMission = async (missionId) => {
        // ... (logic kiem tra report)
        loadingOverlay.style.display = 'flex';
        try {
            const response = await fetch(`${API_BASE_URL}/api/mission/${missionId}/synthesize`, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                showMarkdownModal(`Báo cáo Mission: ${missionId}`, result.report, true, missionId);
                fetchBoard();
            }
        } catch (error) {
            alert('Lỗi kết nối server');
        } finally {
            loadingOverlay.style.display = 'none';
        }
    };

    window.reSynthesize = async (missionId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/mission/${missionId}/synthesize`, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                showMarkdownModal(`Báo cáo Mission: ${missionId}`, result.report, true, missionId);
                fetchBoard();
            }
        } catch (error) {
            alert('Lỗi kết nối khi thử lại');
        }
    };

    window.openRetaskModal = async (missionId, taskId) => {
        agentListContainer.innerHTML = 'Đang quét...';
        agentSelectModal.classList.add('active');
        try {
            const response = await fetch(`${API_BASE_URL}/api/status`);
            const agents = await response.json();
            // ... (render html)
            agentListContainer.innerHTML = agents.map(agent => {
                const isOnline = agent.status === 'online';
                return `<div class="agent-item" onclick="${isOnline ? `confirmRetask('${missionId}', '${taskId}', '${agent.agent}')` : ''}">${agent.agent}</div>`;
            }).join('');
        } catch (error) {
            agentListContainer.innerHTML = 'Lỗi kết nối.';
        }
    };

    window.confirmRetask = async (missionId, taskId, agentName) => {
        if (!confirm(`Giao cho ${agentName}?`)) return;
        try {
            const response = await fetch(`${API_BASE_URL}/api/task/rerun`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mission_id: missionId, task_id: taskId, agent_name: agentName })
            });
            if ((await response.json()).success) fetchBoard();
        } catch (error) {
            alert('Lỗi kết nối');
        }
    };

    downloadPdfBtn.addEventListener('click', async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/export_markdown`, { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mission_id: currentActiveMissionId })
            });
            // ... (pdf download logic)
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url;
                a.download = `Strategic_Report_${currentActiveMissionId}.md`;
                a.click();
            }
        } catch (error) { alert('Lỗi tải báo cáo'); }
    });

    assignBtn.addEventListener('click', async () => {
        const goal = taskInput.value.trim();
        if (!goal) return;
        loadingOverlay.style.display = 'flex';
        try {
            const response = await fetch(`${API_BASE_URL}/api/decompose_stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal })
            });
            // ... (streaming logic)
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                // hien thi console...
            }
            fetchBoard();
        } catch (error) { alert('Lỗi'); } finally { loadingOverlay.style.display = 'none'; }
    });

    const resetBoardBtn = document.getElementById('resetBoardBtn');
    if (resetBoardBtn) {
        resetBoardBtn.addEventListener('click', async () => {
            if (!confirm('Reset Board?')) return;
            try {
                const response = await fetch(`${API_BASE_URL}/api/board/reset`, { method: 'POST' });
                if ((await response.json()).success) await fetchBoard();
            } catch (error) { alert('Lỗi'); }
        });
    }

    fetchBoard();
    setInterval(fetchBoard, 10000);
});
