"""
formatters.py - Agent 输出统一格式化器

将所有格式化逻辑集中到此处，供 executor.py、tools.py 和 engine.py 使用。
避免格式化代码在多个文件中重复。
"""

from typing import Dict, Any, List
import json


class MoleculeFormatter:
    """分子数据格式化器"""
    
    @staticmethod
    def format_molecule_card(mol: Dict, rank: int = None) -> str:
        """格式化单个分子卡片"""
        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}.")
        mol_id = mol.get("id") if mol.get("id") is not None else "未知"
        smiles = mol.get("smiles") if mol.get("smiles") is not None else "N/A"
        score = mol.get("score") if mol.get("score") is not None else "N/A"
        docking = mol.get("docking_score") if mol.get("docking_score") is not None else "待计算"
        admet = mol.get("admet_score") if mol.get("admet_score") is not None else "N/A"
        qed = mol.get("qed") if mol.get("qed") is not None else "N/A"
        mw = mol.get("mw") if mol.get("mw") is not None else "N/A"
        logp = mol.get("logp") if mol.get("logp") is not None else "N/A"
        sa = mol.get("sa_score") if mol.get("sa_score") is not None else "N/A"
        
        lines = [
            f"{rank_emoji} **{mol_id}**",
            f"  - SMILES: `{smiles}`",
            f"  - 综合得分: {score}",
            f"  - 对接分数: {docking}",
            f"  - ADMET 分数: {admet}",
            f"  - QED: {qed}",
            f"  - 分子量: {mw}",
            f"  - LogP: {logp}",
            f"  - SA Score: {sa}",
        ]
        return "\n".join(lines)
    
    @staticmethod
    def format_molecule_table(molecules: List[Dict], max_display: int = 10) -> str:
        """格式化分子表格（Markdown）"""
        if not molecules:
            return "暂无分子数据。"
        
        lines = [
            "| 排名 | 分子ID | 综合得分 | 对接分数 | ADMET | QED |",
            "|------|--------|----------|----------|-------|-----|",
        ]
        for i, mol in enumerate(molecules[:max_display], 1):
            score = mol.get("score") if mol.get("score") is not None else "N/A"
            docking = mol.get("docking_score") if mol.get("docking_score") is not None else "待计算"
            admet = mol.get("admet_score") if mol.get("admet_score") is not None else "N/A"
            qed = mol.get("qed") if mol.get("qed") is not None else "N/A"
            mol_id = mol.get("id") if mol.get("id") is not None else f"mol_{i}"
            lines.append(f"| {i} | {mol_id} | {score} | {docking} | {admet} | {qed} |")
        
        if len(molecules) > max_display:
            lines.append(f"\n*... 共 {len(molecules)} 个分子，显示前 {max_display} 个*")
        
        return "\n".join(lines)


class PipelineFormatter:
    """Pipeline 结果格式化器"""
    
    @staticmethod
    def format_pipeline_result(obs: Dict) -> str:
        """格式化 Pipeline 执行结果"""
        target_name = obs.get("target_name", "")
        target_pdb = obs.get("target_pdb", "")
        project_name = obs.get("project_name", "")
        project_id = obs.get("project_id", "N/A")
        num_generated = obs.get("num_generated", 0)
        num_passed = obs.get("num_passed", 0)
        num_failed = obs.get("num_failed", 0)
        elapsed = obs.get("elapsed_seconds", 0)
        status = obs.get("pipeline_status", "unknown")
        
        lines = [
            f"## {target_name} 全流程完成 — 候选分子报告",
            "",
            f"**项目信息**：ID={project_id} | 靶点：**{target_name}** | PDB：**{target_pdb}** | 项目名称：{project_name}",
            "",
            "**Pipeline 执行结果**",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 生成总数 | {num_generated} 个 |",
            f"| 通过筛选 | {num_passed} 个 |",
            f"| 失败 | {num_failed} 个 |",
            f"| 执行耗时 | {elapsed} 秒 |",
            f"| 状态 | {'完成' if status == 'completed' else status} |",
            "",
        ]
        
        top_molecules = obs.get("top_molecules", [])
        if top_molecules:
            lines.append(f"**Top {len(top_molecules)} 候选分子**")
            lines.append("")
            for i, mol in enumerate(top_molecules, 1):
                lines.append(MoleculeFormatter.format_molecule_card(mol, i))
                lines.append("")
        else:
            lines.append("**暂无通过合成筛选的候选分子**")
            lines.append("")
            lines.append("- 所有分子在筛选中失败，建议分析失败原因并调整参数")
            lines.append("- 可尝试：降低 ADMET 阈值、放宽相似度限制、增加生成分子数量")
        
        return "\n".join(lines)


