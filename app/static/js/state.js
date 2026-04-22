export const S = {
  nodes: [],
  members: [],
  loads: [],
  memberLoads: [],
  nextNodeId: 1,
  nextMemberId: 1,
  tool: 'select',
  selected: null,
  memberStart: null,
  results: null,
  pan: { x: 0, y: 0 },
  zoom: 40,
  dragging: false,
  dragStart: null,
  dragNode: null,
  gridSnap: 0.5,
  _lastExport: null,
};

export const GRID = 0.5;
export const NODE_R = 7;
export const SNAP_R = 15;

export function resetModel() {
  S.nodes = [];
  S.members = [];
  S.loads = [];
  S.memberLoads = [];
  S.nextNodeId = 1;
  S.nextMemberId = 1;
  S.selected = null;
  S.results = null;
  S.memberStart = null;
  S._lastExport = null;
}
