document.addEventListener('DOMContentLoaded', () => {
    // URL Backend chính thức trên Render
    const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? '' : 'https://mas-m54w.onrender.com';

    const taskInput = document.getElementById('taskInput');
    const assignBtn = document.getElementById('assignBtn');
    const taskList = document.getElementById('taskList');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const refreshBoard = document.getElementById('refreshBoard');
    
    // Modal elements
    const resultModal = document.getElementById('resultModal');
    const closeModal = document.getElementById('closeModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalContent = document.getElementById('modalContent');
    const copyResultBtn = document.getElementById('copyResultBtn');
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');

    // Agent Select Modal (Gữ lại cho các tính năng khác nếu cần)
    const agentSelectModal = document.getElementById('agentSelectModal');
    const closeAgentModal = document.getElementById('closeAgentModal');
    const agentListContainer = document.getElementById('agentListContainer');

    let currentMissions = [];
    let currentResultRaw = "";
    let currentActiveMissionId = null;

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

    const updateUIStatus = (status) => {
        const banner = document.getElementById('boardStatusBanner');
        const bannerText = document.getElementById('bannerText');
        const assignBtn = document.getElementById('assignBtn');
        const taskInput = document.getElementById('taskInput');

        if (!status || (!status.warning && !status.blocked)) {
            banner.style.display = 'none';
            assignBtn.disabled = false;
            taskInput.disabled = false;
            return;
        }

        banner.style.display = 'flex';
        if (status.blocked) {
            banner.className = 'status-banner danger';
            bannerText.innerHTML = `⚠️ <strong>HỆ THỐNG ĐÃ KHÓA:</strong> Dung lượng board (${status.size_mb}MB) đã vượt mức 10MB.`;
            assignBtn.disabled = true;
            taskInput.disabled = true;
        } else if (status.warning) {
            banner.className = 'status-banner warning';
            bannerText.innerHTML = `⚠️ <strong>CẢNH BÁO:</strong> Dung lượng board (${status.size_mb}MB) sắp đầy.`;
        }
    };

    const renderBoard = (missions) => {
        if (!missions || missions.length === 0) {
            taskList.innerHTML = '<div style="text-align: center; color: var(--text-dim); padding: 2rem;">Chưa có nhiệm vụ nào.</div>';
            return;
        }

        taskList.innerHTML = missions.map(mission => `
            <div class="mission-card" id="mission-${mission.id}">
                <div class="mission-header">
                    <div class="mission-info">
                        <div class="mission-meta">STRATEGIC MISSION #${mission.id}</div>
                        <div class="mission-goal">${mission.goal}</div>
                    </div>
                    <div class="mission-actions">
                        <button class="btn-view-result" style="margin:0" onclick="synthesizeMission('${mission.id}')">
                            ${mission.report ? 'Xem Báo Cáo' : 'Tổng hợp kết quả'}
                        </button>
                        <button class="btn-delete-task" style="margin:0" onclick="deleteMission('${mission.id}')">Xóa Mission</button>
                    </div>
                </div>
                
                <div class="subtask-grid">
                    ${mission.tasks.map(task => `
                        <div class="task-card">
                            <div class="task-meta">
                                <span class="id-tag">#${task.id}</span>
                                <span class="agent-tag">${task.assigned_to}</span>
                            </div>
                            <div class="task-title">${task.title}</div>
                            <div class="task-desc">${task.description}</div>
                            <div style="display:flex; justify-content: space-between; align-items: center; margin-top: 1rem;">
                                <div class="status-pill status-${task.status}">${task.status.toUpperCase()}</div>
                                <div style="display:flex; gap: 0.3rem;">
                                    <button class="btn-view-result" style="font-size: 0.65rem; padding: 0.2rem 0.5rem; margin:0;" onclick="confirmRerun('${mission.id}', '${task.id}')" title="Yêu cầu Agent thực hiện lại nhiệm vụ này">Làm lại</button>
                                    ${task.status === 'done' ? `<button class="btn-view-result" style="font-size: 0.65rem; padding: 0.2rem 0.5rem; margin:0;" onclick="showTaskResult('${mission.id}', '${task.id}')">Kết quả</button>` : ''}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    };

    window.confirmRerun = async (missionId, taskId) => {
        if (!confirm(`Bạn có chắc muốn Agent thực hiện lại nhiệm vụ #${taskId}?`)) return;
        loadingOverlay.style.display = 'flex';
        try {
            const response = await fetch(`${API_BASE_URL}/api/task/rerun`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mission_id: missionId, task_id: taskId })
            });
            if ((await response.json()).success) fetchBoard();
        } catch (error) { alert('Lỗi kết nối server'); } finally { loadingOverlay.style.display = 'none'; }
    };

    window.deleteMission = async (missionId) => {
        if (!confirm(`Bạn có chắc muốn xóa Mission #${missionId}?`)) return;
        try {
            const response = await fetch(`${API_BASE_URL}/api/mission/${missionId}`, { method: 'DELETE' });
            if ((await response.json()).success) fetchBoard();
        } catch (error) { alert('Lỗi kết nối'); }
    };

    window.synthesizeMission = async (missionId) => {
        const mission = currentMissions.find(m => m.id === missionId);
        if (mission && mission.report) {
            showMarkdownModal(`Báo cáo Mission: ${mission.id}`, mission.report, true, missionId);
            return;
        }
        loadingOverlay.style.display = 'flex';
        try {
            const response = await fetch(`${API_BASE_URL}/api/mission/${missionId}/synthesize`, { method: 'POST' });
            
            // Neu Backend tra ve 202, nghia la da bat dau chay ngam
            if (response.status === 202) {
                alert('Đang khởi tạo báo cáo AI ngầm... Báo cáo sẽ tự hiển thị trên Dashboard sau khoảng 1 phút. Bạn có thể tiếp tục làm việc khác.');
                return;
            }

            const result = await response.json();
            if (result.success && result.report) {
                showMarkdownModal(`Báo cáo Mission: ${missionId}`, result.report, true, missionId);
                fetchBoard();
            }
        } catch (error) { 
            console.error('Synthesis error:', error);
            // alert('Co loi khi ket noi server.'); 
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
        } catch (error) { alert('Lỗi thử lại'); }
    };

    window.showTaskResult = (missionId, taskId) => {
        const mission = currentMissions.find(m => m.id === missionId);
        const task = mission ? mission.tasks.find(t => t.id === taskId) : null;
        if (task && task.result) showMarkdownModal(`Kết quả: ${task.assigned_to}`, task.result, false);
    };

    const showMarkdownModal = (title, content, showPdf, missionId = null) => {
        currentResultRaw = content;
        currentActiveMissionId = missionId;
        modalTitle.innerText = title;
        if (!content) {
            modalContent.innerHTML = '<div style="padding: 2rem; text-align: center;">Chưa có dữ liệu báo cáo.</div>';
        } else if (content.includes("[ERROR]")) {
            modalContent.innerHTML = `<div style="padding: 2rem; text-align: center; color: #ff6b6b;">
                    <strong>AI SYNTHESIS FAILED</strong><br><br>${content}
                </div>`;
        } else {
            modalContent.innerHTML = marked.parse(content);
        }
        resultModal.classList.add('active');
    };

    closeModal.addEventListener('click', () => resultModal.classList.remove('active'));
    closeAgentModal.addEventListener('click', () => agentSelectModal.classList.remove('active'));

    copyResultBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(currentResultRaw).then(() => {
            alert('Đã sao chép vào Clipboard');
        });
    });

    downloadPdfBtn.addEventListener('click', async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/export_markdown`, { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mission_id: currentActiveMissionId })
            });
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url;
                a.download = `Report_${currentActiveMissionId}.md`;
                a.click();
            }
        } catch (error) { alert('Lỗi tải báo cáo'); }
    });

    assignBtn.addEventListener('click', async () => {
        const goal = taskInput.value.trim();
        if (!goal) return;
        
        const consoleContainer = document.getElementById('consoleContainer');
        const consoleBody = document.getElementById('consoleBody');
        consoleBody.innerHTML = '';
        consoleContainer.style.display = 'flex';
        loadingOverlay.style.display = 'flex';

        try {
            const response = await fetch(`${API_BASE_URL}/api/decompose_stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal })
            });
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                consoleBody.innerText += decoder.decode(value, { stream: true });
                consoleBody.scrollTop = consoleBody.scrollHeight;
            }
            setTimeout(() => {
                loadingOverlay.style.display = 'none';
                taskInput.value = '';
                fetchBoard();
            }, 1000);
        } catch (error) { alert('Lỗi decomposition'); loadingOverlay.style.display = 'none'; }
    });

    refreshBoard.addEventListener('click', fetchBoard);
    fetchBoard();
    setInterval(fetchBoard, 10000);
});
