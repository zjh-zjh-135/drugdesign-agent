import React, { createContext, useContext, useReducer } from 'react'

const initialState = {
  currentProject: null,
  pipelineStatus: null,
  filterParams: {
    mw_min: 250, mw_max: 550,
    clogp_min: 0, clogp_max: 5,
    tpsa_min: 40, tpsa_max: 120,
    hbd_max: 5, hba_max: 10,
    rotb_max: 10, sa_score_max: 4.5,
  },
  notifications: [],
  pipelineJobId: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_PROJECT':
      return { ...state, currentProject: action.payload }
    case 'SET_PIPELINE_STATUS':
      return { ...state, pipelineStatus: action.payload }
    case 'SET_PIPELINE_JOB_ID':
      return { ...state, pipelineJobId: action.payload }
    case 'SET_FILTER_PARAMS':
      return { ...state, filterParams: { ...state.filterParams, ...action.payload } }
    case 'ADD_NOTIFICATION':
      return { ...state, notifications: [...state.notifications, action.payload] }
    case 'CLEAR_NOTIFICATIONS':
      return { ...state, notifications: [] }
    // NEW: 支持前端动作直接修改状态
    case 'APPLY_AGENT_ACTION':
      // action.payload: { key: 'filterParams' | 'currentProject' | 'pipelineStatus' | 'pipelineJobId', value: ... }
      if (!action.payload || !action.payload.key) return state
      const key = action.payload.key
      if (key in state) {
        return { ...state, [key]: action.payload.value }
      }
      return state
    default:
      return state
  }
}

const AppContext = createContext()

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  return useContext(AppContext)
}