class AdmetFormatter:
    """ADMET 报告格式化器"""
    
    @staticmethod
    def format_admet_result(result: Dict) -> str:
        """格式化 ADMET 分析结果"""
        smiles = result.get("smiles", "N/A")
        canonical = result.get("canonical_smiles", "N/A")
        admet = result.get("admet_result", {})
        metrics = result.get("key_metrics", {})
        drug_likeness = result.get("drug_likeness", "")
        overall_score = result.get("overall_score", "N/A")
        
        lines = [
            f"**ADMET 分析报告**",
            "",
            f"- 输入 SMILES: `{smiles[:50]}...`",
            f"- 标准 SMILES: `{canonical[:50]}...`",
            f"- 药物样性: {drug_likeness}",
            f"- 综合评分: **{overall_score}** (0-100)",
            "",
            "**关键指标**:",
        ]
        
        for key, value in metrics.items():
            lines.append(f"  - {key}: {value}")
        
        lines.append("")
        lines.append("**五维分类详情**:")
        for category, data in admet.items():
            if isinstance(data, dict):
                lines.append(f"  - {category}: {json.dumps(data, ensure_ascii=False)[:100]}")
        
        return "\n".join(lines)


class ComparisonFormatter:
    """分子对比格式化器"""
    
    @staticmethod
    def format_comparison(molecules: List[Dict]) -> str:
        """格式化分子对比结果"""
        if not molecules:
            return "无对比数据。"
        
        lines = [
            "**分子对比结果**",
            "",
            "| 分子 | MW | LogP | TPSA | HBD | HBA | QED |",
            "|------|------|------|------|------|------|------|",
        ]
        for mol in molecules:
            mw = mol.get("mw", "N/A")
            logp = mol.get("logp", "N/A")
            tpsa = mol.get("tpsa", "N/A")
            hbd = mol.get("hbd", "N/A")
            hba = mol.get("hba", "N/A")
            qed = mol.get("qed", "N/A")
            smiles_short = mol.get("smiles", "N/A")[:30] + "..."
            lines.append(f"| {smiles_short} | {mw} | {logp} | {tpsa} | {hbd} | {hba} | {qed} |")
        
        return "\n".join(lines)


class SynthesisFormatter:
    """合成分析格式化器"""
    
    @staticmethod
    def format_synthesis_result(result: Dict) -> str:
        """格式化逆合成分析结果"""
        smiles = result.get("smiles", "N/A")
        num_steps = result.get("num_steps", 0)
        cost = result.get("estimated_cost", "N/A")
        score = result.get("availability_score", "N/A")
        yield_val = result.get("total_yield", "N/A")
        route = result.get("route", {})
        
        lines = [
            f"**逆合成分析**",
            "",
            f"- 目标分子: `{smiles[:50]}...`",
            f"- 合成步数: **{num_steps} 步**",
            f"- 总收率: {yield_val}",
            f"- 估算成本: {cost}",
            f"- 合成可及性: **{score}** (0-1)",
            "",
        ]
        
        steps = route.get("steps", [])
        if steps:
            lines.append("**合成路线**:")
            for i, step in enumerate(steps, 1):
                reagents = ", ".join(step.get("reagents", [])) or "N/A"
                conditions = step.get("conditions", "N/A")
                lines.append(f"{i}. {step.get('reaction_name', '反应')} — 试剂: {reagents} — 条件: {conditions}")
        
        lines.append("")
        lines.append("可及性评分 > 0.5 表示合成难度适中，< 0.3 表示合成难度较大。")
        
        return "\n".join(lines)


