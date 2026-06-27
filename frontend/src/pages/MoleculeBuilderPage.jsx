import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import builderApi from '../api/builder'

/* ============================================================
   MoleculeBuilder — Professional Molecular Structure Editor
   All 10 features integrated: zoom/pan, force-directed layout,
   SMILES, templates, pseudo-3D, implicit H, bond angles,
   multi-select, charges/lone pairs, collision detection
   ============================================================ */

/* ---------- Scientific Data ---------- */

const VDW_RADII = {
  H: 120, C: 170, N: 155, O: 152, F: 147, P: 180, S: 180, Cl: 175, Br: 185, I: 198,
  B: 192, Si: 210, Na: 227, K: 275, Ca: 231, Mg: 173, Fe: 194, Cu: 196, Zn: 201, Au: 166
}

const COV_RADII = {
  H: 31, C: 76, N: 71, O: 66, F: 57, P: 107, S: 105, Cl: 102, Br: 120, I: 139,
  B: 84, Si: 111, Na: 166, K: 196, Ca: 176, Mg: 141, Fe: 132, Cu: 132, Zn: 122, Au: 136
}

const STD_BOND_LENGTH = {
  'C-C': 154, 'C=C': 134, 'C#C': 120, 'C-H': 109, 'C-O': 143, 'C=O': 122,
  'C-N': 147, 'C=N': 138, 'C#N': 116, 'C-F': 135, 'C-Cl': 177, 'C-Br': 194,
  'C-I': 214, 'C-S': 182, 'C-B': 156, 'C-Si': 185, 'O-H': 96, 'O-O': 148,
  'N-H': 101, 'N-N': 145, 'N-O': 140, 'S-H': 134, 'S-S': 205, 'F-H': 92,
  'Cl-H': 127, 'Br-H': 141, 'I-H': 161, 'B-H': 119, 'Si-H': 148, 'Si-O': 163,
  'Na-Cl': 236, 'K-Cl': 279, 'Ca-O': 240, 'Mg-O': 210, 'Fe-O': 195, 'Cu-O': 195
}

const ATOMIC_WEIGHTS = {
  H: 1.008, C: 12.011, N: 14.007, O: 15.999, F: 18.998, P: 30.974, S: 32.06,
  Cl: 35.45, Br: 79.904, I: 126.9, B: 10.81, Si: 28.085, Na: 22.99, K: 39.098,
  Ca: 40.078, Mg: 24.305, Fe: 55.845, Cu: 63.546, Zn: 65.38, Au: 196.967
}

const VALENCE = {
  H: 1, C: 4, N: 3, O: 2, F: 1, P: 5, S: 6, Cl: 1, Br: 1, I: 1,
  B: 3, Si: 4, Na: 1, K: 1, Ca: 2, Mg: 2, Fe: 2, Cu: 2, Zn: 2, Au: 3
}

const CPK_COLORS = {
  H: '#E8E8E8', C: '#333333', N: '#3050F8', O: '#FF0D0D', F: '#90E050',
  P: '#FF8000', S: '#FFE119', Cl: '#1FF01F', Br: '#A62929', I: '#940094',
  B: '#B5A642', Si: '#8C8C8C', Na: '#AB5CF2', K: '#8F40D4', Ca: '#3DFF00',
  Mg: '#8AFF00', Fe: '#E06633', Cu: '#C78033', Zn: '#7D80B0', Au: '#FFD123'
}

const ELEMENT_NAMES = {
  C: '碳', H: '氢', N: '氮', O: '氧', S: '硫', P: '磷', F: '氟',
  Cl: '氯', Br: '溴', I: '碘', B: '硼', Si: '硅'
}

const ELEMENTS = ['C', 'H', 'N', 'O', 'S', 'P', 'F', 'Cl', 'Br', 'I', 'B', 'Si']

const TEMPLATES = [
  { key: 'benzene',   name: '苯环',     desc: 'C6H6',  formula: 'C6H6' },
  { key: 'cyclohex',  name: '环己烷',   desc: 'C6H12', formula: 'C6H12' },
  { key: 'pyridine',  name: '吡啶',     desc: 'C5H5N', formula: 'C5H5N' },
  { key: 'pyrimidine',name: '嘧啶',     desc: 'C4H4N2',formula: 'C4H4N2' },
  { key: 'furan',     name: '呋喃',     desc: 'C4H4O', formula: 'C4H4O' },
  { key: 'thiophene', name: '噻吩',     desc: 'C4H4S', formula: 'C4H4S' },
  { key: 'imidazole', name: '咪唑',     desc: 'C3H4N2',formula: 'C3H4N2' },
  { key: 'cyclopent', name: '环戊烷',   desc: 'C5H10', formula: 'C5H10' },
  { key: 'cyclohept', name: '环庚烷',   desc: 'C7H14', formula: 'C7H14' },
  { key: 'naphthalene',name:'萘',       desc: 'C10H8', formula: 'C10H8' },
  { key: 'indole',    name: '吲哚',     desc: 'C8H7N', formula: 'C8H7N' },
  { key: 'purine',    name: '嘌呤',     desc: 'C5H4N4',formula: 'C5H4N4' }
]

/* ---------- Pure Helpers ---------- */

let uidCounter = 1
function genId() { return `a_${uidCounter++}` }

function getStdBondLen(e1, e2, type) {
  const k = type === 2 ? `${e1}=${e2}` : type === 3 ? `${e1}#${e2}` : `${e1}-${e2}`
  return STD_BOND_LENGTH[k] || 150
}

function getAtomColor(el) { return CPK_COLORS[el] || '#888' }
function getVdwR(el) { return VDW_RADII[el] || 150 }
function getCovR(el) { return COV_RADII[el] || 100 }
function getValence(el) { return VALENCE[el] || 0 }
function getWeight(el) { return ATOMIC_WEIGHTS[el] || 0 }

function dist2(a, b) { return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 }
function dist(a, b) { return Math.sqrt(dist2(a, b)) }

function bondAngle(atom, n1, n2) {
  const v1 = { x: n1.x - atom.x, y: n1.y - atom.y }
  const v2 = { x: n2.x - atom.x, y: n2.y - atom.y }
  const m1 = Math.sqrt(v1.x ** 2 + v1.y ** 2)
  const m2 = Math.sqrt(v2.x ** 2 + v2.y ** 2)
  if (m1 === 0 || m2 === 0) return 0
  const cos = Math.max(-1, Math.min(1, (v1.x * v2.x + v1.y * v2.y) / (m1 * m2)))
  return Math.acos(cos) * (180 / Math.PI)
}

function formatFormula(counts) {
  const order = ['C', 'H', 'N', 'O', 'S', 'P', 'F', 'Cl', 'Br', 'I', 'B', 'Si']
  let s = ''
  for (const el of order) {
    if (counts[el]) { s += el; if (counts[el] > 1) s += counts[el] }
  }
  for (const el of Object.keys(counts).sort()) {
    if (!order.includes(el) && counts[el]) { s += el; if (counts[el] > 1) s += counts[el] }
  }
  return s || '—'
}

