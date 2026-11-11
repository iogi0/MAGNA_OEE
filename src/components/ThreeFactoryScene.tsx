import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { 
  Crosshair, 
  RotateCw, 
  ArrowLeft, 
  AlertTriangle, 
  CheckCircle2, 
  Sparkles,
  Layers,
  Camera,
  Activity,
  Maximize2
} from 'lucide-react';

export interface HotspotPin {
  id: string;
  stationId: number;
  stepIdx?: number;
  label: string;
  sublabel: string;
  x: number;
  y: number;
  z: number;
  type: 'station' | 'component' | 'alarm';
  color: string;
  badgeCode?: string;
}

interface Props {
  selectedStationId: number | null;
  activeStepIdx: number | null;
  onSelectStation: (stationId: number | null) => void;
  onSelectStep: (stepIdx: number) => void;
  isAlarm: boolean;
  onResolveStation?: () => void;
}

// 10 Stations coordinates along X
const STATION_X: Record<number, number> = {
  1: -14.4,
  2: -11.2,
  3: -8.0, // Camera Inspection (ALARM - Red Neon)
  4: -4.8,
  5: -1.6,
  6: 1.6,
  7: 4.8,
  8: 8.0,
  9: 11.2,
  10: 14.4,
};

export const ThreeFactoryScene: React.FC<Props> = ({
  selectedStationId,
  activeStepIdx,
  onSelectStation,
  onSelectStep,
  isAlarm,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);

  // Screen coordinates of projected 3D hotspots
  const [projectedPins, setProjectedPins] = useState<Array<{
    pin: HotspotPin;
    screenX: number;
    screenY: number;
    visible: boolean;
  }>>([]);

  const isOverview = selectedStationId === null;

  // Balanced Isometric Camera View (Even horizontal distribution matching Image 2)
  const targetCamPos = useRef(new THREE.Vector3(1.5, 11.5, 23.5));
  const targetLookAt = useRef(new THREE.Vector3(0, 1.1, 0));
  const isUserInteracting = useRef(false);
  const controlsRef = useRef<OrbitControls | null>(null);

  // Spatial 3D Hotspots matching Image 2 layout
  const hotspots: HotspotPin[] = [
    // 10 Station pill cards (projected at conveyor base under each station)
    { id: 'st_1', stationId: 1, label: 'Naloženie puzdra', sublabel: 'OP10 • Robot', badgeCode: '01', x: STATION_X[1], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },
    { id: 'st_2', stationId: 2, label: 'Nalisovanie motora', sublabel: 'OP20 • Lis POZOR', badgeCode: '02', x: STATION_X[2], y: 0.15, z: 1.45, type: 'station', color: '#F59E0B' },
    { id: 'st_3', stationId: 3, label: 'Kamerová kontrola', sublabel: 'OP30 • ALARM ST-038', badgeCode: '03', x: STATION_X[3], y: 0.15, z: 1.45, type: isAlarm ? 'alarm' : 'station', color: isAlarm ? '#EF4444' : '#10B981' },
    { id: 'st_4', stationId: 4, label: 'Skrutkovanie #1', sublabel: 'OP40 • Vreteno', badgeCode: '04', x: STATION_X[4], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },
    { id: 'st_5', stationId: 5, label: 'Skrutkovanie #2', sublabel: 'OP50 • Vision', badgeCode: '05', x: STATION_X[5], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },
    { id: 'st_6', stationId: 6, label: 'Otočenie o 90°', sublabel: 'OP60 • Kolíska', badgeCode: '06', x: STATION_X[6], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },
    { id: 'st_7', stationId: 7, label: 'Vloženie invertora', sublabel: 'OP70 • Portál', badgeCode: '07', x: STATION_X[7], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },
    { id: 'st_8', stationId: 8, label: 'Skrutkovanie inv.', sublabel: 'OP80 • 4-Vreteno', badgeCode: '08', x: STATION_X[8], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },
    { id: 'st_9', stationId: 9, label: 'Test tesnosti', sublabel: 'OP90 • Ateq F620', badgeCode: '09', x: STATION_X[9], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },
    { id: 'st_10', stationId: 10, label: 'Výstup na EOL', sublabel: 'OP100 • Paletizér', badgeCode: '10', x: STATION_X[10], y: 0.15, z: 1.45, type: 'station', color: '#10B981' },

    // Station 3 Sub-component pins for the 5 AI Copilot steps (WIDELY DISTRIBUTED around the station!)
    { id: 'comp_loto', stationId: 3, stepIdx: 0, label: 'Krok 1: LOTO Odpojenie', sublabel: 'Istič QF3 & svorka 24V DC', x: STATION_X[3] - 1.4, y: 2.2, z: 1.1, type: 'component', color: '#EF4444' },
    { id: 'comp_lens', stationId: 3, stepIdx: 1, label: 'Krok 2: Optika Cognex', sublabel: 'Čistenie šošovky 8402P', x: STATION_X[3], y: 1.85, z: 0.35, type: 'component', color: '#38BDF8' },
    { id: 'comp_conn', stationId: 3, stepIdx: 2, label: 'Krok 3: Kábel X2', sublabel: 'M12 svorka (0.6 Nm)', x: STATION_X[3] + 0.85, y: 2.75, z: -0.4, type: 'component', color: '#F59E0B' },
    { id: 'comp_led',  stationId: 3, stepIdx: 3, label: 'Krok 4: LED iluminátor', sublabel: 'Kruhové svetlo (>400 lux)', x: STATION_X[3] + 0.55, y: 1.45, z: 0.75, type: 'component', color: '#38BDF8' },
    { id: 'comp_test', stationId: 3, stepIdx: 4, label: 'Krok 5: In-Sight Test', sublabel: 'Kalibračné lôžko & PLC', x: STATION_X[3] - 0.55, y: 0.85, z: 0.85, type: 'component', color: '#10B981' },
  ];

  // Camera Target Position Calculator
  const updateCameraTarget = useCallback((stationId: number | null, stepIdx: number | null) => {
    if (stepIdx !== null && stationId === 3) {
      // Close-up cinematic focus for each individual component
      switch (stepIdx) {
        case 0: // LOTO Electrical Switch on left cabinet
          targetCamPos.current.set(STATION_X[3] - 1.2, 2.5, 2.8);
          targetLookAt.current.set(STATION_X[3] - 1.4, 2.2, 1.1);
          break;
        case 1: // Optical Lens & Glass
          targetCamPos.current.set(STATION_X[3], 1.7, 2.2);
          targetLookAt.current.set(STATION_X[3], 1.85, 0.35);
          break;
        case 2: // Connector X2 on the back-right
          targetCamPos.current.set(STATION_X[3] + 1.6, 3.1, 1.5);
          targetLookAt.current.set(STATION_X[3] + 0.85, 2.75, -0.4);
          break;
        case 3: // Circular LED Illuminator Ring
          targetCamPos.current.set(STATION_X[3] + 1.2, 1.8, 2.2);
          targetLookAt.current.set(STATION_X[3] + 0.55, 1.45, 0.75);
          break;
        case 4: // Inspection Carrier Bed on conveyor
          targetCamPos.current.set(STATION_X[3] - 0.2, 1.8, 2.6);
          targetLookAt.current.set(STATION_X[3] - 0.55, 0.85, 0.85);
          break;
        default:
          targetCamPos.current.set(STATION_X[3], 2.8, 5.2);
          targetLookAt.current.set(STATION_X[3], 1.8, 0.0);
      }
    } else if (stationId !== null) {
      const posX = STATION_X[stationId] ?? 0;
      targetCamPos.current.set(posX + 1.6, 3.0, 5.2);
      targetLookAt.current.set(posX, 1.5, 0.0);
    } else {
      // Signature Balanced Isometric Wide View matching Image 2
      targetCamPos.current.set(1.5, 11.5, 23.5);
      targetLookAt.current.set(0, 1.1, 0);
    }
  }, []);

  // Sync camera when props change
  useEffect(() => {
    if (!isUserInteracting.current) {
      updateCameraTarget(selectedStationId, activeStepIdx);
    }
  }, [selectedStationId, activeStepIdx, updateCameraTarget]);

  // Main Three.js Scene Setup
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. Scene, Camera, Renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060913); // Deep cyber void
    scene.fog = new THREE.FogExp2(0x060913, 0.015);

    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
    camera.position.copy(targetCamPos.current);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    container.appendChild(renderer.domElement);

    // 2. OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI / 2 - 0.02; // Don't go below ground
    controls.minDistance = 1.5;
    controls.maxDistance = 45;
    controls.target.copy(targetLookAt.current);
    controlsRef.current = controls;

    controls.addEventListener('start', () => { isUserInteracting.current = true; });
    controls.addEventListener('end', () => {
      setTimeout(() => { isUserInteracting.current = false; }, 3500);
    });

    // 3. Cyber-Industrial Studio Lighting Setup
    const ambientLight = new THREE.AmbientLight(0x1E293B, 2.4);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xF8FAFC, 2.6);
    keyLight.position.set(16, 26, 18);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 2048;
    keyLight.shadow.mapSize.height = 2048;
    keyLight.shadow.bias = -0.0001;
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x38BDF8, 1.8);
    rimLight.position.set(-18, 14, -12);
    scene.add(rimLight);

    // Dynamic Station 3 Red Volumetric Spotlight (Alarm)
    const st3Spot = new THREE.SpotLight(isAlarm ? 0xEF4444 : 0x38BDF8, 5.0, 16, Math.PI / 4, 0.4, 1.2);
    st3Spot.position.set(STATION_X[3], 6.5, 0);
    st3Spot.target.position.set(STATION_X[3], 0, 0);
    scene.add(st3Spot);
    scene.add(st3Spot.target);

    // 4. Studio Ground Plane & Subtle Tech Grid
    const floorGeo = new THREE.PlaneGeometry(80, 50);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x070B14,
      roughness: 0.88,
      metalness: 0.25,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const grid = new THREE.GridHelper(56, 56, 0x1E293B, 0x0A0F1D);
    grid.position.y = 0.005;
    scene.add(grid);

    // Common Materials
    const darkMachineMat = new THREE.MeshStandardMaterial({
      color: 0x141B26,
      metalness: 0.7,
      roughness: 0.35,
    });
    const chromeMat = new THREE.MeshStandardMaterial({
      color: 0xE2E8F0,
      metalness: 0.95,
      roughness: 0.1,
    });
    const smokedGlassMat = new THREE.MeshPhysicalMaterial({
      color: 0x1E293B,
      transparent: true,
      opacity: 0.3,
      roughness: 0.15,
      metalness: 0.1,
      transmission: 0.85,
    });

    // Helper: Add floor ambient glow disc underneath station (Image 2 signature)
    const floorGlows: THREE.Mesh[] = [];
    const addFloorGlow = (x: number, color: number, radius = 1.45, opacity = 0.35) => {
      const disc = new THREE.Mesh(
        new THREE.CircleGeometry(radius, 32),
        new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity,
          blending: THREE.AdditiveBlending,
          side: THREE.DoubleSide
        })
      );
      disc.rotation.x = -Math.PI / 2;
      disc.position.set(x, 0.015, 0);
      scene.add(disc);
      return disc;
    };

    // Add Floor Glows across all 10 stations
    Object.entries(STATION_X).forEach(([stIdStr, xPos]) => {
      const stId = parseInt(stIdStr, 10);
      let col = 0x10B981; // Green for normal
      let op = 0.28;
      if (stId === 3) {
        col = isAlarm ? 0xEF4444 : 0x10B981; // Red for ALARM Station 3
        op = isAlarm ? 0.75 : 0.35;
      } else if (stId === 2) {
        col = 0xF59E0B; // Amber for POZOR Station 2
        op = 0.45;
      }
      floorGlows.push(addFloorGlow(xPos, col, 1.45, op));
    });

    // 5. Heavy-Duty Continuous Conveyor Assembly with Glowing Neon Guide Rails
    const conveyorGroup = new THREE.Group();
    
    // Conveyor Dual Rails with Cyan/Blue Neon Edges
    const railGeo = new THREE.BoxGeometry(36, 0.16, 0.1);
    const railNeonMat = new THREE.MeshStandardMaterial({ color: 0x38BDF8, emissive: 0x0284C7, emissiveIntensity: 0.8 });
    const rail1 = new THREE.Mesh(railGeo, railNeonMat);
    rail1.position.set(0, 0.75, -1.05);
    const rail2 = new THREE.Mesh(railGeo, railNeonMat);
    rail2.position.set(0, 0.75, 1.05);
    conveyorGroup.add(rail1, rail2);

    // Dark Matte Segmented Conveyor Belt Bed
    const beltMat = new THREE.MeshStandardMaterial({ color: 0x0F141F, roughness: 0.95 });
    const beltGeo = new THREE.BoxGeometry(36, 0.08, 1.96);
    const belt = new THREE.Mesh(beltGeo, beltMat);
    belt.position.set(0, 0.69, 0);
    conveyorGroup.add(belt);

    // Rollers under the belt
    const rollerGeo = new THREE.CylinderGeometry(0.04, 0.04, 2.0, 12);
    const rollerMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8 });
    for (let rx = -17.5; rx <= 17.5; rx += 1.2) {
      const roller = new THREE.Mesh(rollerGeo, rollerMat);
      roller.rotation.x = Math.PI / 2;
      roller.position.set(rx, 0.64, 0);
      conveyorGroup.add(roller);
    }

    // Heavy Stanchion Frame Legs
    const legGeo = new THREE.CylinderGeometry(0.065, 0.065, 0.68, 16);
    const footGeo = new THREE.CylinderGeometry(0.13, 0.15, 0.05, 16);
    for (let x = -17; x <= 17; x += 3.4) {
      [-0.95, 0.95].forEach((zPos) => {
        const leg = new THREE.Mesh(legGeo, darkMachineMat);
        leg.position.set(x, 0.34, zPos);
        const foot = new THREE.Mesh(footGeo, rollerMat);
        foot.position.set(x, 0.025, zPos);
        conveyorGroup.add(leg, foot);
      });
    }
    scene.add(conveyorGroup);

    // 6. BUILD DETAILED MAGNA POWERTRAINS ON PALLETS
    const createPowertrainPallet = (xPos: number) => {
      const g = new THREE.Group();
      g.position.set(xPos, 0.75, 0);

      // Shadow disc on belt
      const shadowDisc = new THREE.Mesh(
        new THREE.RingGeometry(0.1, 0.9, 24),
        new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.55, side: THREE.DoubleSide })
      );
      shadowDisc.rotation.x = -Math.PI / 2;
      shadowDisc.position.y = 0.005;
      g.add(shadowDisc);

      // Carrier Pallet (Blue Neon Outline)
      const palBody = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.12, 1.4), darkMachineMat);
      palBody.position.y = 0.06;
      g.add(palBody);

      const palEdges = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(1.4, 0.12, 1.4)),
        new THREE.LineBasicMaterial({ color: 0x3B82F6, linewidth: 2 })
      );
      palEdges.position.y = 0.06;
      g.add(palEdges);

      // Cast Aluminum Motor Housing
      const housingMat = new THREE.MeshStandardMaterial({ color: 0x94A3B8, metalness: 0.85, roughness: 0.25 });
      const housing = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.6, 0.85), housingMat);
      housing.position.y = 0.42;
      housing.castShadow = true;
      g.add(housing);

      // Stator Core & Copper Hairpin Windings
      const statorCore = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.64, 20), new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8 }));
      statorCore.position.y = 0.44;
      const copper = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.26, 0.7, 20), new THREE.MeshStandardMaterial({ color: 0xC26330, metalness: 0.9, roughness: 0.25 }));
      copper.position.y = 0.44;
      g.add(statorCore, copper);

      return g;
    };

    // ========================================================================
    // 7. ARCHITECTURAL OPEN-FRONT CYBER-TUNNEL BOOTHS (IMAGE 2 STYLE)
    // FRONT IS 100% OPEN - NO SOLID BLACK BOXES!
    // Real Emissive 3D Bars for Vibrant Neon Portal Outline!
    // ========================================================================
    const createOpenCyberBooth = (neonColor: number, emissiveColor: number, options?: { isAlarm?: boolean; isWarning?: boolean }) => {
      const g = new THREE.Group();

      const width = 2.1;
      const height = 2.5;
      const depth = 2.1;
      const wallThickness = 0.12;

      // Top Roof Slab
      const roof = new THREE.Mesh(
        new THREE.BoxGeometry(width, wallThickness, depth),
        darkMachineMat
      );
      roof.position.set(0, height - wallThickness / 2, 0);
      roof.castShadow = true;
      g.add(roof);

      // Rear Back Wall
      const backWall = new THREE.Mesh(
        new THREE.BoxGeometry(width, height - wallThickness, wallThickness),
        darkMachineMat
      );
      backWall.position.set(0, (height - wallThickness) / 2, -depth / 2 + wallThickness / 2);
      backWall.castShadow = true;
      g.add(backWall);

      // Left & Right Vertical Frame Pillars (Front & Back)
      const postGeo = new THREE.BoxGeometry(0.1, height, 0.1);
      const postFL = new THREE.Mesh(postGeo, darkMachineMat);
      postFL.position.set(-width / 2 + 0.05, height / 2, depth / 2 - 0.05);
      const postFR = new THREE.Mesh(postGeo, darkMachineMat);
      postFR.position.set(width / 2 - 0.05, height / 2, depth / 2 - 0.05);
      const postBL = new THREE.Mesh(postGeo, darkMachineMat);
      postBL.position.set(-width / 2 + 0.05, height / 2, -depth / 2 + 0.05);
      const postBR = new THREE.Mesh(postGeo, darkMachineMat);
      postBR.position.set(width / 2 - 0.05, height / 2, -depth / 2 + 0.05);
      g.add(postFL, postFR, postBL, postBR);

      // Left & Right Smoked Transparent Acrylic Side Windows (Upper Half)
      const sideWindowGeo = new THREE.BoxGeometry(0.04, 1.2, depth - 0.2);
      const winL = new THREE.Mesh(sideWindowGeo, smokedGlassMat);
      winL.position.set(-width / 2 + 0.05, 1.7, 0);
      const winR = new THREE.Mesh(sideWindowGeo, smokedGlassMat);
      winR.position.set(width / 2 - 0.05, 1.7, 0);
      g.add(winL, winR);

      // ====================================================================
      // VIBRANT EMISSIVE 3D NEON ARCH BARS (Pure rich neon color without blowout!)
      // ====================================================================
      const neonEmissiveMat = new THREE.MeshStandardMaterial({
        color: neonColor,
        emissive: emissiveColor,
        emissiveIntensity: options?.isAlarm ? 1.6 : 1.2,
        roughness: 0.1,
      });

      const barThickness = 0.04;
      // Left vertical glowing neon bar
      const barVL = new THREE.Mesh(new THREE.BoxGeometry(barThickness, height, barThickness), neonEmissiveMat);
      barVL.position.set(-width / 2, height / 2, depth / 2);
      // Right vertical glowing neon bar
      const barVR = new THREE.Mesh(new THREE.BoxGeometry(barThickness, height, barThickness), neonEmissiveMat);
      barVR.position.set(width / 2, height / 2, depth / 2);
      // Top horizontal glowing neon bar
      const barHT = new THREE.Mesh(new THREE.BoxGeometry(width + barThickness, barThickness, barThickness), neonEmissiveMat);
      barHT.position.set(0, height, depth / 2);
      // Roof side neon bars
      const barSL = new THREE.Mesh(new THREE.BoxGeometry(barThickness, barThickness, depth), neonEmissiveMat);
      barSL.position.set(-width / 2, height, 0);
      const barSR = new THREE.Mesh(new THREE.BoxGeometry(barThickness, barThickness, depth), neonEmissiveMat);
      barSR.position.set(width / 2, height, 0);

      g.add(barVL, barVR, barHT, barSL, barSR);

      // Interior Canopy Downlight illuminating inside tooling
      const downLight = new THREE.PointLight(neonColor, options?.isAlarm ? 2.5 : 1.2, 3.5);
      downLight.position.set(0, height - 0.2, 0);
      g.add(downLight);

      return { group: g, neonEmissiveMat };
    };

    // 8. BUILD 10 PRODUCTION STATIONS (WITH VISIBLE INTERNAL MACHINERY!)
    const stationsGroup = new THREE.Group();

    // ========================================================================
    // STATION 1: Infeed Loading Station (Articulated Industrial Robot Arm)
    // ========================================================================
    const st1 = new THREE.Group();
    st1.position.set(STATION_X[1], 0, 0);
    const st1Booth = createOpenCyberBooth(0x10B981, 0x059669);
    st1.add(st1Booth.group, createPowertrainPallet(0));

    // Robot Base & Articulated Arm (Yellow/Anthracite Magna Robot)
    const robotBase = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.28, 0.45, 20), darkMachineMat);
    robotBase.position.set(-0.6, 0.9, -0.45);
    const robotArmLower = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.7, 0.14), new THREE.MeshStandardMaterial({ color: 0xF59E0B, metalness: 0.6 }));
    robotArmLower.position.set(-0.45, 1.35, -0.3);
    robotArmLower.rotation.z = -Math.PI / 6;
    const robotArmUpper = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.65, 0.12), new THREE.MeshStandardMaterial({ color: 0xF59E0B, metalness: 0.6 }));
    robotArmUpper.position.set(-0.25, 1.7, -0.15);
    robotArmUpper.rotation.z = Math.PI / 5;
    const gripper = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.08, 0.2), chromeMat);
    gripper.position.set(-0.08, 1.45, 0);
    st1.add(robotBase, robotArmLower, robotArmUpper, gripper);
    stationsGroup.add(st1);

    // ========================================================================
    // STATION 2: Electric Motor Press Cell (Hydraulic Chrome Ram - POZOR)
    // ========================================================================
    const st2 = new THREE.Group();
    st2.position.set(STATION_X[2], 0, 0);
    const st2Booth = createOpenCyberBooth(0xF59E0B, 0xD97706, { isWarning: true });
    st2.add(st2Booth.group, createPowertrainPallet(0));

    const pressCylinder = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.6, 20), darkMachineMat);
    pressCylinder.position.set(0, 2.15, 0);
    const pressPiston = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.9, 20), chromeMat);
    pressPiston.position.set(0, 1.75, 0);
    const pressPlate = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 0.08, 20), chromeMat);
    pressPlate.position.set(0, 1.32, 0);
    st2.add(pressCylinder, pressPiston, pressPlate);
    stationsGroup.add(st2);

    // ========================================================================
    // STATION 3: COGNEX VISION INSPECTION CELL (ALARM ST-038 - RED NEON GLOW)
    // ========================================================================
    const st3 = new THREE.Group();
    st3.position.set(STATION_X[3], 0, 0);

    const st3NeonCol = isAlarm ? 0xEF4444 : 0x10B981;
    const st3EmissCol = isAlarm ? 0xDC2626 : 0x059669;
    const st3Booth = createOpenCyberBooth(st3NeonCol, st3EmissCol, { isAlarm });
    st3.add(st3Booth.group);

    // Realistic Industrial Andon Stack Light Tower on roof
    if (isAlarm) {
      const andonGroup = new THREE.Group();
      andonGroup.position.set(0, 2.5, 0.95);
      const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.2, 12), darkMachineMat);
      mast.position.y = 0.1;
      const redLight = new THREE.Mesh(
        new THREE.CylinderGeometry(0.065, 0.065, 0.14, 16),
        new THREE.MeshStandardMaterial({ color: 0xEF4444, emissive: 0xDC2626, emissiveIntensity: 2.0 })
      );
      redLight.position.y = 0.27;
      const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.03, 16), darkMachineMat);
      cap.position.y = 0.355;
      andonGroup.add(mast, redLight, cap);
      st3.add(andonGroup);
    }

    // Step 1: Left Electrical Control Cabinet with Red LOTO Switch (QF3)
    const lotoCabinet = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.65, 0.35), darkMachineMat);
    lotoCabinet.position.set(-1.4, 2.2, 1.05);
    const lotoCabinetEdges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(0.32, 0.65, 0.35)),
      new THREE.LineBasicMaterial({ color: 0xEF4444, linewidth: 2 })
    );
    lotoCabinetEdges.position.set(-1.4, 2.2, 1.05);
    const lotoSwitch = new THREE.Mesh(
      new THREE.CylinderGeometry(0.065, 0.065, 0.1, 16),
      new THREE.MeshStandardMaterial({ color: 0xEF4444, emissive: 0xDC2626, emissiveIntensity: 1.5 })
    );
    lotoSwitch.rotation.z = Math.PI / 2;
    lotoSwitch.position.set(-1.22, 2.2, 1.05);
    st3.add(lotoCabinet, lotoCabinetEdges, lotoSwitch);

    // Overhead Camera Mounting Gantry Rig
    const camGantry = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.12, 1.2), darkMachineMat);
    camGantry.position.set(0, 2.4, 0);
    st3.add(camGantry);

    // Step 2 & 4: Cognex In-Sight 8402P Optical Camera Unit
    const cameraGroup = new THREE.Group();
    cameraGroup.position.set(0, 2.25, 0);

    // Camera Main Body (Graphite with Cognex Yellow Stripe)
    const camBody = new THREE.Mesh(new THREE.BoxGeometry(0.48, 0.5, 0.48), darkMachineMat);
    const camBodyEdges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(0.48, 0.5, 0.48)),
      new THREE.LineBasicMaterial({ color: st3NeonCol, linewidth: 2 })
    );
    const cognexStripe = new THREE.Mesh(
      new THREE.BoxGeometry(0.49, 0.08, 0.49),
      new THREE.MeshStandardMaterial({ color: 0xFACC15, roughness: 0.3 })
    );
    cognexStripe.position.y = 0.12;
    cameraGroup.add(camBody, camBodyEdges, cognexStripe);

    // Optical Lens Barrel
    const lensBarrel = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.22, 0.45, 24),
      new THREE.MeshStandardMaterial({ color: 0x0A0F1D, metalness: 0.92, roughness: 0.15 })
    );
    lensBarrel.position.set(0, -0.42, 0);
    cameraGroup.add(lensBarrel);

    // Anti-Reflective Cyan Coated Glass Lens Element
    const lensGlass = new THREE.Mesh(
      new THREE.CircleGeometry(0.17, 24),
      new THREE.MeshPhysicalMaterial({ color: 0x38BDF8, roughness: 0.04, transmission: 0.95, ior: 1.55 })
    );
    lensGlass.rotation.x = Math.PI / 2;
    lensGlass.position.set(0, -0.65, 0);
    cameraGroup.add(lensGlass);

    // Step 4: Circular LED Illuminator Ring (Pulsing Red Torus)
    const ledRingMat = new THREE.MeshStandardMaterial({
      color: isAlarm ? 0xEF4444 : 0x38BDF8,
      emissive: isAlarm ? 0xDC2626 : 0x0284C7,
      emissiveIntensity: 2.2,
      roughness: 0.15
    });
    const ledTorus = new THREE.Mesh(new THREE.TorusGeometry(0.26, 0.04, 16, 32), ledRingMat);
    ledTorus.rotation.x = Math.PI / 2;
    ledTorus.position.set(0, -0.6, 0);
    cameraGroup.add(ledTorus);

    // Step 3: M12 Connector X2 with Orange Wiring
    const connX2 = new THREE.Mesh(
      new THREE.BoxGeometry(0.2, 0.18, 0.22),
      new THREE.MeshStandardMaterial({ color: 0xF59E0B, metalness: 0.5 })
    );
    connX2.position.set(0.85, 2.75, -0.4);
    const connX2Wire = new THREE.Mesh(
      new THREE.CylinderGeometry(0.02, 0.02, 0.8, 12),
      new THREE.MeshStandardMaterial({ color: 0xEA580C })
    );
    connX2Wire.position.set(0.45, 2.5, -0.2);
    connX2Wire.rotation.z = Math.PI / 3;
    st3.add(connX2, connX2Wire);

    // Holographic Optical Scanning Beam Cone (Volumetric light cone shining down)
    const coneMat = new THREE.MeshBasicMaterial({
      color: isAlarm ? 0xEF4444 : 0x38BDF8,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide
    });
    const scanCone = new THREE.Mesh(new THREE.ConeGeometry(0.85, 1.25, 24, 1, true), coneMat);
    scanCone.rotation.x = Math.PI;
    scanCone.position.set(0, -1.25, 0);
    cameraGroup.add(scanCone);

    st3.add(cameraGroup, createPowertrainPallet(0));
    stationsGroup.add(st3);

    // ========================================================================
    // STATIONS 4 & 5: Automatic Screwdriver Cells (Spindles & Operator Screen)
    // ========================================================================
    [STATION_X[4], STATION_X[5]].forEach((xPos, idx) => {
      const stScrew = new THREE.Group();
      stScrew.position.set(xPos, 0, 0);
      const booth = createOpenCyberBooth(0x10B981, 0x059669);
      stScrew.add(booth.group, createPowertrainPallet(0));

      // Screwdriver Spindle
      const spindle = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.9, 16), chromeMat);
      spindle.position.set(0, 1.85, 0);
      stScrew.add(spindle);

      // Station 5 has an Operator Touch Display Screen on the front right post
      if (idx === 1) {
        const screenArm = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.35, 12), chromeMat);
        screenArm.rotation.z = Math.PI / 2;
        screenArm.position.set(0.95, 1.7, 0.95);
        const touchScreen = new THREE.Mesh(
          new THREE.BoxGeometry(0.42, 0.32, 0.04),
          new THREE.MeshStandardMaterial({ color: 0x090D16, roughness: 0.2 })
        );
        touchScreen.position.set(1.15, 1.7, 0.95);
        const screenDisplay = new THREE.Mesh(
          new THREE.PlaneGeometry(0.38, 0.28),
          new THREE.MeshStandardMaterial({ color: 0x10B981, emissive: 0x059669, emissiveIntensity: 1.2 })
        );
        screenDisplay.position.set(1.15, 1.7, 0.98);
        stScrew.add(screenArm, touchScreen, screenDisplay);
      }
      stationsGroup.add(stScrew);
    });

    // ========================================================================
    // STATION 6: 90° Rotator Mechanism (Rotary Cradle Ring)
    // ========================================================================
    const st6 = new THREE.Group();
    st6.position.set(STATION_X[6], 0, 0);
    const st6Booth = createOpenCyberBooth(0x10B981, 0x059669);
    st6.add(st6Booth.group, createPowertrainPallet(0));

    const ringCradle = new THREE.Mesh(new THREE.TorusGeometry(0.85, 0.08, 16, 32), chromeMat);
    ringCradle.position.set(0, 1.25, 0);
    ringCradle.rotation.y = Math.PI / 4;
    st6.add(ringCradle);
    stationsGroup.add(st6);

    // ========================================================================
    // STATIONS 7 & 8: Inverter Insertion Gantry & Tightening
    // ========================================================================
    [STATION_X[7], STATION_X[8]].forEach((xPos, idx) => {
      const stInv = new THREE.Group();
      stInv.position.set(xPos, 0, 0);
      const booth = createOpenCyberBooth(0x10B981, 0x059669);
      stInv.add(booth.group, createPowertrainPallet(0));

      if (idx === 0) {
        // Inverter insertion gripper
        const invUnit = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.25, 0.45), chromeMat);
        invUnit.position.set(0, 1.6, 0);
        stInv.add(invUnit);
      } else {
        // 4-Spindle tightener
        const spindleGantry = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.08, 0.5), darkMachineMat);
        spindleGantry.position.set(0, 1.85, 0);
        [-0.15, 0.15].forEach(sx => {
          [-0.15, 0.15].forEach(sz => {
            const sp = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.6, 12), chromeMat);
            sp.position.set(sx, 1.55, sz);
            stInv.add(sp);
          });
        });
        stInv.add(spindleGantry);
      }
      stationsGroup.add(stInv);
    });

    // ========================================================================
    // STATION 9: Ateq Leak Test Chamber (Differential Pressure)
    // ========================================================================
    const st9 = new THREE.Group();
    st9.position.set(STATION_X[9], 0, 0);
    const st9Booth = createOpenCyberBooth(0x10B981, 0x059669);
    st9.add(st9Booth.group, createPowertrainPallet(0));

    const testBell = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.5, 0.7, 24), chromeMat);
    testBell.position.set(0, 1.7, 0);
    st9.add(testBell);
    stationsGroup.add(st9);

    // ========================================================================
    // STATION 10: EOL Output / Palletize Station (Transfer Robot)
    // ========================================================================
    const st10 = new THREE.Group();
    st10.position.set(STATION_X[10], 0, 0);
    const st10Booth = createOpenCyberBooth(0x10B981, 0x059669);
    st10.add(st10Booth.group, createPowertrainPallet(0));

    const robotBase10 = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.28, 0.45, 20), darkMachineMat);
    robotBase10.position.set(0.6, 0.9, -0.45);
    const arm10 = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.75, 0.14), new THREE.MeshStandardMaterial({ color: 0xF59E0B, metalness: 0.6 }));
    arm10.position.set(0.4, 1.4, -0.3);
    arm10.rotation.z = Math.PI / 6;
    st10.add(robotBase10, arm10);
    stationsGroup.add(st10);

    scene.add(stationsGroup);

    // 9. Animation & Render Loop with Smooth Camera Lerp and Hotspot 2D Projection
    let animationFrameId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smooth Camera & Controls Lerp
      if (!isUserInteracting.current) {
        camera.position.lerp(targetCamPos.current, 0.055);
        controls.target.lerp(targetLookAt.current, 0.055);
      }
      controls.update();

      // Pulsing Neon Glow on Station 3 Alarm
      if (isAlarm) {
        const pulse = (Math.sin(elapsed * 6) + 1) * 0.5;
        ledRingMat.emissiveIntensity = 1.2 + pulse * 2.0;
        st3Booth.neonEmissiveMat.emissiveIntensity = 1.3 + pulse * 1.5;
        scanCone.scale.set(1 + pulse * 0.06, 1, 1 + pulse * 0.06);
        st3Spot.intensity = 3.5 + pulse * 3.5;
        if (floorGlows[2]) {
          (floorGlows[2].material as THREE.MeshBasicMaterial).opacity = 0.5 + pulse * 0.45;
        }
      } else {
        ledRingMat.emissiveIntensity = 1.8;
      }

      // Project 3D Hotspots to Screen Coordinates
      const currentWidth = container.clientWidth;
      const currentHeight = container.clientHeight;
      const tempVec = new THREE.Vector3();

      const projected = hotspots.map((spot) => {
        // In Station focus: ONLY show component pins for the selected station
        if (spot.type === 'component') {
          if (isOverview || spot.stationId !== selectedStationId) {
            return { pin: spot, screenX: 0, screenY: 0, visible: false };
          }
        }
        
        // In Overview: ONLY show station base cards
        if (spot.type === 'station' || spot.type === 'alarm') {
          if (!isOverview && spot.stationId !== selectedStationId) {
            return { pin: spot, screenX: 0, screenY: 0, visible: false };
          }
        }

        tempVec.set(spot.x, spot.y, spot.z);
        tempVec.project(camera);

        const isBehind = tempVec.z > 1.0;
        const screenX = (tempVec.x * 0.5 + 0.5) * currentWidth;
        const screenY = (-(tempVec.y * 0.5) + 0.5) * currentHeight;

        const isInsideBounds = screenX >= 0 && screenX <= currentWidth && screenY >= 0 && screenY <= currentHeight;

        return {
          pin: spot,
          screenX,
          screenY,
          visible: !isBehind && isInsideBounds
        };
      });

      setProjectedPins(projected);
      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [hotspots, isAlarm, isOverview, selectedStationId]);

  return (
    <div className="relative w-full h-[460px] sm:h-[500px] lg:h-[560px] bg-[#060913] rounded-[32px] overflow-hidden border border-[#1E293B] shadow-[0px_8px_32px_rgba(0,0,0,0.6)]">
      
      {/* 3D WebGL Canvas Mount */}
      <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Top Left Navigation Header (Back Button style) */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
        {!isOverview ? (
          <button
            onClick={() => {
              onSelectStation(null);
              onSelectStep(-1);
              updateCameraTarget(null, null);
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#0F172A]/90 hover:bg-[#1E293B] text-white text-xs font-bold border border-white/20 shadow-2xl backdrop-blur-md transition-all active:scale-95"
          >
            <ArrowLeft className="w-4 h-4 text-[#38BDF8]" />
            <span>‹ Späť na celú linku (Izometrický prehľad)</span>
          </button>
        ) : (
          <div className="px-4 py-2 rounded-full bg-[#0F172A]/85 backdrop-blur-md border border-white/10 text-white text-xs font-semibold flex items-center gap-2.5 shadow-xl">
            <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] animate-pulse" />
            <span>Pohľad: <b>Izometrický Cyber-Twin L01 (3D WebGL)</b></span>
          </div>
        )}
      </div>

      {/* Top Right Controls: Reset Camera & Orbit Tip */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <button
          onClick={() => {
            onSelectStation(null);
            onSelectStep(-1);
            updateCameraTarget(null, null);
          }}
          className="p-2.5 rounded-full bg-[#0F172A]/80 hover:bg-[#1E293B] text-[#94A3B8] hover:text-white border border-white/10 shadow-lg backdrop-blur-md transition-all"
          title="Resetovať polohu kamery na izometrický rakurz"
        >
          <RotateCw className="w-4 h-4" />
        </button>
        <div className="px-3.5 py-2 rounded-full bg-[#0F172A]/80 backdrop-blur-md border border-white/10 text-[11px] text-[#94A3B8] font-mono hidden sm:flex items-center gap-1.5">
          <Crosshair className="w-3.5 h-3.5 text-[#38BDF8]" />
          <span>Myš: Ľavé tlačidlo = Otočiť 360° • Koliesko = Zoom</span>
        </div>
      </div>

      {/* 2D HTML/SVG Overlaid 3D Hotspot Pins (Projected from 3D coordinates!) */}
      {projectedPins.map(({ pin, screenX, screenY, visible }) => {
        if (!visible) return null;

        const isComponentPin = pin.type === 'component';
        const isPinActive = pin.stepIdx === activeStepIdx;
        const isAlarmPin = pin.type === 'alarm';

        return (
          <div
            key={pin.id}
            style={{
              position: 'absolute',
              left: `${screenX}px`,
              top: `${screenY}px`,
              transform: 'translate(-50%, -50%)',
              pointerEvents: 'auto',
              zIndex: isPinActive ? 35 : 20
            }}
            className="group"
          >
            {isComponentPin ? (
              // Component Pin (e.g. Lens, Connector X2, Illuminator)
              // SMART EXPANSION: Only active pin or hovered pin shows full card to prevent stacking!
              <div 
                onClick={() => pin.stepIdx !== undefined && onSelectStep(pin.stepIdx)}
                className="cursor-pointer flex flex-col items-center"
              >
                {/* Sleek Circular Beacon Badge with Step Number */}
                <div className={`relative flex items-center justify-center transition-transform duration-200 ${
                  isPinActive ? 'scale-125' : 'hover:scale-115'
                }`}>
                  <span 
                    className="absolute w-7 h-7 rounded-full animate-ping opacity-45"
                    style={{ backgroundColor: pin.color }}
                  />
                  <div 
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-mono font-extrabold shadow-2xl border-2 transition-all ${
                      isPinActive ? 'border-white ring-4 ring-white/30 scale-110' : 'border-white/80'
                    }`}
                    style={{ backgroundColor: pin.color }}
                  >
                    {pin.stepIdx !== undefined ? pin.stepIdx + 1 : '+'}
                  </div>
                </div>

                {/* Pin Tooltip Label: Expanded when active, or on hover! */}
                <div className={`mt-1.5 px-3 py-1.5 rounded-xl shadow-2xl text-[10.5px] font-bold whitespace-nowrap transition-all duration-200 border backdrop-blur-md ${
                  isPinActive 
                    ? 'block bg-[#090D16] text-white border-[#38BDF8] ring-2 ring-[#38BDF8]/50 scale-105 z-30' 
                    : 'hidden group-hover:block bg-[#090D16]/95 text-[#E2E8F0] border-white/20 z-20'
                }`}>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: pin.color }} />
                    <span>{pin.label}</span>
                  </div>
                  <div className="text-[9px] text-[#94A3B8] font-normal mt-0.5">
                    {pin.sublabel}
                  </div>
                </div>
              </div>
            ) : (
              // Station Pill Card at Base (Matching Image 2 exactly!)
              <button
                onClick={() => onSelectStation(pin.stationId)}
                className={`flex flex-col items-center p-2 rounded-xl text-center transition-all duration-300 shadow-2xl backdrop-blur-md border min-w-[92px] ${
                  isAlarmPin 
                    ? 'bg-[#EF4444]/25 border-[#EF4444] text-white ring-2 ring-[#EF4444]/60 scale-105 animate-pulse' 
                    : pin.stationId === selectedStationId
                    ? 'bg-[#3B82F6]/25 border-[#38BDF8] text-white ring-2 ring-[#38BDF8]/60 scale-105'
                    : 'bg-[#0B0F19]/90 border-[#1E293B] text-[#94A3B8] hover:text-white hover:border-[#10B981] hover:scale-105'
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-mono font-extrabold px-1.5 py-0.5 rounded bg-white/10 text-white">
                    {pin.badgeCode}
                  </span>
                  {isAlarmPin && <span className="text-[11px]">⚠️</span>}
                </div>
                <div className="text-[10px] font-bold tracking-tight text-white mt-0.5">
                  {pin.label}
                </div>
                <div className={`text-[8.5px] font-semibold mt-0.5 ${
                  isAlarmPin ? 'text-[#EF4444]' : 'text-[#10B981]'
                }`}>
                  {isAlarmPin ? 'ALARM ST-038' : 'Running OK'}
                </div>
              </button>
            )}
          </div>
        );
      })}

      {/* Bottom Status Ticker */}
      <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between text-xs z-10 pointer-events-none">
        <div className="px-3.5 py-1.5 rounded-full bg-[#090D16]/90 backdrop-blur-md border border-white/10 text-[#94A3B8] text-[11px] flex items-center gap-2 shadow-lg pointer-events-auto">
          <span className="w-2 h-2 rounded-full bg-[#3B82F6]" />
          <span>Vybraté: <b className="text-white">{selectedStationId ? `OP${selectedStationId * 10}` : 'Celá linka (10 staníc)'}</b> {activeStepIdx !== null && <span className="text-[#38BDF8]">› Krok {activeStepIdx + 1}</span>}</span>
        </div>

        {selectedStationId === 3 && isAlarm && (
          <div className="px-4 py-1.5 rounded-full bg-[#EF4444]/25 backdrop-blur-md border border-[#EF4444]/60 text-[#FCA5A5] text-[11px] font-bold flex items-center gap-2 animate-pulse shadow-lg pointer-events-auto">
            <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
            <span>Kritická porucha: ST-038 (Optická kamera Cognex)</span>
          </div>
        )}
      </div>

    </div>
  );
};