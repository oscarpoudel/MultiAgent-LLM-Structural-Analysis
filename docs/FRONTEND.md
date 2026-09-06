# Frontend Documentation

## File Structure

```
app/static/
├── index.html           # Single-page application shell
├── styles.css           # Complete design system (theming, layout, components)
└── js/
    ├── chat.js          # Chat message handling, LLM status polling, quick-prompt buttons, Clear chat
    ├── analysis.js      # Model payload builder, template generators, analysis results handler, JSON export/import
    ├── main.js          # Application controller, autosave, initialization, event wiring
    ├── projects.js      # Server-backed project CRUD with IndexedDB migration
    ├── sections.js      # Sections tab: section search + design subtabs (select, concrete, timber, foundation, fatigue, cost)
    ├── loads.js         # Loads tab: wind/seismic/snow/spectrum/P-delta/sensitivity/multi-hazard forms + results
    ├── history.js       # Analysis history viewer
    ├── tabs.js          # Tab manager for panel switching
    ├── shortcuts.js     # Keyboard shortcuts
    ├── state.js         # Central state store (S object)
    ├── theme.js         # Dark/light theme management
    ├── results.js       # Results rendering and display
    ├── modals.js        # Modal dialog management
    ├── dom.js           # DOM helper utilities
    ├── api.js           # HTTP fetch wrapper for all API calls
    └── canvas3d/
        ├── index.js     # Canvas3D namespace and coordination
        ├── scene.js     # Three.js scene, camera, lights, grid
        ├── render.js    # WebGL renderer and animation loop
        ├── interaction.js  # Orbit controls, click/hover, grid snapping
        └── ui.js        # Canvas UI controls (toolbar, panels)
```

## app/static/index.html - Application Shell

Single-page application entry point. Loads all CSS and JavaScript modules:

- **Libraries**: Three.js (r128), Plotly.js (2.35.0), KaTeX (0.16.9), marked (9.1.6), Font Awesome (6.5.1)
- **Styles**: `styles.css` (single combined stylesheet)
- **Scripts**: All JS modules loaded in dependency order at bottom of `<body>`

### Layout Structure

- **Header** (`#app-header`): Logo, title, LLM status indicator (green/yellow/red dot), theme toggle, help/about buttons, 3D view toggle, "Developed by Oscar" credit link
- **Main content** (`#main-content`): Two-panel layout
  - **Left panel** (`#left-panel`): Chat interface with message history, quick-prompt buttons (3D Frame, Beam, Column, 2D Frame), Clear chat button, input textarea, and send button
  - **Right panel** (`#right-panel`): 3D canvas, 2D canvas, results panel, and tabs for switching views
- **Modals**: Help modal, about modal, results modal, section search modal, history modal, export modal
- **Toast notifications**: `#toast-container` for success/error/info messages

### LLM Status Indicator

- Green dot: LLM provider reachable
- Yellow dot: Checking / loading
- Red dot: LLM provider offline
- Polls `GET /api/llm-status` every 30 seconds

### Quick-Prompt Buttons

Replaced the example `<select>` dropdown with labeled buttons:
- **3D Frame** - `drawThreeByThreeThreeStoryFrame()`
- **Beam** - "Analyze a simply supported beam..."
- **Column** - "Analyze a steel column..."
- **2D Frame** - "Analyze a 2D portal frame..."
- **Clear** - Empties chat history and clears analysis results

## app/static/styles.css - Main Stylesheet

Complete design system with CSS custom properties for theming. Single file (no separate css/ directory). Includes dark and light theme via `.dark-theme` / `.light-theme` classes on `<html>`.

### Color Variables

- **Primary palette**: `--primary-50` through `--primary-900` (blue tones)
- **Secondary palette**: `--secondary-50` through `--secondary-900` (indigo tones)
- **Status colors**: `--success-*`, `--warning-*`, `--danger-*`, `--info-*`
- **Neutral colors**: `--neutral-50` through `--neutral-950`

### Layout