/* ---------- SMILES Parser ---------- */
function parseSmiles(smi) {
  const atoms = [], bonds = []
  let i = 0, prevAtom = null
  const ringClosures = {}
  const stack = []

  function consume() { return smi[i++] }
  function peek() { return smi[i] }

  function parseAtom() {
    let ch = peek()
    if (!ch) return null
    let element = '', charge = 0, hCount = 0
    let aromatic = false

    if (ch === '[') {
      consume() // '['
      // isotope number
      while (peek() >= '0' && peek() <= '9') consume()
      ch = peek()
      if (ch >= 'A' && ch <= 'Z') { element += consume(); if (peek() >= 'a' && peek() <= 'z') element += consume() }
      else if (ch >= 'a' && ch <= 'z') { aromatic = true; element = consume().toUpperCase() }
      while (peek() && peek() !== ']') {
        const c = peek()
        if (c === 'H') { consume(); hCount = 1; if (peek() >= '0' && peek() <= '9') { hCount = 0; while (peek() >= '0' && peek() <= '9') hCount = hCount * 10 + (consume() - '0') } }
        else if (c === '+' || c === '-') { const sign = consume() === '+' ? 1 : -1; let num = 1; if (peek() >= '0' && peek() <= '9') { num = 0; while (peek() >= '0' && peek() <= '9') num = num * 10 + (consume() - '0') } charge = sign * num }
        else consume()
      }
      if (peek() === ']') consume()
    } else if (ch >= 'A' && ch <= 'Z') {
      element = consume()
      if (peek() >= 'a' && peek() <= 'z') element += consume()
    } else if (ch >= 'a' && ch <= 'z') {
      aromatic = true
      const map = { c: 'C', n: 'N', o: 'O', s: 'S', p: 'P', b: 'B' }
      element = map[ch] || ch.toUpperCase()
      consume()
    } else return null

    const atom = { id: genId(), element, x: 0, y: 0, z: 0, charge, implicitH: hCount }
    return atom
  }

  function parseBond() {
    const ch = peek()
    if (ch === '=') { consume(); return 2 }
    if (ch === '#') { consume(); return 3 }
    if (ch === '.') { consume(); return 0 }
    if (ch === '-' || ch === '/' || ch === '\\') { consume(); return 1 }
    return 1
  }

  while (i < smi.length) {
    const ch = peek()
    if (!ch) break

    if (ch === '(') { consume(); stack.push(prevAtom); continue }
    if (ch === ')') { consume(); prevAtom = stack.pop() || prevAtom; continue }

    if (ch >= '1' && ch <= '9') {
      const d = consume()
      if (ringClosures[d]) {
        const from = ringClosures[d]
        if (from && prevAtom) bonds.push({ id: genId(), from: from.id, to: prevAtom.id, type: 1, stereo: 'none' })
        delete ringClosures[d]
      } else { ringClosures[d] = prevAtom }
      continue
    }

    if (ch === '%') {
      consume()
      let numStr = ''
      while (peek() >= '0' && peek() <= '9') numStr += consume()
      const key = '%' + numStr
      if (ringClosures[key]) {
        const from = ringClosures[key]
        if (from && prevAtom) bonds.push({ id: genId(), from: from.id, to: prevAtom.id, type: 1, stereo: 'none' })
        delete ringClosures[key]
      } else { ringClosures[key] = prevAtom }
      continue
    }

    const bType = parseBond()
    if (bType === 0) { prevAtom = null; continue }

    const atom = parseAtom()
    if (!atom) { consume(); continue }

    atoms.push(atom)
    if (prevAtom && bType > 0) {
      bonds.push({ id: genId(), from: prevAtom.id, to: atom.id, type: bType, stereo: 'none' })
    }
    prevAtom = atom
  }

  // 2D layout
  if (atoms.length > 0) {
    const adj = {}
    for (const a of atoms) adj[a.id] = []
    for (const b of bonds) { adj[b.from].push(b.to); adj[b.to].push(b.from) }
    const placed = new Set([atoms[0].id])
    atoms[0].x = 0; atoms[0].y = 0
    const q = [atoms[0]]
    let baseAngle = 0
    while (q.length > 0) {
      const cur = q.shift()
      const nbrs = adj[cur.id].filter(nid => !placed.has(nid))
      if (nbrs.length === 0) continue
      const step = nbrs.length > 1 ? (2 * Math.PI / nbrs.length) : Math.PI / 3
      for (let j = 0; j < nbrs.length; j++) {
        const nid = nbrs[j]
        const nb = atoms.find(a => a.id === nid)
        if (!nb) continue
        const a = baseAngle + j * step
        const len = 120
        nb.x = cur.x + Math.cos(a) * len
        nb.y = cur.y + Math.sin(a) * len
        placed.add(nid)
        q.push(nb)
      }
      baseAngle += Math.PI / 4
    }
    const cx = atoms.reduce((s, a) => s + a.x, 0) / atoms.length
    const cy = atoms.reduce((s, a) => s + a.y, 0) / atoms.length
    for (const a of atoms) { a.x -= cx; a.y -= cy }
  }
  return { atoms, bonds }
}

/* ---------- SMILES Generator ---------- */
function genSmiles(atoms, bonds) {
  if (atoms.length === 0) return ''
  const adj = {}
  for (const a of atoms) adj[a.id] = []
  const bondMap = {}
  for (const b of bonds) {
    adj[b.from].push({ to: b.to, type: b.type })
    adj[b.to].push({ to: b.from, type: b.type })
    bondMap[b.from + '_' + b.to] = b.type
    bondMap[b.to + '_' + b.from] = b.type
  }
  const visited = new Set()
  const ringLabels = {}
  let nextRing = 1

  function dfs(id) {
    if (visited.has(id)) {
      const label = ringLabels[id] || (nextRing++)
      ringLabels[id] = label
      return label <= 9 ? String(label) : '%' + String(label).padStart(2, '0')
    }
    visited.add(id)
    const a = atoms.find(at => at.id === id)
    if (!a) return ''

    let s = a.element
    const nbrs = adj[id] || []
    const branches = []
    let mainNext = null

    for (const nb of nbrs) {
      if (!visited.has(nb.to)) {
        if (!mainNext) mainNext = nb
        else branches.push(nb)
      } else {
        const label = ringLabels[id + '_' + nb.to] || (nextRing++)
        ringLabels[id + '_' + nb.to] = label
        ringLabels[nb.to + '_' + id] = label
        s += label <= 9 ? String(label) : '%' + String(label).padStart(2, '0')
      }
    }

    for (const br of branches) {
      const bc = br.type === 2 ? '=' : br.type === 3 ? '#' : ''
      s += '(' + bc + dfs(br.to) + ')'
    }
    if (mainNext) {
      const bc = mainNext.type === 2 ? '=' : mainNext.type === 3 ? '#' : ''
      s += bc + dfs(mainNext.to)
    }
    return s
  }

  return dfs(atoms[0].id)
}

/* ---------- Template Builder ---------- */
function buildTemplate(key) {
  const atoms = [], bonds = []
  const R = 100
  function addAtom(el, x, y) { const a = { id: genId(), element: el, x, y, z: 0, charge: 0, implicitH: 0 }; atoms.push(a); return a }
  function addBond(a1, a2, type = 1) { bonds.push({ id: genId(), from: a1.id, to: a2.id, type, stereo: 'none' }) }
  function ring(n, els, start = -Math.PI / 2) {
    const pts = []
    for (let i = 0; i < n; i++) { const a = start + (2 * Math.PI * i) / n; pts.push(addAtom(els[i] || 'C', Math.cos(a) * R, Math.sin(a) * R)) }
    for (let i = 0; i < n; i++) addBond(pts[i], pts[(i + 1) % n])
    return pts
  }

  if (key === 'benzene') ring(6, ['C','C','C','C','C','C'])
  else if (key === 'cyclohex') ring(6, ['C','C','C','C','C','C'])
  else if (key === 'pyridine') ring(6, ['C','N','C','C','C','C'])
  else if (key === 'pyrimidine') ring(6, ['C','N','C','N','C','C'])
  else if (key === 'furan') ring(5, ['C','C','O','C','C'])
  else if (key === 'thiophene') ring(5, ['C','C','S','C','C'])
  else if (key === 'imidazole') ring(5, ['C','N','C','N','C'])
  else if (key === 'cyclopent') ring(5, ['C','C','C','C','C'])
  else if (key === 'cyclohept') ring(7, ['C','C','C','C','C','C','C'])
  else if (key === 'naphthalene') {
    const p1 = ring(6, ['C','C','C','C','C','C'])
    const off = R * 0.866
    const p2 = [addAtom('C', off * 1.5, -R * 0.5), addAtom('C', off * 2.5, -R * 0.5), addAtom('C', off * 3, R * 0.5), addAtom('C', off * 2.5, R * 1.5), addAtom('C', off * 1.5, R * 1.5), addAtom('C', off, R * 0.5)]
    addBond(p1[1], p2[0]); addBond(p2[0], p2[1]); addBond(p2[1], p2[2]); addBond(p2[2], p2[3]); addBond(p2[3], p2[4]); addBond(p2[4], p2[5]); addBond(p2[5], p1[4])
  } else if (key === 'indole') {
    const p1 = ring(6, ['C','C','C','C','C','C'])
    const p2 = [addAtom('C', -R * 0.6, -R * 1.3), addAtom('N', R * 0.6, -R * 1.3), addAtom('C', 0, -R * 2.1)]
    addBond(p2[0], p2[1]); addBond(p2[1], p2[2]); addBond(p2[2], p2[0])
    addBond(p2[0], p1[0]); addBond(p2[1], p1[1])
  } else if (key === 'purine') {
    const p1 = ring(6, ['C','N','C','N','C','C'])
    const p2 = [addAtom('N', -R * 0.5, -R * 1.3), addAtom('C', R * 0.5, -R * 1.3), addAtom('N', 0, -R * 2.1)]
    addBond(p2[0], p2[1]); addBond(p2[1], p2[2]); addBond(p2[2], p2[0])
    addBond(p2[0], p1[0]); addBond(p2[1], p1[1])
  }
  return { atoms, bonds }
}

/* ============================================================
   MAIN COMPONENT
   ============================================================ */