class DockingFormatter:
    """对接结果格式化器"""
    
    @staticmethod
    def format_docking_result(result: Dict) -> str:
        """格式化分子对接结果"""
        smiles = result.get("smiles", "N/A")
        affinity = result.get("best_affinity", "N/A")
        poses = result.get("poses", [])
        
        lines = [
            f"**分子对接结果**",
            "",
            f"- 配体: `{smiles[:50]}...`",
            f"- 最佳结合能: **{affinity} kcal/mol**",
            f"- 构象数量: {len(poses)}",
            "",
        ]
        
        if poses:
            lines.append("**Top 3 构象**:")
            for i, pose in enumerate(poses[:3], 1):
                lines.append(f"{i}. 结合能: {pose.get('affinity', 'N/A')} kcal/mol, RMSD: {pose.get('rmsd_ub', 'N/A')}")
        
        lines.append("")
        lines.append("结合能 <-6 kcal/mol 表示较强的结合力，<-8 表示非常强。")
        
        return "\n".join(lines)


class ActivityFormatter:
    """活性预测格式化器"""
    
    @staticmethod
    def format_activity_result(result: Dict) -> str:
        """格式化活性预测结果"""
        smiles = result.get("smiles", "N/A")
        predicted = result.get("predicted_value", "N/A")
        unit = result.get("unit", "N/A")
        confidence = result.get("confidence", "N/A")
        model = result.get("model_used", "N/A")
        
        return (
            f"**活性预测**\n\n"
            f"- 分子: `{smiles[:50]}...`\n"
            f"- 预测活性: **{predicted} {unit}**\n"
            f"- 置信度: {confidence}\n"
            f"- 模型来源: {model}\n\n"
            f"pIC50 > 7 表示高活性（<100 nM），> 8 表示非常强（<10 nM）。"
        )


class FailureFormatter:
    """失败分析格式化器"""
    
    @staticmethod
    def format_failure_analysis(result: Dict) -> str:
        """格式化失败分析结果"""
        total = result.get("total_failed", 0)
        stage_counts = result.get("stage_counts", {})
        reasons = result.get("reasons", {})
        suggestions = result.get("suggestions", [])
        
        lines = [
            f"**失败分析**",
            "",
            f"- 总失败分子: **{total} 个**",
            "",
            "**各阶段失败分布**:",
        ]
        
        for stage, count in stage_counts.items():
            lines.append(f"  - {stage}: {count} 个")
        
        if reasons:
            lines.append("")
            lines.append("**主要失败原因**:")
            for reason, count in reasons.items():
                lines.append(f"  - {reason}: {count} 个")
        
        if suggestions:
            lines.append("")
            lines.append("**优化建议**:")
            for s in suggestions:
                lines.append(f"  - {s}")
        
        return "\n".join(lines)


class UnsupportedRequestFormatter:
    """无法完成请求格式化器"""
    
    @staticmethod
    def format_unsupported(request: str, available_tools: List[str]) -> str:
        """格式化无法完成的请求回复"""
        return (
            f"抱歉，我暂时无法直接完成'{request}'。\n\n"
            f"当前系统支持以下类型的任务：\n"
            f"  - 分子生成与筛选（Pipeline）\n"
            f"  - ADMET 性质预测\n"
            f"  - 分子对接打分\n"
            f"  - 逆合成分析\n"
            f"  - 活性预测与 QSAR 建模\n"
            f"  - 靶点查询与信息检索\n"
            f"  - 3D 结构获取\n\n"
            f"如果您需要湿实验验证（如细胞实验、动物实验），建议：\n"
            f"  1. 先通过本平台筛选出 Top 候选分子\n"
            f"  2. 联系 CRO 公司进行体外/体内验证\n\n"
            f"有什么我可以帮您的吗？"
        )


# 便捷函数：供 executor.py 和 tools.py 直接调用
format_molecule_card = MoleculeFormatter.format_molecule_card
format_molecule_table = MoleculeFormatter.format_molecule_table
format_pipeline_result = PipelineFormatter.format_pipeline_result
format_admet_result = AdmetFormatter.format_admet_result
format_comparison = ComparisonFormatter.format_comparison
format_synthesis_result = SynthesisFormatter.format_synthesis_result
format_docking_result = DockingFormatter.format_docking_result
format_activity_result = ActivityFormatter.format_activity_result
format_failure_analysis = FailureFormatter.format_failure_analysis
format_unsupported = UnsupportedRequestFormatter.format_unsupported