- **Header**: Fixed 64px height, flexbox layout with responsive breakpoints
- **Main content**: Flexbox two-panel layout, 50/50 split by default, resizable via CSS grid
- **Chat panel**: Scrollable message list, fixed input bar at bottom
- **Results panel**: Tabbed interface for 3D view, 2D canvas, and results data
- **Responsive**: Breakpoints at 1280px, 1024px, 768px, 480px

### Components

- **Message bubbles**: AI messages (left-aligned, gradient border), user messages (right-aligned, primary color)
- **Buttons**: Primary, secondary, ghost, quick-prompt variants
- **Input fields**: Styled textareas with placeholder text (no default value)
- **Tabs**: Horizontal tab bar with active indicator
- **Cards**: Elevated cards with shadows and rounded corners
- **Loading states**: Spinners, skeleton loaders
- **Toast notifications**: Slide-in notifications with auto-dismiss
- **LLM dot**: `.llm-dot` - Small colored circle for LLM status
- **Quick-prompt buttons**: `.qp-btn` - Labeled action buttons in chat input area
- **Clear chat**: `.clear-chat-btn` - Removes all messages and results
- **Credit**: `.credit` - "Developed by Oscar" footer link

## app/static/js/state.js - Application State Management

Central state store (`S` object, not `AppState`):

```javascript
const S = {
  // Analysis state
  currentAnalysis: null,
  analysisHistory: [],
  selectedResults: null,

  // Canvas state
  canvas3D: { nodes: [], members: [], loads: [], supports: [] },
  model: null,

  // UI state
  activeTab: 'results',
  theme: 'dark',
  selectedNode: null,
  selectedMember: null,

  // Chat state
  conversationHistory: [],
  isTyping: false,

  // Project state
  currentProject: null,
  projects: [],
  autosaveTimer: null,

  // LLM status
  llmAvailable: false,
  llmChecking: true,

  // Modal state
  activeModal: null,
  modalData: null
};
```

## app/static/js/chat.js - Chat Module

Handles all chat-related functionality:

- `sendChatMessage()` - POST to `/api/chat`, handle response
- `displayUserMessage()` - Add user message to chat
- `displayAIMessage()` - Parse and display AI response with formatting
- `handleCanvasAction()` - Execute canvas tool action from AI
- `updateLLMStatus()` - Poll `GET /api/llm-status` and update indicator
- `setupQuickPromptButtons()` - Wire 3D Frame, Beam, Column, 2D Frame buttons
- `clearChat()` - Remove all messages and analysis results

## app/static/js/analysis.js - Analysis Module

Handles model building and analysis:

- `getModelPayload()` - Build structure model from canvas state
- `clearAnalysisResults()` - Remove result overlays from canvas
- `drawThreeByThreeThreeStoryFrame()` - Generate 3D frame template data
- `applyMemberGroupSections()` - Apply section properties to member groups
- `runAnalysis()` - POST to `/api/analyze` with model data

## app/static/js/main.js - Main Controller

Central controller that wires all components:

- `init()` - Boot sequence: load projects, init canvases, setup events
- `setupEventListeners()` - Register all DOM event handlers
- `autosave()` - Save project every 2s (debounced) + on beforeunload
- `saveProjectSnapshot()` - Capture current model/results state

## app/static/js/projects.js - Projects Module

Server-backed project persistence with IndexedDB migration:

- `loadProjects()` - Fetch projects from `GET /api/projects`
- `createProject(name)` - Create new project via `POST /api/projects`
- `saveProject(id, data)` - Update project via `PUT /api/projects/<id>`
- `deleteProject(id)` - Delete project via `DELETE /api/projects/<id>`
- `migrateFromIndexedDB()` - On first load, copy old IndexedDB projects to server
- `autosave()` - Debounced save on model/results changes

## app/static/js/api.js - API Module

HTTP fetch wrapper for all backend API calls. Provides consistent error handling and JSON parsing.

## app/static/js/dom.js - DOM Utilities

Helper functions for DOM manipulation: element creation, class toggling, event delegation.

