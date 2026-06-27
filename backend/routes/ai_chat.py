from flask import Blueprint, request, jsonify, Response
import requests
import json
import os
from .knowledge_base import retrieve_knowledge

ai_chat_bp = Blueprint('ai_chat', __name__, url_prefix='/api')

KIMI_API_KEY = os.environ.get('KIMI_API_KEY', '')
if not KIMI_API_KEY:
    import warnings
    warnings.warn('KIMI_API_KEY 环境变量未设置，AI 聊天功能将不可用', UserWarning)

KIMI_BASE_URL = 'https://api.moonshot.cn/v1'

SYSTEM_PROMPT = """你是 DrugDesign Agent 的专业AI助手，专注于小分子药物设计领域的知识解答。你可以回答以下方面的问题：

1. 分子生成与优化（CReM片段替换、RNN、基于结构的优化）
2. ADMET成药性分析（吸收、分布、代谢、排泄、毒性预测）
3. 分子对接（AutoDock Vina、FEP自由能微扰、结合能计算）
4. 活性预测（DeepAffinity、QSAR模型、IC50/EC50预测）
5. 药物设计流程（Pipeline 8层结构：输入→生成→过滤→结构筛选→ADMET→FEP精筛→合成→输出）
6. 化学信息学工具（RDKit、3Dmol.js、OpenMM、OpenFE）
7. 合成路径分析（逆合成、反应模板、可行性评估）
8. 项目数据管理（SQLite、Flask后端、React前端）

请用专业但易懂的语言回答，必要时提供具体操作指导。如果问题超出上述范围，请礼貌地说明并建议用户查阅相关文档。"""

# 消息长度限制（与安全模块一致）
MAX_AI_MESSAGE_LENGTH = 2000
MAX_AI_MESSAGES = 20

@ai_chat_bp.route('/ai_chat', methods=['POST'])
def chat():
    data = request.get_json()
    messages = data.get('messages', [])
    
    if not messages:
        return jsonify({'success': False, 'error': '消息不能为空'}), 400
    
    # 验证消息数量
    if len(messages) > MAX_AI_MESSAGES:
        return jsonify({'success': False, 'error': f'消息列表超过 {MAX_AI_MESSAGES} 条限制'}), 413
    
    # 验证每条消息长度
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str) and len(content) > MAX_AI_MESSAGE_LENGTH:
            return jsonify({'success': False, 'error': f'单条消息长度超过 {MAX_AI_MESSAGE_LENGTH} 字符'}), 413
    
    # 检查 API Key 是否配置
    if not KIMI_API_KEY:
        return jsonify({
            'success': False, 
            'error': 'AI 服务未配置，请设置 KIMI_API_KEY 环境变量'
        }), 503
    
    if not messages:
        return jsonify({'success': False, 'error': '消息不能为空'}), 400
    
    # 提取最后一条用户消息进行 RAG 检索
    last_user_msg = ''
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            last_user_msg = msg.get('content', '')
            break
    
    # 先检索知识库
    kb_answer = retrieve_knowledge(last_user_msg) if last_user_msg else None
    if kb_answer:
        return jsonify({
            'success': True,
            'data': {
                'content': kb_answer,
                'role': 'assistant',
                'source': 'rag'  # 标记来源：知识库
            }
        })
    
    # 知识库未命中，调用 KIMI API
    full_messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    for msg in messages:
        full_messages.append({
            'role': msg.get('role', 'user'),
            'content': msg.get('content', '')
        })
    
    try:
        resp = requests.post(
            f'{KIMI_BASE_URL}/chat/completions',
            headers={
                'Authorization': f'Bearer {KIMI_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'moonshot-v1-8k',
                'messages': full_messages,
                'temperature': 0.7,
                'max_tokens': 2048,
                'stream': False
            },
            timeout=60
        )
        
        if resp.status_code != 200:
            error_detail = resp.text[:200] if resp.text else '无详细信息'
            return jsonify({
                'success': False, 
                'error': f'KIMI API错误 ({resp.status_code}): {error_detail}'
            }), 500
        
        result = resp.json()
        content = result['choices'][0]['message']['content']
        
        return jsonify({
            'success': True,
            'data': {
                'content': content,
                'role': 'assistant',
                'source': 'ai'  # 标记来源：AI 模型
            }
        })
    
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI请求超时，请稍后重试'}), 504
    except Exception as e:
        return jsonify({'success': False, 'error': f'AI服务错误: {str(e)}'}), 500


@ai_chat_bp.route('/ai_chat/stream', methods=['POST'])
def chat_stream():
    data = request.get_json()
    messages = data.get('messages', [])
    
    if not messages:
        return jsonify({'success': False, 'error': '消息不能为空'}), 400
    
    full_messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    for msg in messages:
        full_messages.append({
            'role': msg.get('role', 'user'),
            'content': msg.get('content', '')
        })
    
    def generate():
        try:
            resp = requests.post(
                f'{KIMI_BASE_URL}/chat/completions',
                headers={
                    'Authorization': f'Bearer {KIMI_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'moonshot-v1-8k',
                    'messages': full_messages,
                    'temperature': 0.7,
                    'max_tokens': 2048,
                    'stream': True
                },
                timeout=60,
                stream=True
            )
            
            for line in resp.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data:'):
                        data_str = line[5:].strip()
                        if data_str == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk['choices'][0]['delta']
                            if 'content' in delta:
                                yield f"data: {json.dumps({'content': delta['content']})}\n\n"
                        except:
                            pass
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')