export default function MoleculeBuilderPage() {
  /* ----- State (ALL at top level) ----- */
  const [atoms, setAtoms] = useState([])
  const [bonds, setBonds] = useState([])
  const [viewport, setViewport] = useState({ scale: 1, panX: 0, panY: 0 })
  const [tool, setTool] = useState('select')
  const [bondType, setBondType] = useState(1)
  const [placeEl, setPlaceEl] = useState('C')
  const [selIds, setSelIds] = useState(new Set())
  const [hoverAtomId, setHoverAtomId] = useState(null)
  const [hoverBondId, setHoverBondId] = useState(null)
  const [smilesInput, setSmilesInput] = useState('')
  const [showImplicitH, setShowImplicitH] = useState(true)
  const [showCollision, setShowCollision] = useState(false)
  const [leftTab, setLeftTab] = useState('atoms')
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [dragCurr, setDragCurr] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0, vpX: 0, vpY: 0 })
  const [bondStartId, setBondStartId] = useState(null)
  const [mouseWorld, setMouseWorld] = useState({ x: 0, y: 0 })
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [chargeVal, setChargeVal] = useState(0)
  const [boxSelect, setBoxSelect] = useState(null)
  const [copyBuf, setCopyBuf] = useState({ atoms: [], bonds: [] })
  const [stereoMode, setStereoMode] = useState('none')

  /* ----- 5大高级功能状态 ----- */
  const [admetData, setAdmetData] = useState(null)
  const [admetLoading, setAdmetLoading] = useState(false)
  const [showAdmetPanel, setShowAdmetPanel] = useState(false)
  const [conformerData, setConformerData] = useState(null)
  const [conformerLoading, setConformerLoading] = useState(false)
  const [show3DPanel, setShow3DPanel] = useState(false)
  const [scaffoldTarget, setScaffoldTarget] = useState('')
  const [showScaffoldPanel, setShowScaffoldPanel] = useState(false)
  const [pocketData, setPocketData] = useState(null)
  const [showPocketPanel, setShowPocketPanel] = useState(false)
  const [pdbInput, setPdbInput] = useState('')

  const svgRef = useRef(null)
  const canvasRef = useRef(null)

  /* ----- Coordinate transforms ----- */
  const worldToScreen = useCallback((x, y) => ({
    x: x * viewport.scale + viewport.panX,
    y: y * viewport.scale + viewport.panY
  }), [viewport])

  const screenToWorld = useCallback((sx, sy) => ({
    x: (sx - viewport.panX) / viewport.scale,
    y: (sy - viewport.panY) / viewport.scale
  }), [viewport])

  const getMouseWorld = useCallback((e) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
  }, [screenToWorld])

  /* ----- Computed data (useMemo) ----- */
  const implicitH = useMemo(() => {
    const map = {}
    for (const a of atoms) {
      const v = getValence(a.element)
      let used = Math.abs(a.charge)
      for (const b of bonds) {
        if (b.from === a.id || b.to === a.id) used += b.type
      }
      map[a.id] = Math.max(0, v - used)
    }
    return map
  }, [atoms, bonds])

  const formulaData = useMemo(() => {
    const counts = {}
    let mw = 0
    for (const a of atoms) {
      const hc = showImplicitH ? implicitH[a.id] || 0 : 0
      counts[a.element] = (counts[a.element] || 0) + 1
      counts['H'] = (counts['H'] || 0) + hc
      mw += getWeight(a.element)
      mw += hc * 1.008
    }
    return { formula: formatFormula(counts), mw: mw.toFixed(2) }
  }, [atoms, implicitH, showImplicitH])

  const collisionInfo = useMemo(() => {
    const info = {}
    if (!showCollision) return info
    for (let i = 0; i < atoms.length; i++) {
      for (let j = i + 1; j < atoms.length; j++) {
        const a = atoms[i], b = atoms[j]
        const threshold = (getVdwR(a.element) + getVdwR(b.element)) * 0.5
        if (dist(a, b) < threshold) {
          info[a.id] = { collision: true, msg: '原子间距过小' }
          info[b.id] = { collision: true, msg: '原子间距过小' }
        }
      }
    }
    for (const b of bonds) {
      const a1 = atoms.find(a => a.id === b.from)
      const a2 = atoms.find(a => a.id === b.to)
      if (!a1 || !a2) continue
      const ideal = getStdBondLen(a1.element, a2.element, b.type)
      const d = dist(a1, a2)
      if (d < ideal * 0.7 || d > ideal * 1.5) {
        info[b.id] = { bondWarn: true, msg: `键长异常: ${d.toFixed(1)} pm (标准 ${ideal} pm)` }
      }
    }
    for (const a of atoms) {
      const v = getValence(a.element)
      let used = Math.abs(a.charge)
      for (const b of bonds) if (b.from === a.id || b.to === a.id) used += b.type
      if (used > v) info[a.id] = { ...info[a.id], valence: true, msg: `价键数超出: ${used}/${v}` }
    }
    return info
  }, [atoms, bonds, showCollision])

  const selectedAtom = useMemo(() => {
    const arr = Array.from(selIds)
    return arr.length === 1 ? atoms.find(a => a.id === arr[0]) || null : null
  }, [selIds, atoms])

  const bondAngles = useMemo(() => {
    if (!selectedAtom) return []
    const nbrs = bonds.filter(b => b.from === selectedAtom.id || b.to === selectedAtom.id)
      .map(b => atoms.find(a => a.id === (b.from === selectedAtom.id ? b.to : b.from)))
      .filter(Boolean)
    const angles = []
    for (let i = 0; i < nbrs.length; i++) {
      for (let j = i + 1; j < nbrs.length; j++) {
        angles.push({ pair: `${nbrs[i].element}-${selectedAtom.element}-${nbrs[j].element}`, val: bondAngle(selectedAtom, nbrs[i], nbrs[j]).toFixed(1) })
      }
    }
    return angles
  }, [selectedAtom, bonds, atoms])

  const selectedBonds = useMemo(() => {
    return bonds.filter(b => selIds.has(b.from) || selIds.has(b.to))
  }, [bonds, selIds])

  const sortedAtoms = useMemo(() => [...atoms].sort((a, b) => a.z - b.z), [atoms])

  /* ----- Actions ----- */
  const addAtom = useCallback((el, x, y) => {
    const id = genId()
    setAtoms(prev => [...prev, { id, element: el, x, y, z: 0, charge: 0, implicitH: 0 }])
    return id
  }, [])

  const addBond = useCallback((from, to, type) => {
    if (from === to) return
    const exists = bonds.find(b => (b.from === from && b.to === to) || (b.from === to && b.to === from))
    if (!exists) setBonds(prev => [...prev, { id: genId(), from, to, type, stereo: 'none' }])
  }, [bonds])

  const delAtom = useCallback((id) => {
    setAtoms(prev => prev.filter(a => a.id !== id))
    setBonds(prev => prev.filter(b => b.from !== id && b.to !== id))
    setSelIds(prev => { const n = new Set(prev); n.delete(id); return n })
  }, [])

  const delBond = useCallback((id) => {
    setBonds(prev => prev.filter(b => b.id !== id))
  }, [])

  const clearAll = useCallback(() => { setAtoms([]); setBonds([]); setSelIds(new Set()); setBondStartId(null) }, [])

  const optimizeLayout = useCallback(() => {
    if (atoms.length === 0) return
    setIsOptimizing(true)
    let iteration = 0
    const maxIter = 200
    const k = 0.3
    const rep = 80000
    const damp = 0.85

    const animate = () => {
      let totalDelta = 0
      const forces = atoms.map(() => ({ fx: 0, fy: 0 }))

      for (let i = 0; i < atoms.length; i++) {
        for (let j = i + 1; j < atoms.length; j++) {
          const dx = atoms[i].x - atoms[j].x
          const dy = atoms[i].y - atoms[j].y
          const d2 = dx * dx + dy * dy
          const d = Math.sqrt(d2) || 1
          const f = rep / d2
          const fx = (dx / d) * f, fy = (dy / d) * f
          forces[i].fx += fx; forces[i].fy += fy
          forces[j].fx -= fx; forces[j].fy -= fy
        }
      }

      for (const b of bonds) {
        const a1 = atoms.find(a => a.id === b.from)
        const a2 = atoms.find(a => a.id === b.to)
        if (!a1 || !a2) continue
        const dx = a2.x - a1.x, dy = a2.y - a1.y
        const d = Math.sqrt(dx * dx + dy * dy) || 1
        const ideal = getStdBondLen(a1.element, a2.element, b.type)
        const f = k * (d - ideal)
        const fx = (dx / d) * f, fy = (dy / d) * f
        const i1 = atoms.indexOf(a1), i2 = atoms.indexOf(a2)
        forces[i1].fx -= fx; forces[i1].fy -= fy
        forces[i2].fx += fx; forces[i2].fy += fy
      }

      for (let i = 0; i < atoms.length; i++) {
        const dx = forces[i].fx * damp
        const dy = forces[i].fy * damp
        atoms[i].x += dx
        atoms[i].y += dy
        totalDelta += Math.abs(dx) + Math.abs(dy)
      }

      iteration++
      setAtoms([...atoms.map(a => ({ ...a }))])

      if (iteration < maxIter && totalDelta > 0.05) {
        requestAnimationFrame(animate)
      } else {
        setIsOptimizing(false)
      }
    }
    requestAnimationFrame(animate)
  }, [atoms, bonds])

  const importSmiles = useCallback(() => {
    if (!smilesInput.trim()) return
    const res = parseSmiles(smilesInput.trim())
    setAtoms(res.atoms)
    setBonds(res.bonds)
    setSelIds(new Set())
  }, [smilesInput])

  const exportSmiles = useCallback(() => {
    if (atoms.length === 0) return
    setSmilesInput(genSmiles(atoms, bonds))
  }, [atoms, bonds])

  const insertTemplate = useCallback((key) => {
    const tpl = buildTemplate(key)
    const cw = canvasRef.current?.clientWidth || 800
    const ch = canvasRef.current?.clientHeight || 600
    const center = screenToWorld(cw / 2, ch / 2)
    const newAtoms = tpl.atoms.map(a => ({ ...a, x: a.x + center.x, y: a.y + center.y }))
    setAtoms(prev => [...prev, ...newAtoms])
    setBonds(prev => [...prev, ...tpl.bonds])
  }, [screenToWorld])

  const cycleCharge = useCallback(() => {
    const vals = [0, 1, 2, -1, -2]
    const idx = vals.indexOf(chargeVal)
    setChargeVal(vals[(idx + 1) % vals.length])
  }, [chargeVal])

  const applyCharge = useCallback((atomId) => {
    setAtoms(prev => prev.map(a => a.id === atomId ? { ...a, charge: chargeVal } : a))
  }, [chargeVal])

  /* ----- Mouse handlers ----- */
  const hitTest = useCallback((pos) => {
    for (let i = atoms.length - 1; i >= 0; i--) {
      const a = atoms[i]
      const r = getCovR(a.element) / 2.5
      if (dist2(a, pos) <= r * r) return a
    }
    return null
  }, [atoms])

  const handleMouseDown = useCallback((e) => {
    // Pan: middle button
    if (e.button === 1) {
      e.preventDefault()
      setIsPanning(true)
      setPanStart({ x: e.clientX, y: e.clientY, vpX: viewport.panX, vpY: viewport.panY })
      return
    }
    if (e.button !== 0) return

    const pos = getMouseWorld(e)
    setMouseWorld(pos)
    setDragStart(pos)
    setDragCurr(pos)

    const hit = hitTest(pos)

    if (tool === 'select') {
      if (e.shiftKey) {
        if (hit) {
          setSelIds(prev => { const n = new Set(prev); if (n.has(hit.id)) n.delete(hit.id); else n.add(hit.id); return n })
        } else {
          setBoxSelect({ x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y })
        }
      } else if (hit) {
        if (selIds.has(hit.id)) {
          setIsDragging(true)
        } else {
          setSelIds(new Set([hit.id]))
          setIsDragging(true)
        }
      } else {
        setSelIds(new Set())
        setBoxSelect({ x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y })
      }
    } else if (tool === 'place') {
      if (!hit) {
        addAtom(placeEl, pos.x, pos.y)
      } else if (chargeVal !== 0) {
        applyCharge(hit.id)
      }
    } else if (tool === 'bond') {
      if (hit) {
        if (!bondStartId) {
          setBondStartId(hit.id)
        } else if (bondStartId !== hit.id) {
          addBond(bondStartId, hit.id, bondType)
          setBondStartId(null)
        } else {
          setBondStartId(null)
        }
      } else {
        setBondStartId(null)
      }
    }
  }, [tool, hitTest, selIds, bondStartId, bondType, placeEl, chargeVal, addAtom, addBond, applyCharge, viewport, getMouseWorld])

  const handleMouseMove = useCallback((e) => {
    const pos = getMouseWorld(e)
    setMouseWorld(pos)

    if (isPanning) {
      const dx = e.clientX - panStart.x
      const dy = e.clientY - panStart.y
      setViewport(prev => ({ ...prev, panX: panStart.vpX + dx, panY: panStart.vpY + dy }))
      return
    }

    if (isDragging && selIds.size > 0) {
      const dx = pos.x - dragStart.x
      const dy = pos.y - dragStart.y
      setDragStart(pos)
      setAtoms(prev => prev.map(a => selIds.has(a.id) ? { ...a, x: a.x + dx, y: a.y + dy } : a))
    } else if (boxSelect) {
      setDragCurr(pos)
      setBoxSelect(prev => prev ? { ...prev, x2: pos.x, y2: pos.y } : null)
    }
  }, [isPanning, isDragging, selIds, dragStart, panStart, boxSelect, getMouseWorld])

  const handleMouseUp = useCallback(() => {
    if (isPanning) setIsPanning(false)
    if (isDragging) setIsDragging(false)
    if (boxSelect) {
      const minX = Math.min(boxSelect.x1, boxSelect.x2)
      const maxX = Math.max(boxSelect.x1, boxSelect.x2)
      const minY = Math.min(boxSelect.y1, boxSelect.y2)
      const maxY = Math.max(boxSelect.y1, boxSelect.y2)
      const inside = atoms.filter(a => a.x >= minX && a.x <= maxX && a.y >= minY && a.y <= maxY)
      setSelIds(prev => { const n = new Set(prev); for (const a of inside) n.add(a.id); return n })
      setBoxSelect(null)
    }
  }, [isPanning, isDragging, boxSelect, atoms])

  const handleWheel = useCallback((e) => {
    e.preventDefault()
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left, my = e.clientY - rect.top
    const before = screenToWorld(mx, my)
    const factor = e.deltaY < 0 ? 1.15 : 0.87
    const newScale = Math.max(0.1, Math.min(10, viewport.scale * factor))
    setViewport({ scale: newScale, panX: mx - before.x * newScale, panY: my - before.y * newScale })
  }, [viewport.scale, screenToWorld])

  /* ----- Keyboard ----- */
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const ids = Array.from(selIds)
        if (ids.length > 0) {
          setAtoms(prev => prev.filter(a => !ids.includes(a.id)))
          setBonds(prev => prev.filter(b => !ids.includes(b.from) && !ids.includes(b.to)))
          setSelIds(new Set())
        }
      }
      if (e.key === 'Escape') { setSelIds(new Set()); setBondStartId(null); }
      if (e.key === '1') setBondType(1)
      if (e.key === '2') setBondType(2)
      if (e.key === '3') setBondType(3)
      if (e.key === 's' || e.key === 'S') setTool('select')
      if (e.key === 'b' || e.key === 'B') setTool('bond')
      if (e.key === 'p' || e.key === 'P') setTool('place')
      if (e.ctrlKey && e.key === 'c') {
        const selAtoms = atoms.filter(a => selIds.has(a.id))
        const idMap = {}
        const newAtoms = selAtoms.map(a => { const na = { ...a, id: genId() }; idMap[a.id] = na.id; return na })
        const newBonds = bonds.filter(b => selIds.has(b.from) && selIds.has(b.to)).map(b => ({ ...b, id: genId(), from: idMap[b.from], to: idMap[b.to] }))
        setCopyBuf({ atoms: newAtoms, bonds: newBonds })
      }
      if (e.ctrlKey && e.key === 'v') {
        if (copyBuf.atoms.length > 0) {
          const pasted = copyBuf.atoms.map(a => ({ ...a, x: a.x + 40, y: a.y + 40 }))
          setAtoms(prev => [...prev, ...pasted])
          setBonds(prev => [...prev, ...copyBuf.bonds])
          setSelIds(new Set(pasted.map(a => a.id)))
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selIds, atoms, bonds, copyBuf])

  /* ----- Zoom controls ----- */
  const zoomIn = useCallback(() => setViewport(p => ({ ...p, scale: Math.min(10, p.scale * 1.2) })), [])
  const zoomOut = useCallback(() => setViewport(p => ({ ...p, scale: Math.max(0.1, p.scale / 1.2) })), [])
  const zoomFit = useCallback(() => {
    if (atoms.length === 0) return
    const xs = atoms.map(a => a.x), ys = atoms.map(a => a.y)
    const minX = Math.min(...xs), maxX = Math.max(...xs)
    const minY = Math.min(...ys), maxY = Math.max(...ys)
    const cw = canvasRef.current?.clientWidth || 800
    const ch = canvasRef.current?.clientHeight || 600
    const pad = 60
    const scale = Math.min((cw - pad * 2) / ((maxX - minX) || 1), (ch - pad * 2) / ((maxY - minY) || 1), 5)
    setViewport({ scale, panX: (cw - (maxX + minX) * scale) / 2, panY: (ch - (maxY + minY) * scale) / 2 })
  }, [atoms])

  /* ----- 5大高级功能调用 ----- */
  const checkAdmetNow = useCallback(async () => {
    if (atoms.length === 0) return
    const smi = genSmiles(atoms, bonds)
    if (!smi) return
    setAdmetLoading(true)
    setShowAdmetPanel(true)
    try {
      const res = await builderApi.checkAdmet(smi)
      setAdmetData(res)
    } catch (e) {
      setAdmetData({ error: e.message })
    }
    setAdmetLoading(false)
  }, [atoms, bonds])

  const generate3D = useCallback(async () => {
    if (atoms.length === 0) return
    setConformerLoading(true)
    setShow3DPanel(true)
    try {
      const res = await builderApi.generateConformer(atoms, bonds)
      setConformerData(res)
    } catch (e) {
      setConformerData({ error: e.message })
    }
    setConformerLoading(false)
  }, [atoms, bonds])

  const doScaffoldHop = useCallback(async (target) => {
    if (selIds.size < 3) return
    const ringIds = Array.from(selIds)
    try {
      const res = await builderApi.scaffoldHop(atoms, bonds, ringIds, target)
      if (res.success) {
        setAtoms(res.atoms)
        setBonds(res.bonds)
        setSelIds(new Set())
      }
    } catch (e) {
      console.error('Scaffold hop failed:', e)
    }
    setShowScaffoldPanel(false)
  }, [atoms, bonds, selIds])

  const loadPocket = useCallback(async () => {
    if (!pdbInput.trim()) return
    try {
      const res = await builderApi.loadPocket(pdbInput.trim())
      setPocketData(res)
    } catch (e) {
      setPocketData({ error: e.message })
    }
  }, [pdbInput])

  /* ----- Tooltip ----- */
  const tooltip = useMemo(() => {
    if (hoverBondId) {
      const b = bonds.find(bo => bo.id === hoverBondId)
      if (!b) return null
      const a1 = atoms.find(a => a.id === b.from), a2 = atoms.find(a => a.id === b.to)
      if (!a1 || !a2) return null
      const d = dist(a1, a2), ideal = getStdBondLen(a1.element, a2.element, b.type)
      const t = b.type === 2 ? '双键' : b.type === 3 ? '三键' : '单键'
      return `${a1.element}-${a2.element} ${t} | 实测: ${d.toFixed(1)} pm | 标准: ${ideal} pm | 偏差: ${((d - ideal) / ideal * 100).toFixed(1)}%`
    }
    if (hoverAtomId) {
      const a = atoms.find(at => at.id === hoverAtomId)
      if (!a) return null
      const c = collisionInfo[a.id]
      return c ? `${a.element} | ${c.msg}` : `${a.element} | (${a.x.toFixed(1)}, ${a.y.toFixed(1)}) | VDW: ${getVdwR(a.element)} pm`
    }
    return null
  }, [hoverBondId, hoverAtomId, atoms, bonds, collisionInfo])

  /* ----- Render bond ----- */
  const renderBond = useCallback((b) => {
    const a1 = atoms.find(a => a.id === b.from)
    const a2 = atoms.find(a => a.id === b.to)
    if (!a1 || !a2) return null
    const s1 = worldToScreen(a1.x, a1.y)
    const s2 = worldToScreen(a2.x, a2.y)
    const isHov = hoverBondId === b.id
    const col = isHov ? '#2563eb' : '#475569'
    const sw = isHov ? 3.5 : 2.5

    const dx = s2.x - s1.x, dy = s2.y - s1.y
    const len = Math.sqrt(dx * dx + dy * dy) || 1
    const nx = -dy / len, ny = dx / len
    const off = 3 * viewport.scale

    if (b.stereo === 'wedge') {
      const w = 6 * viewport.scale
      return (
        <polygon key={b.id} points={`${s1.x},${s1.y} ${s2.x + nx * w},${s2.y + ny * w} ${s2.x - nx * w},${s2.y - ny * w}`}
          fill={col} opacity={0.9} stroke="none"
          onMouseEnter={() => setHoverBondId(b.id)} onMouseLeave={() => setHoverBondId(null)} />
      )
    }

    if (b.type === 2) {
      return (
        <g key={b.id} onMouseEnter={() => setHoverBondId(b.id)} onMouseLeave={() => setHoverBondId(null)}>
          <line x1={s1.x + nx * off} y1={s1.y + ny * off} x2={s2.x + nx * off} y2={s2.y + ny * off} stroke={col} strokeWidth={sw} />
          <line x1={s1.x - nx * off} y1={s1.y - ny * off} x2={s2.x - nx * off} y2={s2.y - ny * off} stroke={col} strokeWidth={sw} />
        </g>
      )
    }
    if (b.type === 3) {
      return (
        <g key={b.id} onMouseEnter={() => setHoverBondId(b.id)} onMouseLeave={() => setHoverBondId(null)}>
          <line x1={s1.x} y1={s1.y} x2={s2.x} y2={s2.y} stroke={col} strokeWidth={sw} />
          <line x1={s1.x + nx * off} y1={s1.y + ny * off} x2={s2.x + nx * off} y2={s2.y + ny * off} stroke={col} strokeWidth={sw} />
          <line x1={s1.x - nx * off} y1={s1.y - ny * off} x2={s2.x - nx * off} y2={s2.y - ny * off} stroke={col} strokeWidth={sw} />
        </g>
      )
    }
    return (
      <line key={b.id} x1={s1.x} y1={s1.y} x2={s2.x} y2={s2.y} stroke={col} strokeWidth={sw}
        onMouseEnter={() => setHoverBondId(b.id)} onMouseLeave={() => setHoverBondId(null)} />
    )
  }, [atoms, worldToScreen, hoverBondId, viewport.scale])

  /* ----- Render atom ----- */
  const renderAtom = useCallback((a) => {
    const isH = a.element === 'H'
    if (isH && showImplicitH) return null

    const s = worldToScreen(a.x, a.y)
    const baseR = getCovR(a.element) / 2.5
    const r = baseR * viewport.scale * (1 + a.z * 0.05)
    const opacity = 0.6 + 0.4 / (1 + Math.abs(a.z) * 0.3)
    const color = getAtomColor(a.element)
    const isSel = selIds.has(a.id)
    const isHov = hoverAtomId === a.id
    const isLight = a.element === 'H' || a.element === 'Na' || a.element === 'K' || a.element === 'Ca' || a.element === 'Mg'
    const colInfo = collisionInfo[a.id] || {}

    return (
      <g key={a.id} opacity={opacity} style={{ cursor: tool === 'select' ? 'pointer' : 'crosshair' }}>
        {/* Collision glow */}
        {colInfo.collision && (
          <circle cx={s.x} cy={s.y} r={r + 6} fill="none" stroke="#ef4444" strokeWidth={2} opacity={0.5} />
        )}
        {/* Selection rect */}
        {isSel && (
          <rect x={s.x - r - 4} y={s.y - r - 4} width={(r + 4) * 2} height={(r + 4) * 2}
            fill="none" stroke="#3b82f6" strokeWidth={2} rx={4} />
        )}
        {/* Bond start indicator */}
        {bondStartId === a.id && (
          <circle cx={s.x} cy={s.y} r={r + 8} fill="none" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 2" />
        )}
        {/* Shadow */}
        <circle cx={s.x + 1} cy={s.y + 2} r={r} fill="rgba(0,0,0,0.1)" />
        {/* Atom sphere */}
        <circle cx={s.x} cy={s.y} r={r} fill={color} stroke={isHov ? '#2563eb' : isLight ? '#94a3b8' : '#1e293b'} strokeWidth={isHov ? 2 : 1}
          onMouseEnter={() => setHoverAtomId(a.id)} onMouseLeave={() => setHoverAtomId(null)}
          onMouseDown={(e) => { e.stopPropagation(); handleMouseDown(e) }}
        />
        {/* 3D highlight */}
        <ellipse cx={s.x - r * 0.3} cy={s.y - r * 0.35} rx={r * 0.4} ry={r * 0.3} fill="rgba(255,255,255,0.25)" />
        {/* Element symbol */}
        <text x={s.x} y={s.y + 1} textAnchor="middle" dominantBaseline="central"
          fill={isLight ? '#0f172a' : '#f8fafc'} fontSize={Math.max(8, r * 0.7)} fontWeight="700" pointerEvents="none">{a.element}</text>
        {/* Implicit H count */}
        {showImplicitH && implicitH[a.id] > 0 && (
          <text x={s.x + r + 3} y={s.y - r * 0.2} textAnchor="start" dominantBaseline="central"
            fill="#0f172a" fontSize={Math.max(7, r * 0.45)} pointerEvents="none">H{implicitH[a.id] > 1 ? implicitH[a.id] : ''}</text>
        )}
        {/* Charge */}
        {a.charge !== 0 && (
          <g transform={`translate(${s.x + r + 2}, ${s.y - r - 2})`}>
            <circle r={7} fill="#f8fafc" stroke="#0f172a" strokeWidth={1} />
            <text x={0} y={0.5} textAnchor="middle" dominantBaseline="central" fill="#0f172a" fontSize={9} fontWeight="700">{a.charge > 0 ? '+' : ''}{a.charge}</text>
          </g>
        )}
        {/* Valence warning */}
        {colInfo.valence && (
          <text x={s.x + r + 4} y={s.y + r + 4} textAnchor="start" dominantBaseline="central"
            fill="#ef4444" fontSize={12} fontWeight="700">!</text>
        )}
        {/* Lone pairs */}
        {['O', 'N', 'S', 'P', 'Cl', 'Br', 'I'].includes(a.element) && !isH && (
          <g pointerEvents="none">
            <circle cx={s.x - r * 0.6} cy={s.y - r * 0.6} r={2} fill="#0f172a" opacity={0.5} />
            <circle cx={s.x - r * 0.4} cy={s.y - r * 0.8} r={2} fill="#0f172a" opacity={0.5} />
          </g>
        )}
      </g>
    )
  }, [worldToScreen, viewport.scale, selIds, hoverAtomId, showImplicitH, implicitH, collisionInfo, tool, bondStartId, handleMouseDown])

  /* ============================================================
     JSX
     ============================================================ */
  return (
    <div className="h-full flex flex-col select-none bg-slate-50">
      {/* ====== Toolbar ====== */}
      <div className="bg-white border-b border-slate-200 px-3 py-2 flex items-center gap-2 shrink-0">
        <div className="flex items-center gap-1.5 mr-2">
          <div className="w-5 h-5 rounded bg-slate-800 flex items-center justify-center">
            <span className="text-white text-[9px] font-bold">MB</span>
          </div>
          <span className="text-sm font-semibold text-slate-700">分子工作台</span>
        </div>

        <div className="h-5 w-px bg-slate-200" />

        {/* Mode */}
        {['select', 'bond', 'place'].map(m => (
          <button key={m} onClick={() => setTool(m)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium border transition ${
              tool === m ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}>
            {m === 'select' ? '选择' : m === 'bond' ? '键' : '放置'}
          </button>
        ))}

        <div className="h-5 w-px bg-slate-200" />

        {/* Bond type */}
        {[1, 2, 3].map(t => (
          <button key={t} onClick={() => setBondType(t)}
            className={`px-2 py-1 rounded-md text-xs font-medium border transition ${
              bondType === t ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'
            }`}>
            {t === 1 ? '单键' : t === 2 ? '双键' : '三键'}
          </button>
        ))}

        <div className="h-5 w-px bg-slate-200" />

        <button onClick={optimizeLayout} disabled={isOptimizing}
          className="px-2.5 py-1 rounded-md text-xs font-medium border bg-white text-slate-600 border-slate-200 hover:bg-slate-50 disabled:opacity-50">
          {isOptimizing ? '优化中...' : '优化布局'}
        </button>

        <div className="h-5 w-px bg-slate-200" />

        {/* SMILES */}
        <input className="px-2 py-1 text-xs border border-slate-200 rounded w-40 focus:outline-none focus:border-blue-400"
          placeholder="SMILES" value={smilesInput} onChange={e => setSmilesInput(e.target.value)} />
        <button onClick={importSmiles} className="px-2 py-1 rounded-md text-xs border bg-white text-slate-600 border-slate-200 hover:bg-slate-50">导入</button>
        <button onClick={exportSmiles} className="px-2 py-1 rounded-md text-xs border bg-white text-slate-600 border-slate-200 hover:bg-slate-50">导出</button>

        <div className="h-5 w-px bg-slate-200" />

        {/* Toggles */}
        <button onClick={() => setShowImplicitH(v => !v)}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition ${showImplicitH ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-white text-slate-500 border-slate-200'}`}>
          隐式H
        </button>
        <button onClick={() => setShowCollision(v => !v)}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition ${showCollision ? 'bg-red-50 text-red-600 border-red-200' : 'bg-white text-slate-500 border-slate-200'}`}>
          检测
        </button>
        <button onClick={cycleCharge}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition ${chargeVal !== 0 ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-white text-slate-500 border-slate-200'}`}>
          电荷{chargeVal !== 0 ? `(${chargeVal > 0 ? '+' : ''}${chargeVal})` : ''}
        </button>

        <div className="h-5 w-px bg-slate-200" />

        {/* 5大高级功能按钮 */}
        <button onClick={checkAdmetNow}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition ${showAdmetPanel ? 'bg-green-50 text-green-700 border-green-200' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}
          disabled={admetLoading}>
          {admetLoading ? 'ADMET...' : 'ADMET'}
        </button>
        <button onClick={generate3D}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition ${show3DPanel ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}
          disabled={conformerLoading}>
          {conformerLoading ? '3D...' : '3D'}
        </button>
        <button onClick={() => setShowScaffoldPanel(v => !v)}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition ${showScaffoldPanel ? 'bg-cyan-50 text-cyan-700 border-cyan-200' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}>
          骨架
        </button>
        <button onClick={() => setShowPocketPanel(v => !v)}
          className={`px-2 py-1 rounded-md text-xs font-medium border transition ${showPocketPanel ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}>
          口袋
        </button>

        <div className="flex-1" />

        {/* Zoom */}
        <div className="flex items-center gap-1">
          <button onClick={zoomOut} className="px-2 py-1 rounded text-xs border bg-white border-slate-200 hover:bg-slate-50">-</button>
          <span className="text-xs text-slate-500 w-10 text-center">{(viewport.scale * 100).toFixed(0)}%</span>
          <button onClick={zoomIn} className="px-2 py-1 rounded text-xs border bg-white border-slate-200 hover:bg-slate-50">+</button>
          <button onClick={zoomFit} className="px-2 py-1 rounded text-xs border bg-white border-slate-200 hover:bg-slate-50">Fit</button>
        </div>
      </div>

      {/* ====== Main workspace ====== */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel */}
        <div className="w-44 bg-white border-r border-slate-200 flex flex-col shrink-0">
          <div className="flex border-b border-slate-200">
            <button onClick={() => setLeftTab('atoms')} className={`flex-1 py-2 text-xs font-medium ${leftTab === 'atoms' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-slate-400 hover:text-slate-600'}`}>原子</button>
            <button onClick={() => setLeftTab('templates')} className={`flex-1 py-2 text-xs font-medium ${leftTab === 'templates' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-slate-400 hover:text-slate-600'}`}>模板</button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {leftTab === 'atoms' ? (
              <div className="grid grid-cols-2 gap-1.5">
                {ELEMENTS.map(el => {
                  const isActive = placeEl === el && tool === 'place'
                  const r = Math.max(16, getCovR(el) / 4)
                  const color = getAtomColor(el)
                  const isLight = el === 'H' || el === 'Na' || el === 'K' || el === 'Ca' || el === 'Mg'
                  return (
                    <button key={el} onClick={() => { setPlaceEl(el); setTool('place') }}
                      className={`flex flex-col items-center gap-0.5 p-1.5 rounded-lg border transition ${isActive ? 'bg-blue-50 border-blue-300' : 'bg-white border-slate-100 hover:bg-slate-50'}`}>
                      <div className="rounded-full flex items-center justify-center text-[10px] font-bold border"
                        style={{ width: r, height: r, backgroundColor: color, borderColor: isLight ? '#cbd5e1' : 'rgba(0,0,0,0.1)', color: isLight ? '#0f172a' : '#fff' }}>
                        {el}
                      </div>
                      <span className="text-[10px] text-slate-500">{ELEMENT_NAMES[el] || el}</span>
                      <span className="text-[9px] text-slate-400">v{getValence(el)}</span>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                {TEMPLATES.map(tpl => (
                  <button key={tpl.key} onClick={() => insertTemplate(tpl.key)}
                    className="p-2 rounded-lg border border-slate-100 bg-white hover:bg-slate-50 text-left text-xs">
                    <div className="font-medium text-slate-700">{tpl.name}</div>
                    <div className="text-[10px] text-slate-400">{tpl.desc}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Canvas */}
        <div className="flex-1 relative overflow-hidden bg-slate-50" ref={canvasRef}>
          <svg ref={svgRef} className="w-full h-full"
            onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp} onWheel={handleWheel}
            style={{ cursor: isPanning ? 'grabbing' : tool === 'select' ? 'default' : 'crosshair' }}>
            <defs>
              <pattern id="grid" width={50 * viewport.scale} height={50 * viewport.scale} patternUnits="userSpaceOnUse">
                <path d={`M ${50 * viewport.scale} 0 L 0 0 0 ${50 * viewport.scale}`} fill="none" stroke="#e2e8f0" strokeWidth={1} />
              </pattern>
            </defs>
            <rect x={-10000} y={-10000} width={30000} height={30000} fill="url(#grid)" />

            {/* Bond preview */}
            {bondStartId && tool === 'bond' && (() => {
              const a = atoms.find(at => at.id === bondStartId)
              if (!a) return null
              const s1 = worldToScreen(a.x, a.y)
              const s2 = worldToScreen(mouseWorld.x, mouseWorld.y)
              return <line x1={s1.x} y1={s1.y} x2={s2.x} y2={s2.y} stroke="#94a3b8" strokeWidth={2} strokeDasharray="5,5" />
            })()}

            {/* Box select */}
            {boxSelect && (() => {
              const minX = Math.min(boxSelect.x1, boxSelect.x2)
              const minY = Math.min(boxSelect.y1, boxSelect.y2)
              const w = Math.abs(boxSelect.x2 - boxSelect.x1)
              const h = Math.abs(boxSelect.y2 - boxSelect.y1)
              const s = worldToScreen(minX, minY)
              return <rect x={s.x} y={s.y} width={w * viewport.scale} height={h * viewport.scale} fill="rgba(59,130,246,0.08)" stroke="#3b82f6" strokeWidth={1} strokeDasharray="4,4" />
            })()}

            {/* Bonds */}
            {bonds.map(b => renderBond(b))}

            {/* Atoms (sorted by z for depth) */}
            {sortedAtoms.map(a => renderAtom(a))}
          </svg>

          {/* Tooltip */}
          {tooltip && (() => {
            const rect = canvasRef.current?.getBoundingClientRect()
            const s = worldToScreen(mouseWorld.x, mouseWorld.y)
            return (
              <div className="absolute pointer-events-none bg-slate-800 text-white text-[10px] px-2 py-1 rounded shadow-lg z-10"
                style={{ left: s.x + 12, top: s.y - 24 }}>{tooltip}</div>
            )
          })()}

          {/* Empty state */}
          {atoms.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center text-slate-300">
                <div className="text-4xl font-light mb-3 opacity-40">C6H6</div>
                <div className="text-sm font-medium text-slate-400">从左侧选择原子或模板开始构建</div>
                <div className="text-xs text-slate-300 mt-1">S=选择 B=键 P=放置 1/2/3=键类型</div>
              </div>
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="w-52 bg-white border-l border-slate-200 flex flex-col shrink-0 overflow-y-auto">
          <div className="p-3 border-b border-slate-100">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">属性</div>
          </div>

          <div className="p-3 space-y-3">
            {selectedAtom ? (
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold border"
                    style={{ backgroundColor: getAtomColor(selectedAtom.element), borderColor: '#e2e8f0', color: '#fff' }}>
                    {selectedAtom.element}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-700">{ELEMENT_NAMES[selectedAtom.element] || selectedAtom.element}</div>
                    <div className="text-[10px] text-slate-400">ID: {selectedAtom.id}</div>
                  </div>
                </div>
                {[
                  ['坐标', `(${selectedAtom.x.toFixed(1)}, ${selectedAtom.y.toFixed(1)})`],
                  ['范德华半径', `${getVdwR(selectedAtom.element)} pm`],
                  ['共价半径', `${getCovR(selectedAtom.element)} pm`],
                  ['化合价', String(getValence(selectedAtom.element))],
                  ['电荷', selectedAtom.charge > 0 ? `+${selectedAtom.charge}` : String(selectedAtom.charge)],
                  ['隐式H', String(implicitH[selectedAtom.id] || 0)],
                  ['深度Z', String(selectedAtom.z)],
                  ['当前键数', (() => { let u = 0; for (const b of bonds) if (b.from === selectedAtom.id || b.to === selectedAtom.id) u += b.type; return u; })() + ' / ' + getValence(selectedAtom.element)],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between py-0.5 border-b border-slate-50">
                    <span className="text-slate-500">{k}</span>
                    <span className="font-mono text-slate-700">{v}</span>
                  </div>
                ))}
                <button onClick={() => delAtom(selectedAtom.id)}
                  className="w-full py-1.5 rounded-md text-xs font-medium bg-red-50 text-red-600 hover:bg-red-100 transition mt-2">
                  删除原子
                </button>
              </div>
            ) : selIds.size > 1 ? (
              <div className="text-xs text-slate-500">
                <div className="text-sm font-medium text-slate-700 mb-2">多选 ({selIds.size} 原子)</div>
                <div>Shift+点击添加/移除</div>
                <div>拖拽移动整组</div>
                <div>Ctrl+C 复制, Ctrl+V 粘贴</div>
              </div>
            ) : bondStartId ? (
              <div className="text-xs text-amber-600">
                <div className="text-sm font-medium mb-1">创建键中...</div>
                <div>拖拽到目标原子后释放</div>
              </div>
            ) : (
              <div className="text-xs text-slate-400 text-center py-6">
                <div className="text-sm mb-1">选择原子查看属性</div>
                <div>点击键查看长度</div>
              </div>
            )}
          </div>

          {selectedAtom && bondAngles.length > 0 && (
            <div className="px-3 pb-3">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">键角</div>
              <div className="space-y-1 text-xs">
                {bondAngles.map((ang, i) => (
                  <div key={i} className="flex justify-between">
                    <span className="text-slate-500">{ang.pair}</span>
                    <span className="font-mono text-slate-700">{ang.val}°</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedBonds.length > 0 && (
            <div className="px-3 pb-3">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">键信息</div>
              <div className="space-y-1 text-xs">
                {selectedBonds.slice(0, 3).map(b => {
                  const a1 = atoms.find(a => a.id === b.from), a2 = atoms.find(a => a.id === b.to)
                  const d = dist(a1, a2), ideal = getStdBondLen(a1.element, a2.element, b.type)
                  const t = b.type === 2 ? '双' : b.type === 3 ? '三' : '单'
                  return (
                    <div key={b.id} className="flex justify-between">
                      <span className="text-slate-500">{a1.element}-{a2.element} {t}</span>
                      <span className="font-mono">{d.toFixed(1)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {atoms.length > 0 && (
            <div className="mt-auto p-3 border-t border-slate-100">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">分子式</div>
              <div className="text-lg font-bold text-slate-800">{formulaData.formula}</div>
              <div className="text-xs text-slate-500 mt-1">MW: {formulaData.mw} g/mol</div>
              <div className="text-[10px] text-slate-400 mt-1">
                {atoms.length} 原子 / {bonds.length} 键
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ====== ADMET 面板弹窗 ====== */}
      {showAdmetPanel && admetData && admetData.success && (
        <div className="absolute top-12 right-56 w-72 bg-white border border-slate-200 rounded-lg shadow-xl z-20 p-4 max-h-[80vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-bold text-slate-800">ADMET 规则检查</div>
            <button onClick={() => setShowAdmetPanel(false)} className="text-slate-400 hover:text-slate-600 text-xs">关闭</button>
          </div>
          <div className="space-y-2 text-xs">
            <div className={`flex items-center gap-2 p-2 rounded ${admetData.lipinski.pass ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className={`w-3 h-3 rounded-full ${admetData.lipinski.pass ? 'bg-green-500' : 'bg-red-500'}`} />
              <div className="flex-1">
                <div className="font-medium">Lipinski 五规则</div>
                <div className="text-[10px] text-slate-500">{admetData.lipinski.pass ? '全部通过' : admetData.lipinski.violations.join('；')}</div>
              </div>
            </div>
            <div className={`flex items-center gap-2 p-2 rounded ${admetData.veber.pass ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className={`w-3 h-3 rounded-full ${admetData.veber.pass ? 'bg-green-500' : 'bg-red-500'}`} />
              <div className="flex-1">
                <div className="font-medium">Veber 规则</div>
                <div className="text-[10px] text-slate-500">{admetData.veber.pass ? '全部通过' : admetData.veber.violations.join('；')}</div>
              </div>
            </div>
            <div className={`flex items-center gap-2 p-2 rounded ${admetData.pains.count === 0 ? 'bg-green-50' : 'bg-amber-50'}`}>
              <div className={`w-3 h-3 rounded-full ${admetData.pains.count === 0 ? 'bg-green-500' : 'bg-amber-500'}`} />
              <div className="flex-1">
                <div className="font-medium">PAINS 检查</div>
                <div className="text-[10px] text-slate-500">{admetData.pains.count === 0 ? '无干扰结构' : admetData.pains.warnings.join('；')}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 p-2 bg-slate-50 rounded">
              <div className="text-[10px] text-slate-500">MW <span className="font-mono text-slate-800">{admetData.mw}</span></div>
              <div className="text-[10px] text-slate-500">logP <span className="font-mono text-slate-800">{admetData.logp}</span></div>
              <div className="text-[10px] text-slate-500">TPSA <span className="font-mono text-slate-800">{admetData.tpsa} Å²</span></div>
              <div className="text-[10px] text-slate-500">旋转键 <span className="font-mono text-slate-800">{admetData.rotatable_bonds}</span></div>
              <div className="text-[10px] text-slate-500">HBD <span className="font-mono text-slate-800">{admetData.hbd}</span></div>
              <div className="text-[10px] text-slate-500">HBA <span className="font-mono text-slate-800">{admetData.hba}</span></div>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${admetData.druglikeness_score}%` }} />
              </div>
              <span className="text-xs font-medium text-slate-700">{admetData.druglikeness_score}分</span>
            </div>
          </div>
        </div>
      )}

      {/* ====== 3D 构象查看弹窗 ====== */}
      {show3DPanel && (
        <div className="absolute inset-0 bg-slate-900/60 z-30 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-2xl w-[600px] h-[500px] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
              <div className="text-sm font-bold text-slate-800">3D 构象</div>
              <button onClick={() => setShow3DPanel(false)} className="text-slate-400 hover:text-slate-600 text-sm">关闭</button>
            </div>
            <div className="flex-1 p-4 flex flex-col items-center justify-center relative">
              {conformerLoading ? (
                <div className="text-slate-400 text-sm">正在生成 3D 构象...</div>
              ) : conformerData && conformerData.success ? (
                <div className="w-full h-full flex flex-col">
                  <div className="flex-1 relative bg-slate-50 rounded-lg overflow-hidden">
                    <Builder3DView coords={conformerData.coords} />
                  </div>
                  <div className="mt-2 text-xs text-slate-500 flex gap-4">
                    <span>能量: {conformerData.energy} kcal/mol</span>
                    <span>原子数: {conformerData.num_atoms}</span>
                  </div>
                </div>
              ) : conformerData && conformerData.error ? (
                <div className="text-red-500 text-sm">错误: {conformerData.error}</div>
              ) : (
                <div className="text-slate-400 text-sm">点击"3D"按钮生成构象</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ====== 骨架跃迁面板 ====== */}
      {showScaffoldPanel && (
        <div className="absolute top-12 left-48 w-56 bg-white border border-slate-200 rounded-lg shadow-xl z-20 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-bold text-slate-800">骨架跃迁</div>
            <button onClick={() => setShowScaffoldPanel(false)} className="text-slate-400 hover:text-slate-600 text-xs">关闭</button>
          </div>
          <div className="text-[10px] text-slate-500 mb-2">选中一个环后选择目标骨架</div>
          <div className="flex flex-col gap-1">
            {TEMPLATES.map(tpl => (
              <button key={tpl.key} onClick={() => doScaffoldHop(tpl.key)}
                className="p-2 rounded-lg border border-slate-100 bg-white hover:bg-slate-50 text-left text-xs disabled:opacity-40"
                disabled={selIds.size < 3}>
                <div className="font-medium text-slate-700">{tpl.name}</div>
                <div className="text-[10px] text-slate-400">{tpl.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ====== 口袋查看面板 ====== */}
      {showPocketPanel && (
        <div className="absolute top-12 left-48 w-72 bg-white border border-slate-200 rounded-lg shadow-xl z-20 p-4 max-h-[80vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-bold text-slate-800">蛋白质口袋</div>
            <button onClick={() => setShowPocketPanel(false)} className="text-slate-400 hover:text-slate-600 text-xs">关闭</button>
          </div>
          <div className="mb-2 text-[10px] text-slate-500">粘贴 PDB 内容</div>
          <textarea className="w-full h-32 text-[10px] border border-slate-200 rounded p-2 font-mono resize-none focus:outline-none focus:border-blue-400"
            placeholder="ATOM   1  N   SER A   1      11.104  13.889  13.410..."
            value={pdbInput} onChange={e => setPdbInput(e.target.value)} />
          <button onClick={loadPocket}
            className="w-full mt-2 py-1.5 rounded-md text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 transition">
            加载口袋
          </button>
          {pocketData && pocketData.success && (
            <div className="mt-3 space-y-1 text-xs">
              <div className="text-green-600 font-medium">加载成功</div>
              <div className="text-slate-500">原子数: {pocketData.num_atoms}</div>
              <div className="text-slate-500">表面原子: {pocketData.num_surface}</div>
              <div className="text-slate-500">中心: ({pocketData.center.x}, {pocketData.center.y}, {pocketData.center.z})</div>
            </div>
          )}
          {pocketData && pocketData.error && (
            <div className="mt-2 text-red-500 text-xs">{pocketData.error}</div>
          )}
        </div>
      )}

      {/* Status bar */}
      <div className="bg-white border-t border-slate-200 px-3 py-1 flex items-center gap-4 text-[10px] text-slate-500 shrink-0">
        <span>模式: {tool === 'select' ? '选择' : tool === 'bond' ? '键' : '放置'}</span>
        <span>键: {bondType === 1 ? '单' : bondType === 2 ? '双' : '三'}</span>
        <span>放置: {placeEl}</span>
        <span>缩放: {(viewport.scale * 100).toFixed(0)}%</span>
        <span>原子: {atoms.length}</span>
        <span>键: {bonds.length}</span>
        <span>选中: {selIds.size}</span>
        <span className="flex-1" />
        <span>S=选择 B=键 P=放置 1/2/3=键 Del=删除 Ctrl+C/V=复制粘贴</span>
      </div>
    </div>
  )
}
/* 3D 构象查看器 — 简单正交投影 */
function Builder3DView({ coords }) {
  const [rotX, setRotX] = useState(-20)
  const [rotY, setRotY] = useState(30)
  const [isRotating, setIsRotating] = useState(false)
  const [lastPos, setLastPos] = useState({ x: 0, y: 0 })
  const containerRef = useRef(null)

  if (!coords || coords.length === 0) return null

  // 计算中心
  const cx = coords.reduce((s, c) => s + c.x, 0) / coords.length
  const cy = coords.reduce((s, c) => s + c.y, 0) / coords.length
  const cz = coords.reduce((s, c) => s + c.z, 0) / coords.length

  // 3D 旋转 + 正交投影
  const project = (x, y, z) => {
    const rx = (x - cx) * Math.cos(rotY * Math.PI / 180) - (z - cz) * Math.sin(rotY * Math.PI / 180)
    const rz = (x - cx) * Math.sin(rotY * Math.PI / 180) + (z - cz) * Math.cos(rotY * Math.PI / 180)
    const ry = (y - cy) * Math.cos(rotX * Math.PI / 180) - rz * Math.sin(rotX * Math.PI / 180)
    const rz2 = (y - cy) * Math.sin(rotX * Math.PI / 180) + rz * Math.cos(rotX * Math.PI / 180)
    return { x: rx + 250, y: ry + 200, z: rz2 }
  }

  const projected = coords.map((c, i) => {
    const p = project(c.x, c.y, c.z)
    const r = c.element === 'H' ? 3 : Math.max(5, (getCovR(c.element) || 80) / 15)
    return { ...p, r, element: c.element, idx: i }
  }).sort((a, b) => a.z - b.z)

  const handleMouseDown = (e) => {
    setIsRotating(true)
    setLastPos({ x: e.clientX, y: e.clientY })
  }

  const handleMouseMove = (e) => {
    if (!isRotating) return
    const dx = e.clientX - lastPos.x
    const dy = e.clientY - lastPos.y
    setRotY(prev => prev + dx * 0.5)
    setRotX(prev => prev - dy * 0.5)
    setLastPos({ x: e.clientX, y: e.clientY })
  }

  const handleMouseUp = () => setIsRotating(false)

  return (
    <div className="w-full h-full relative" ref={containerRef}
      onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
      <svg className="w-full h-full" viewBox="0 0 500 400">
        {projected.map(a => (
          <g key={a.idx}>
            <circle cx={a.x} cy={a.y} r={a.r}
              fill={getAtomColor(a.element)} stroke="rgba(0,0,0,0.2)" strokeWidth={0.5}
              opacity={0.6 + 0.4 / (1 + Math.abs(a.z) * 0.01)} />
            <text x={a.x} y={a.y + 1} textAnchor="middle" dominantBaseline="central"
              fontSize={a.r * 0.8} fontWeight="700" fill={a.element === 'H' ? '#334155' : '#fff'} pointerEvents="none">{a.element}</text>
          </g>
        ))}
      </svg>
      <div className="absolute bottom-2 left-2 text-[10px] text-slate-400">拖拽旋转</div>
    </div>
  )
}
