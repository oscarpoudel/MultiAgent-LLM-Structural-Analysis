import { byId } from '../dom.js';

export let needsRedraw = true;

export const canvas3d = {
  canvas: null,
  renderer: null,
  scene: null,
  camera: null,
  orthoCamera: null,
  controls: null,
  nodesGroup: null,
  membersGroup: null,
  loadsGroup: null,
  supportsGroup: null,
  gridGroup: null,
  levelLinesGroup: null,
  labelsGroup: null,
  groundPlane: null,
  hoverMesh: null,
  axesRenderer: null,
  axesScene: null,
  axesCamera: null,
  axesLabels: null,
  viewMode: '3d',
  elevType: 'xAxis',
  selectedElevGrid: 0,
  gridLinesX: [],
  gridLinesY: [],
  levels: [],
  currentPlanZ: 0,
  loadScale: 3.0,
  nodeSize: 0.2,
  memberSize: 0.12,
  gridColor: null,
};

export function initScene() {
  canvas3d.canvas = byId('canvas');

  canvas3d.renderer = new THREE.WebGLRenderer({ canvas: canvas3d.canvas, antialias: true });
  canvas3d.renderer.setPixelRatio(window.devicePixelRatio);
  canvas3d.renderer.shadowMap.enabled = true;
  canvas3d.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  canvas3d.scene = new THREE.Scene();
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  canvas3d.scene.background = new THREE.Color(isDark ? '#0f1419' : '#f8fafb');

  canvas3d.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
  canvas3d.camera.up.set(0, 0, 1);

  canvas3d.orthoCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  canvas3d.orthoCamera.up.set(0, 0, 1);

  canvas3d.controls = new THREE.OrbitControls(canvas3d.camera, canvas3d.renderer.domElement);
  canvas3d.controls.enableDamping = true;
  canvas3d.controls.dampingFactor = 0.05;

  const ambient = new THREE.AmbientLight(0xffffff, 0.6);
  canvas3d.scene.add(ambient);
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(20, 20, 30);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width = 2048;
  dirLight.shadow.mapSize.height = 2048;
  canvas3d.scene.add(dirLight);

  canvas3d.nodesGroup = new THREE.Group();
  canvas3d.membersGroup = new THREE.Group();
  canvas3d.slabsGroup = new THREE.Group();
  canvas3d.loadsGroup = new THREE.Group();
  canvas3d.supportsGroup = new THREE.Group();
  canvas3d.gridGroup = new THREE.Group();
  canvas3d.levelLinesGroup = new THREE.Group();
  canvas3d.labelsGroup = new THREE.Group();
  canvas3d.scene.add(canvas3d.nodesGroup);
  canvas3d.scene.add(canvas3d.membersGroup);
  canvas3d.scene.add(canvas3d.slabsGroup);
  canvas3d.scene.add(canvas3d.loadsGroup);
  canvas3d.scene.add(canvas3d.supportsGroup);
  canvas3d.scene.add(canvas3d.gridGroup);
  canvas3d.scene.add(canvas3d.levelLinesGroup);
  canvas3d.scene.add(canvas3d.labelsGroup);

  const planeGeo = new THREE.PlaneGeometry(1, 1);
  const planeMat = new THREE.MeshBasicMaterial({ visible: false, side: THREE.DoubleSide });
  canvas3d.groundPlane = new THREE.Mesh(planeGeo, planeMat);
  canvas3d.scene.add(canvas3d.groundPlane);

  const hoverGeo = new THREE.SphereGeometry(0.25, 16, 16);
  const hoverMat = new THREE.MeshBasicMaterial({ color: 0x22c55e, transparent: true, opacity: 0.5 });
  canvas3d.hoverMesh = new THREE.Mesh(hoverGeo, hoverMat);
  canvas3d.hoverMesh.visible = false;
  canvas3d.scene.add(canvas3d.hoverMesh);

  let axesContainer = byId('axesViewport');
  if (!axesContainer) {
    axesContainer = document.createElement('div');
    axesContainer.id = 'axesViewport';
    axesContainer.style.cssText = 'position:absolute;bottom:24px;right:24px;width:100px;height:100px;pointer-events:none;z-index:100;';
    canvas3d.canvas.parentElement.appendChild(axesContainer);
  }

  canvas3d.axesRenderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  canvas3d.axesRenderer.setSize(100, 100);
  axesContainer.innerHTML = '';
  axesContainer.appendChild(canvas3d.axesRenderer.domElement);

  canvas3d.axesScene = new THREE.Scene();
  canvas3d.axesCamera = new THREE.OrthographicCamera(-1.5, 1.5, 1.5, -1.5, 0.1, 100);
  canvas3d.axesCamera.position.set(0, 0, 10);
  canvas3d.axesCamera.up.set(0, 0, 1);
  canvas3d.axesScene.add(new THREE.AxesHelper(1.2));
  addAxesLabels();
}

function createAxisLabel(text, color) {
  const labelCanvas = document.createElement('canvas');
  labelCanvas.width = 96;
  labelCanvas.height = 96;
  const ctx = labelCanvas.getContext('2d');
  ctx.font = 'bold 54px Inter, Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = 8;
  ctx.strokeStyle = 'rgba(255,255,255,0.9)';
  ctx.fillStyle = color;
  ctx.strokeText(text, 48, 50);
  ctx.fillText(text, 48, 50);

  const texture = new THREE.CanvasTexture(labelCanvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.35, 0.35, 0.35);
  return sprite;
}

function addAxesLabels() {
  const labels = new THREE.Group();
  const x = createAxisLabel('X', '#ef4444');
  const y = createAxisLabel('Y', '#22c55e');
  const z = createAxisLabel('Z', '#3b82f6');
  x.position.set(1.45, 0, 0);
  y.position.set(0, 1.45, 0);
  z.position.set(0, 0, 1.45);
  labels.add(x, y, z);
  canvas3d.axesLabels = labels;
  canvas3d.axesScene.add(labels);
}

export function startRenderLoop(drawFn) {
  canvas3d.renderer.setAnimationLoop(() => {
    canvas3d.controls.update();

    // Ensure renderer has valid dimensions
    const wrap = canvas3d.canvas.parentElement;
    if (wrap && wrap.clientWidth > 0 && wrap.clientHeight > 0) {
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      const rw = canvas3d.renderer.domElement.width;
      if (rw < 1 || rw !== w) {
        canvas3d.renderer.setSize(w, h);
        canvas3d.camera.aspect = w / h;
        canvas3d.camera.updateProjectionMatrix();
      }
      // Only rebuild geometry when something changed
      if (needsRedraw) {
        drawFn();
        needsRedraw = false;
      }
    }

    // Use perspective camera for all views (elevation, plan, 3D)
    canvas3d.renderer.render(canvas3d.scene, canvas3d.camera);

    // Axes widget always uses perspective camera for direction reference
    canvas3d.axesCamera.position.copy(canvas3d.camera.position).sub(canvas3d.controls.target).normalize().multiplyScalar(10);
    canvas3d.axesCamera.lookAt(0, 0, 0);
    canvas3d.axesRenderer.render(canvas3d.axesScene, canvas3d.axesCamera);
  });
}

export function triggerRedraw() {
  needsRedraw = true;
}
