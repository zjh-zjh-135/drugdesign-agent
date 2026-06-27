import axios from 'axios'

const API_BASE = '/api'

export const builderApi = {
  // 1. 3D 构象生成
  async generateConformer(atoms, bonds) {
    const res = await axios.post(`${API_BASE}/builder/conformer`, { atoms, bonds })
    return res.data
  },

  // 2. ADMET 规则检查
  async checkAdmet(smiles) {
    const res = await axios.post(`${API_BASE}/builder/admet`, { smiles })
    return res.data
  },

  // 3. 骨架跃迁
  async scaffoldHop(atoms, bonds, ringAtoms, targetScaffold) {
    const res = await axios.post(`${API_BASE}/builder/scaffold`, {
      atoms, bonds, ring_atoms: ringAtoms, target_scaffold: targetScaffold
    })
    return res.data
  },

  // 4. 分子对齐
  async alignMolecules(molecules, referenceIndex = 0) {
    const res = await axios.post(`${API_BASE}/builder/align`, {
      molecules, reference_index: referenceIndex
    })
    return res.data
  },

  // 5. 口袋加载
  async loadPocket(pdbContent) {
    const res = await axios.post(`${API_BASE}/builder/pocket`, { pdb_content: pdbContent })
    return res.data
  }
}

export default builderApi