## app/static/js/sections.js - Sections Tab

UI for the Sections tab, which hosts the section library plus the deterministic design subtabs:
- **Section Library**: search input with live filtering, results table, click to select a section for member assignment
- **Section Selection**: steel beam/column selection forms (AISC 360, incl. LTB)
- **Concrete Design**: ACI 318 beam/column forms
- **Timber Design**: NDS beam form + species lookup
- **Foundation**: spread footing + pile forms
- **Fatigue**: AISC 360 S-N check form + category lookup
- **Cost Estimate**: steel takeoff form

## app/static/js/loads.js - Loads Tab

UI for the Loads tab, which hosts the deterministic load-determination and second-order/advanced subtabs:
- **Wind / Seismic / Snow**: ASCE 7-22 forms with results panels, story-force tables, and apply-to-3D-model + analyze
- **Response Spectrum**: multi-mode SRSS analysis on the drawn 3D model
- **P-Delta**: stability-coefficient drift amplification + equivalent lateral forces
- **Sensitivity**: OAT parametric study with ranked parameters
- **Multi-Hazard**: load-combination optimizer against a member capacity

Subtab switching uses `data-loadtab` buttons + `data-loadform` containers (`switchLoadTab`). Each run function posts to the matching `/api/loads/*` or `/api/analyze/*` endpoint and renders results into the panel.

## app/static/js/history.js - History Viewer

UI for browsing analysis history:
- Paginated list of past analyses
- Click to view full results
- Delete individual records

## app/static/js/tabs.js - Tab Manager

Manages the right-panel tab switching between 3D canvas, 2D canvas, and results view.

## app/static/js/shortcuts.js - Keyboard Shortcuts

Keyboard bindings for common actions:
- `Ctrl+Enter` - Send chat message
- `Escape` - Close modals
- Other navigation shortcuts

## app/static/js/theme.js - Theme Management

Handles theme switching between dark and light modes:
- `initTheme()` - Load saved theme from localStorage
- `toggleTheme()` - Switch between dark/light themes
- `applyTheme(theme)` - Update CSS classes and persist

## app/static/js/results.js - Results Rendering

Formats and displays analysis results:
- `renderResultsPanel(results)` - Populate results tab
- `formatValue(value, unit)` - Format numbers with units
- `renderWarnings(warnings)` - Display warning badges
- `renderAssumptions(assumptions)` - List analysis assumptions
- `renderAgentTraces(traces)` - Show agent pipeline trace

## app/static/js/modals.js - Modal Management

Manages all modal dialogs: Help, About, Results, Section Search, History, Export.

## app/static/js/canvas3d/ - 3D Canvas Module

Modular Three.js-based 3D canvas system:

- **index.js**: Namespace and coordination, exports `Canvas3D` global
- **scene.js**: Scene setup, camera (perspective), lights (ambient + directional), grid, axes
- **render.js**: WebGL renderer, animation loop, resize handling
- **interaction.js**: OrbitControls, raycasting for click selection, hover tooltips, grid snapping
- **ui.js**: Canvas toolbar buttons, panel controls, view toggles

### 3D Scene Features

- Perspective camera with orbit controls (rotate, pan, zoom)
- Grid helper and axis helper
- Ambient + directional lighting with shadows
- Antialiased WebGL renderer
- Node spheres with color coding, member cylinders, load arrows, support indicators
- Deflected shape overlay with color-coded displacement
- Click selection for nodes/members with info display
- Export scene as PNG

## Autosave

The application automatically saves project state:

- **Trigger**: Model change, analysis results change, beforeunload
- **Interval**: 2-second debounce on continuous edits
- **Target**: Server via `PUT /api/projects/<id>`
- **Fallback**: First-time IndexedDB migration on initial load

## LLM Status Polling

- Polls `GET /api/llm-status` every 30 seconds
- Green dot = reachable, yellow = checking, red = unreachable
- Status shown in chat header
- Quick-prompt buttons disabled when LLM offline
