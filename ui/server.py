from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import subprocess
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import threading

# Thêm tools vào path để import delegate và storage
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR / "tools"))

try:
    import storage
    import delegate
except ImportError:
    sys.path.append(str(BASE_DIR))
    import storage
    import delegate

app = Flask(__name__)
# Cho phép CORS từ mọi nguồn (hoặc bạn có thể giới hạn Netlify URL sau này)
CORS(app)

file_lock = threading.Lock()
WORKSPACE_ROOT = BASE_DIR
UI_DIR = Path(__file__).parent

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# CAC API ENDPOINTS DUOI DAY...
def get_board_status():
    try:
        if not storage.board_exists():
            return {"warning": False, "blocked": False, "size_mb": 0}
        size_mb = storage.get_board_size_mb()
        return {
            "warning": size_mb > 9,
            "blocked": size_mb > 10,
            "size_mb": round(size_mb, 2)
        }
    except Exception as e:
        return {"warning": False, "blocked": False, "size_mb": 0}

@app.route('/api/board', methods=['GET'])
def get_board():
    data = storage.get_board()
    data["status"] = get_board_status()
    return jsonify(data)

@app.route('/api/decompose_stream', methods=['POST'])
def decompose_stream():
    status = get_board_status()
    if status["blocked"]:
        return jsonify({"error": "Board is full"}), 403

    data = request.json
    goal = data.get('goal')
    if not goal:
        return jsonify({"error": "Goal is required"}), 400
        
    def generate():
        try:
            # Chạy script phân rã từ thư mục tools
            process = subprocess.Popen(
                [sys.executable, "-u", str(WORKSPACE_ROOT / "tools" / "decompose_task.py"), goal],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield line
            process.stdout.close()
            process.wait()
        except Exception as e:
            yield f"\n[ERROR] {str(e)}\n"
            
    return Response(stream_with_context(generate()), mimetype='text/plain')

@app.route('/api/status', methods=['GET'])
def get_status():
    """Kiểm tra trạng thái các agent (Dựa trên Database activity)."""
    try:
        result = subprocess.run(
            [sys.executable, str(WORKSPACE_ROOT / "tools" / "check_agent_status.py"), "--json"],
            capture_output=True, check=True
        )
        return jsonify(json.loads(result.stdout.decode("utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mission/<mission_id>/synthesize', methods=['POST'])
def synthesize_mission(mission_id):
    try:
        subprocess.run(
            [sys.executable, str(WORKSPACE_ROOT / "tools" / "synthesize_results.py"), mission_id],
            capture_output=True, check=True, encoding="utf-8"
        )
        board = storage.get_board()
        mission = next((m for m in board.get("missions", []) if m["id"] == mission_id), None)
        if mission and mission.get("report"):
            return jsonify({"success": True, "report": mission["report"]})
        return jsonify({"success": False, "error": "No report found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/export_markdown', methods=['POST'])
def export_markdown():
    try:
        data = request.json or {}
        mission_id = data.get("mission_id")
        board = storage.get_board()
        missions = board.get("missions", [])
        target_mission = next((m for m in missions if m["id"] == mission_id), None)
        if not target_mission:
            return jsonify({"success": False, "error": "Mission not found"}), 404
        return Response(
            target_mission["report"],
            mimetype="text/markdown",
            headers={"Content-disposition": f"attachment; filename=Strategic_Report_{mission_id}.md"}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/mission/<mission_id>', methods=['DELETE'])
def delete_mission(mission_id):
    if storage.delete_mission(mission_id):
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route('/api/task/rerun', methods=['POST'])
def rerun_task():
    """Reset status về pending. Agent sẽ tự nhặt việc qua Polling."""
    data = request.json
    task_id = data.get('task_id')
    agent_name = data.get('agent_name')
    updates = {"status": "pending", "result": ""}
    if agent_name:
        updates["assigned_to"] = agent_name
    if storage.update_task_atomic(task_id, updates):
        return jsonify({"success": True, "message": "Task reset to pending. Agent will poll it soon."})
    return jsonify({"success": False}), 500

@app.route('/api/board/reset', methods=['POST'])
def reset_board():
    if storage.reset_board():
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
